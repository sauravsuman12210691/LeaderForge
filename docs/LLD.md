# Low-Level Design (LLD) - LeaderForge

## 1. Database Schema

### 1.1 Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

**Columns**:
- `id`: Auto-incrementing primary key
- `username`: Unique username (indexed for fast lookups)
- `email`: Unique email address
- `created_at`: Account creation timestamp

**Constraints**:
- Primary key on `id`
- Unique constraints on `username` and `email`

### 1.2 Game Sessions Table

```sql
CREATE TABLE game_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    score INTEGER NOT NULL CHECK (score >= 0),
    played_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sessions_user ON game_sessions(user_id);
CREATE INDEX idx_sessions_played_at ON game_sessions(played_at);
CREATE INDEX idx_sessions_user_score ON game_sessions(user_id, score DESC);
```

**Columns**:
- `id`: Auto-incrementing primary key
- `user_id`: Foreign key to users table
- `score`: Game score (non-negative)
- `played_at`: Timestamp of game session

**Constraints**:
- Foreign key to users table
- Check constraint: score >= 0

**Indexes**:
- Composite index on (user_id, score DESC) for efficient user score queries
- Index on played_at for time-based queries

### 1.3 Leaderboard Table

```sql
CREATE TABLE leaderboard (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    username VARCHAR(50) NOT NULL,
    total_score BIGINT NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_leaderboard_score_desc ON leaderboard(total_score DESC);
```

**Columns**:
- `user_id`: Primary key, foreign key to users
- `username`: Denormalized username for faster queries
- `total_score`: Aggregated total score (BIGINT for large values)
- `session_count`: Number of games played
- `last_updated`: Last update timestamp

**Design Decision**: Materialized aggregation
- Instead of calculating SUM(score) on every query, we maintain aggregated data
- Trade-off: Extra writes on score submission vs. much faster reads
- For a leaderboard system with high read/write ratio, this is optimal

**Indexes**:
- Descending B-tree index on total_score for fast top-N queries
- PostgreSQL uses this index efficiently for ORDER BY ... DESC LIMIT queries

## 2. API Endpoints

### 2.1 Submit Score

```python
POST /api/scores
Content-Type: application/json

Request Body:
{
    "user_id": int,  # Required, > 0
    "score": int     # Required, >= 0, <= 1000000
}

Response (200 OK):
{
    "success": bool,
    "user_id": int,
    "new_total_score": int,
    "current_rank": int | null,
    "message": str
}

Response (404 Not Found):
{
    "detail": "User not found"
}

Response (422 Validation Error):
{
    "detail": [
        {
            "loc": ["body", "score"],
            "msg": "Score cannot exceed 1,000,000",
            "type": "value_error"
        }
    ]
}
```

**Implementation Logic**:

```python
async def submit_score(submission: ScoreSubmission, db: Session):
    # 1. Verify user exists
    user = db.query(User).filter(User.id == submission.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    # 2. Start transaction
    # 3. Insert game session
    game_session = GameSession(
        user_id=submission.user_id,
        score=submission.score
    )
    db.add(game_session)
    
    # 4. Upsert leaderboard (atomic operation)
    upsert_query = """
        INSERT INTO leaderboard (user_id, username, total_score, session_count)
        VALUES (:user_id, :username, :score, 1)
        ON CONFLICT (user_id)
        DO UPDATE SET
            total_score = leaderboard.total_score + :score,
            session_count = leaderboard.session_count + 1,
            last_updated = NOW()
        RETURNING total_score
    """
    result = db.execute(upsert_query, {...})
    new_total_score = result.fetchone()[0]
    
    # 5. Commit transaction
    db.commit()
    
    # 6. Invalidate caches
    cache.invalidate_user_cache(user_id)
    cache.invalidate_top_cache()
    
    # 7. Calculate new rank
    rank = calculate_rank(user_id, db)
    
    return response
```

**Complexity**:
- Time: O(log n) for index updates + O(1) for cache invalidation
- Space: O(1)

### 2.2 Get Top Players

```python
GET /api/leaderboard/top?limit={N}

Query Parameters:
- limit: int (default=10, min=1, max=100)

Response (200 OK):
{
    "top_players": [
        {
            "rank": int,
            "user_id": int,
            "username": str,
            "total_score": int,
            "session_count": int
        }
    ],
    "total_players": int,
    "timestamp": str (ISO 8601)
}
```

**Implementation Logic**:

```python
async def get_top_players(limit: int, db: Session):
    cache_key = f"leaderboard:top:{limit}"
    
    # 1. Check cache
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # 2. Query database
    top_players = (
        db.query(Leaderboard)
        .order_by(Leaderboard.total_score.desc())
        .limit(limit)
        .all()
    )
    
    # 3. Get total count
    total_players = db.query(Leaderboard).count()
    
    # 4. Build response
    response = {
        "top_players": [
            {
                "rank": idx + 1,
                "user_id": p.user_id,
                "username": p.username,
                "total_score": p.total_score,
                "session_count": p.session_count
            }
            for idx, p in enumerate(top_players)
        ],
        "total_players": total_players,
        "timestamp": datetime.now().isoformat()
    }
    
    # 5. Cache result
    cache.set(cache_key, response, ttl=30)
    
    return response
```

**SQL Query**:
```sql
-- Executed query (efficient with descending index)
SELECT user_id, username, total_score, session_count
FROM leaderboard
ORDER BY total_score DESC
LIMIT 10;

-- Query plan uses: Index Scan using idx_leaderboard_score_desc
```

**Complexity**:
- Time: O(log n + k) where k is limit (index scan + limit rows)
- Space: O(k)
- With cache: O(1)

### 2.3 Get Player Rank

```python
GET /api/leaderboard/rank/{user_id}

Path Parameters:
- user_id: int (required)

Response (200 OK):
{
    "user_id": int,
    "username": str,
    "rank": int,
    "total_score": int,
    "session_count": int,
    "percentile": float
}

Response (404 Not Found):
{
    "detail": "Player not found in leaderboard"
}
```

**Implementation Logic**:

```python
async def get_player_rank(user_id: int, db: Session):
    cache_key = f"leaderboard:rank:{user_id}"
    
    # 1. Check cache
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # 2. Query with window function
    rank_query = """
        SELECT 
            ranked.user_id,
            ranked.username,
            ranked.rank,
            ranked.total_score,
            ranked.session_count,
            ranked.total_count
        FROM (
            SELECT 
                user_id,
                username,
                total_score,
                session_count,
                RANK() OVER (ORDER BY total_score DESC) as rank,
                COUNT(*) OVER () as total_count
            FROM leaderboard
        ) ranked
        WHERE ranked.user_id = :user_id
    """
    
    result = db.execute(rank_query, {"user_id": user_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(404, "Player not found")
    
    # 3. Calculate percentile
    percentile = ((row.total_count - row.rank) / row.total_count) * 100
    
    # 4. Build response
    response = {
        "user_id": row.user_id,
        "username": row.username,
        "rank": row.rank,
        "total_score": row.total_score,
        "session_count": row.session_count,
        "percentile": round(percentile, 2)
    }
    
    # 5. Cache result
    cache.set(cache_key, response, ttl=60)
    
    return response
```

**SQL Window Function Explanation**:
```sql
-- Window functions allow rank calculation in a single pass
-- RANK() assigns same rank to ties, next rank skips
-- DENSE_RANK() would not skip ranks after ties
-- COUNT(*) OVER () gets total count without additional query

SELECT 
    user_id,
    total_score,
    RANK() OVER (ORDER BY total_score DESC) as rank
FROM leaderboard
WHERE user_id = 123;

-- PostgreSQL optimizes this with index scan
```

**Complexity**:
- Time: O(n log n) for window function (full table scan + sort)
- Space: O(n) for window computation
- With cache: O(1)

**Optimization Note**: For very large leaderboards (>10M rows), consider:
- Approximate rank using sampling
- Maintain rank in leaderboard table (updated on score submission)
- Use range queries instead of window functions

## 3. Caching Strategy

### 3.1 Cache Keys

```python
# Redis key patterns
CACHE_KEY_TOP = "leaderboard:top:{limit}"
CACHE_KEY_RANK = "leaderboard:rank:{user_id}"
CACHE_KEY_SCORE = "leaderboard:score:{user_id}"
```

### 3.2 Cache Operations

```python
class CacheManager:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url)
    
    def get(self, key: str) -> Optional[dict]:
        """Get value from cache."""
        value = self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    def set(self, key: str, value: dict, ttl: int):
        """Set value in cache with TTL."""
        serialized = json.dumps(value)
        self.redis.setex(key, ttl, serialized)
    
    def delete(self, *keys: str):
        """Delete one or more keys."""
        if keys:
            self.redis.delete(*keys)
    
    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
```

### 3.3 Cache Invalidation Logic

```python
def invalidate_caches_on_score_submit(user_id: int):
    """
    Invalidate relevant caches after score submission.
    
    Strategy:
    1. Delete user-specific caches (rank, score)
    2. Delete all top-N caches (could affect rankings)
    3. Use wildcard pattern for efficiency
    """
    # Delete user caches
    cache.delete(
        f"leaderboard:rank:{user_id}",
        f"leaderboard:score:{user_id}"
    )
    
    # Delete all top caches (any limit value)
    cache.delete_pattern("leaderboard:top:*")
```

**Cache Invalidation Trade-offs**:

| Strategy | Pros | Cons |
|----------|------|------|
| Invalidate all on write | Simple, always consistent | Higher cache miss rate |
| Selective invalidation | Better cache hit rate | Complex logic, potential bugs |
| TTL-only (no invalidation) | Simplest | Stale data possible |

**Current choice**: Invalidate all + TTL for balance

### 3.4 Cache Warming

```python
async def warm_cache_on_startup():
    """
    Warm cache with frequently accessed data on application start.
    """
    # Warm top 10, 20, 50, 100 players
    for limit in [10, 20, 50, 100]:
        await get_top_players(limit)
```

## 4. Algorithms

### 4.1 Rank Calculation Algorithm

**Problem**: Given a user_id, find their rank among all players.

**Approach 1**: Window Function (Current Implementation)
```sql
SELECT RANK() OVER (ORDER BY total_score DESC) as rank
FROM leaderboard
WHERE user_id = ?
```

**Time Complexity**: O(n log n)
**Space Complexity**: O(n)

**Approach 2**: Count-Based (Alternative)
```sql
SELECT COUNT(*) + 1 as rank
FROM leaderboard
WHERE total_score > (
    SELECT total_score FROM leaderboard WHERE user_id = ?
)
```

**Time Complexity**: O(n)
**Space Complexity**: O(1)

**Why Window Function?**
- Single query (no subquery)
- Returns additional info (total_count)
- PostgreSQL optimizes window functions well

### 4.2 Score Aggregation Algorithm

**Problem**: Efficiently update total_score when new score is submitted.

**Naive Approach**: Recalculate SUM on every read
```sql
-- Bad: O(m) where m = sessions per user
SELECT user_id, SUM(score) as total_score
FROM game_sessions
GROUP BY user_id
```

**Current Approach**: Maintain aggregate (materialized view pattern)
```sql
-- O(1) update on write
UPDATE leaderboard
SET total_score = total_score + :new_score,
    session_count = session_count + 1
WHERE user_id = :user_id
```

**Trade-off Analysis**:
- Write cost: +O(1) for aggregate update
- Read cost: -O(m) no need to aggregate
- For read-heavy workloads: Optimal

## 5. Concurrency Control

### 5.1 Transaction Isolation

```python
# PostgreSQL transaction with proper isolation
with db.begin():
    # Insert session
    db.add(game_session)
    
    # Update leaderboard with row lock
    db.execute("""
        UPDATE leaderboard
        SET total_score = total_score + :score
        WHERE user_id = :user_id
        FOR UPDATE  -- Row-level lock
    """)
    
    db.commit()
```

**Isolation Levels**:
- `READ COMMITTED` (default): Sufficient for our use case
- `SERIALIZABLE`: Maximum isolation, but lower concurrency

### 5.2 Handling Race Conditions

**Scenario**: Two concurrent score submissions for same user

**Problem**:
```
Time  Thread 1              Thread 2
-------------------------------------------
T1    Read: score = 1000
T2                          Read: score = 1000
T3    Write: score = 1500   
T4                          Write: score = 1800
-------------------------------------------
Result: score = 1800 (wrong! should be 2300)
```

**Solution**: Use UPSERT with atomic increment
```sql
INSERT INTO leaderboard (user_id, total_score, session_count)
VALUES (123, 500, 1)
ON CONFLICT (user_id)
DO UPDATE SET
    total_score = leaderboard.total_score + EXCLUDED.total_score,
    session_count = leaderboard.session_count + 1;
```

This is atomic at the database level, preventing race conditions.

## 6. Performance Optimizations

### 6.1 Database Connection Pooling

```python
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,        # Persistent connections
    max_overflow=40,     # Additional connections when busy
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600    # Recycle connections after 1 hour
)
```

**Benefits**:
- Avoid connection establishment overhead
- Reuse existing connections
- Handle bursts with overflow pool

### 6.2 Batch Operations

**Data Population Script**:
```python
# Insert users in batches of 10,000
for batch in chunks(users, 10000):
    db.execute(
        insert_query,
        [{"username": u.username, "email": u.email} for u in batch]
    )
    db.commit()
```

**Benefits**:
- Reduce transaction overhead
- Better database throughput
- Faster population (5-10 minutes for 1M users)

### 6.3 Index Optimization

```sql
-- B-tree index for range queries
CREATE INDEX idx_leaderboard_score_desc 
ON leaderboard(total_score DESC);

-- Composite index for filtered queries
CREATE INDEX idx_sessions_user_time 
ON game_sessions(user_id, played_at DESC);

-- Partial index for active users only
CREATE INDEX idx_active_leaderboard 
ON leaderboard(total_score DESC) 
WHERE session_count > 0;
```

**Index Selection Guidelines**:
- Index columns used in WHERE, ORDER BY, JOIN
- Consider index size vs. benefit
- Use EXPLAIN ANALYZE to verify usage

## 7. Error Handling

### 7.1 Error Response Format

```python
{
    "detail": str,        # User-friendly message
    "error_code": str,    # Machine-readable code (optional)
    "timestamp": str      # ISO 8601 timestamp
}
```

### 7.2 Exception Hierarchy

```python
# Custom exceptions
class LeaderForgeException(Exception):
    """Base exception for LeaderForge."""
    pass

class UserNotFoundException(LeaderForgeException):
    """User not found in database."""
    pass

class InvalidScoreException(LeaderForgeException):
    """Invalid score value."""
    pass

# Exception handlers
@app.exception_handler(UserNotFoundException)
async def user_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )
```

## 8. Data Validation

### 8.1 Pydantic Schemas

```python
class ScoreSubmission(BaseModel):
    user_id: int = Field(..., gt=0)
    score: int = Field(..., ge=0, le=1000000)
    
    @validator('score')
    def validate_score(cls, v):
        if v < 0:
            raise ValueError('Score must be non-negative')
        if v > 1000000:
            raise ValueError('Score cannot exceed 1,000,000')
        return v
```

**Validation Levels**:
1. **Type validation**: int, str, etc.
2. **Range validation**: gt=0, le=1000000
3. **Custom validation**: @validator decorators
4. **Database constraints**: CHECK constraints

## 9. Testing Strategy

### 9.1 Test Categories

**Unit Tests**:
- Individual functions
- Pydantic schemas
- Utility functions

**Integration Tests**:
- API endpoints
- Database operations
- Cache operations

**Load Tests**:
- Performance under load
- Concurrent requests
- Bottleneck identification

### 9.2 Test Data

```python
# Fixtures for consistent test data
@pytest.fixture
def sample_users():
    return [
        User(id=1, username="user1", email="user1@test.com"),
        User(id=2, username="user2", email="user2@test.com"),
    ]

@pytest.fixture
def sample_leaderboard():
    return [
        Leaderboard(user_id=1, username="user1", 
                   total_score=5000, session_count=10),
        Leaderboard(user_id=2, username="user2", 
                   total_score=3000, session_count=5),
    ]
```

## 10. Monitoring Metrics

### 10.1 Custom Instrumentation

```python
import newrelic.agent

@newrelic.agent.function_trace()
def calculate_rank(user_id: int, db: Session) -> int:
    """Calculate player rank with custom tracing."""
    # Track execution time in New Relic
    ...

# Custom metrics
newrelic.agent.record_custom_metric('Cache/HitRate', hit_rate)
newrelic.agent.record_custom_metric('Leaderboard/Size', total_players)
```

### 10.2 Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API Latency (p95) | < 50ms | > 100ms |
| Cache Hit Rate | > 80% | < 70% |
| Database Connections | < 50 | > 80 |
| Error Rate | < 0.1% | > 1% |
| Throughput | > 1000 req/s | < 500 req/s |

## 11. Conclusion

This low-level design provides a comprehensive blueprint for implementing LeaderForge. The design emphasizes:
- Performance through caching and indexing
- Consistency through transactions and atomic operations
- Scalability through efficient algorithms and data structures
- Maintainability through clear code organization and error handling
