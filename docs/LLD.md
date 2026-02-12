# Low-Level Design (LLD) - LeaderForge Gaming Leaderboard System

## 1. Introduction

This document provides detailed low-level design specifications for the LeaderForge gaming leaderboard system, including database schemas, API specifications, algorithms, and implementation details.

## 2. Database Design

### 2.1 Entity Relationship Diagram

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│    Users    │         │ Game Sessions│         │ Leaderboard  │
├─────────────┤         ├──────────────┤         ├──────────────┤
│ id (PK)     │◄──┐     │ id (PK)      │         │ user_id (PK) │
│ username    │   │     │ user_id (FK) │────────►│ username     │
│ email       │   │     │ score        │         │ total_score  │
│ created_at  │   │     │ game_mode    │         │ session_count│
└─────────────┘   │     │ played_at    │         │ last_updated │
                  │     └──────────────┘         └──────────────┘
                  │            │
                  └────────────┘
```

### 2.2 Database Schema

#### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_id ON users(id);
```

**Fields:**
- `id`: Primary key, auto-incrementing
- `username`: Unique username, indexed for lookups
- `email`: Unique email address
- `created_at`: Timestamp of user creation

#### Game Sessions Table
```sql
CREATE TABLE game_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    game_mode VARCHAR(50) NOT NULL DEFAULT 'solo',
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes
CREATE INDEX idx_game_sessions_user_id ON game_sessions(user_id);
CREATE INDEX idx_game_sessions_score ON game_sessions(score);
CREATE INDEX idx_game_sessions_played_at ON game_sessions(played_at);
CREATE INDEX idx_game_sessions_user_score ON game_sessions(user_id, score DESC);
CREATE INDEX idx_game_sessions_mode_score ON game_sessions(game_mode, score DESC);
```

**Fields:**
- `id`: Primary key, auto-incrementing
- `user_id`: Foreign key to users table
- `score`: Game score (0 to 1,000,000)
- `game_mode`: 'solo' or 'team'
- `played_at`: Timestamp of game session

**Indexes:**
- User ID index for user-specific queries
- Score index for ranking queries
- Composite indexes for common query patterns

#### Leaderboard Table
```sql
CREATE TABLE leaderboard (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    username VARCHAR(50) NOT NULL,
    total_score BIGINT NOT NULL,
    session_count INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_leaderboard_total_score ON leaderboard(total_score);
CREATE INDEX idx_leaderboard_total_score_desc ON leaderboard(total_score DESC);
```

**Fields:**
- `user_id`: Primary key, foreign key to users
- `username`: Cached username for performance
- `total_score`: Aggregated total score
- `session_count`: Number of games played
- `last_updated`: Last update timestamp

**Indexes:**
- Descending index on total_score for efficient top-N queries

### 2.3 Database Queries

#### Score Submission Query
```sql
-- Atomic upsert operation
INSERT INTO leaderboard (user_id, username, total_score, session_count, last_updated)
VALUES (:user_id, :username, :score, 1, NOW())
ON CONFLICT (user_id)
DO UPDATE SET
    total_score = leaderboard.total_score + :score,
    session_count = leaderboard.session_count + 1,
    last_updated = NOW()
RETURNING total_score, session_count;
```

**Purpose**: Atomically update leaderboard on score submission  
**Performance**: O(1) with index on user_id

#### Top Players Query
```sql
SELECT user_id, username, total_score, session_count
FROM leaderboard
ORDER BY total_score DESC
LIMIT :limit;
```

**Purpose**: Retrieve top N players  
**Performance**: O(N log N) with index on total_score DESC, optimized to O(N) with limit

#### Player Rank Query
```sql
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
WHERE ranked.user_id = :user_id;
```

**Purpose**: Calculate player rank using window function  
**Performance**: O(N log N) for window function, O(1) for user lookup

## 3. API Design

### 3.1 API Endpoints

#### POST /api/leaderboard/submit
**Purpose**: Submit a new game score

**Request:**
```json
{
    "user_id": 123,
    "score": 500,
    "game_mode": "solo"
}
```

**Response:**
```json
{
    "success": true,
    "user_id": 123,
    "new_total_score": 5000,
    "current_rank": 42,
    "message": "Score submitted successfully. Current rank: 42"
}
```

**Algorithm:**
1. Validate user exists
2. Begin database transaction
3. Insert game session record
4. Upsert leaderboard entry (atomic)
5. Commit transaction
6. Invalidate cache entries
7. Calculate and return new rank

**Time Complexity**: O(1) for insert, O(log N) for rank calculation  
**Space Complexity**: O(1)

#### GET /api/leaderboard/top
**Purpose**: Retrieve top N players

**Query Parameters:**
- `limit` (optional): Number of players (default: 10, max: 100)

**Response:**
```json
{
    "top_players": [
        {
            "rank": 1,
            "user_id": 456,
            "username": "player1",
            "total_score": 100000,
            "session_count": 50
        }
    ],
    "total_players": 1000000,
    "timestamp": "2026-02-12T10:30:00"
}
```

**Algorithm:**
1. Check Redis cache
2. If cache hit, return cached data
3. If cache miss:
   - Query database with ORDER BY and LIMIT
   - Cache result with TTL
   - Return data

**Time Complexity**: O(1) cache hit, O(N log N) cache miss  
**Space Complexity**: O(N) for result set

#### GET /api/leaderboard/rank/{user_id}
**Purpose**: Get player rank and statistics

**Path Parameters:**
- `user_id`: User ID to look up

**Response:**
```json
{
    "user_id": 123,
    "username": "player123",
    "rank": 42,
    "total_score": 5000,
    "session_count": 10,
    "percentile": 95.8
}
```

**Algorithm:**
1. Check Redis cache
2. If cache hit, return cached data
3. If cache miss:
   - Query database with window function
   - Calculate percentile: (total_count - rank) / total_count * 100
   - Cache result with TTL
   - Return data

**Time Complexity**: O(1) cache hit, O(N log N) cache miss  
**Space Complexity**: O(1)

### 3.2 API Error Handling

#### Error Response Format
```json
{
    "error": "Error Type",
    "detail": "Detailed error message",
    "status_code": 404
}
```

#### Error Codes
- `400`: Bad Request - Invalid input
- `404`: Not Found - User/player not found
- `422`: Unprocessable Entity - Validation error
- `429`: Too Many Requests - Rate limit exceeded
- `500`: Internal Server Error - Server error

## 4. Caching Strategy

### 4.1 Cache Keys

```
leaderboard:top:{limit}          # Top N players cache
leaderboard:rank:{user_id}        # Player rank cache
leaderboard:score:{user_id}       # Player score cache (future)
```

### 4.2 Cache TTL

- Top Players: 30 seconds
- Player Rank: 60 seconds

### 4.3 Cache Invalidation

**On Score Submission:**
1. Invalidate `leaderboard:rank:{user_id}`
2. Invalidate `leaderboard:top:*` (pattern match)
3. Invalidate `leaderboard:score:{user_id}`

**Strategy**: Write-through with immediate invalidation

### 4.4 Cache Algorithm

```python
def get_top_players(limit):
    cache_key = f"leaderboard:top:{limit}"
    
    # Try cache
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Cache miss - query database
    result = query_database(limit)
    
    # Store in cache
    redis.setex(cache_key, ttl=30, value=json.dumps(result))
    
    return result
```

## 5. Concurrency & Consistency

### 5.1 Transaction Management

**Score Submission Transaction:**
```python
try:
    db.begin()
    # Insert game session
    db.add(game_session)
    # Upsert leaderboard (atomic)
    db.execute(upsert_query)
    db.commit()
except:
    db.rollback()
    raise
```

**Isolation Level**: READ COMMITTED (PostgreSQL default)

### 5.2 Race Condition Prevention

**Problem**: Concurrent score submissions for same user

**Solution**: 
- Database-level atomic upsert with `ON CONFLICT`
- Transaction isolation
- Row-level locking implicit in PostgreSQL

**Example:**
```sql
-- This operation is atomic
INSERT INTO leaderboard ...
ON CONFLICT (user_id) DO UPDATE ...
```

### 5.3 Cache Consistency

**Strategy**: Cache invalidation on writes

**Trade-offs**:
- Pros: Simple, ensures consistency
- Cons: Cache misses after writes

**Alternative Considered**: Write-through caching
- Rejected due to complexity and potential for stale data

## 6. Performance Optimizations

### 6.1 Database Optimizations

#### Indexes
- Primary keys: Automatic indexes
- Foreign keys: Indexed for joins
- `total_score DESC`: Optimized for top-N queries
- Composite indexes: For common query patterns

#### Query Optimization
- Use window functions instead of subqueries
- Limit result sets early
- Use prepared statements
- Connection pooling (20 connections)

### 6.2 Caching Optimizations

#### Cache Hit Ratio Target
- Top Players: > 80% hit rate
- Player Rank: > 70% hit rate

#### Cache Warming
- Not implemented (future enhancement)
- Could pre-populate cache for top 100 players

### 6.3 Application Optimizations

#### Async I/O
- FastAPI async endpoints
- Non-blocking database operations
- Concurrent request handling

#### Connection Pooling
- Database: 20 connections, 40 max overflow
- Redis: Connection pool with 50 max connections

## 7. Monitoring Implementation

### 7.1 Custom Metrics

```python
# Score submission metric
record_custom_metric("Leaderboard/ScoreSubmitted", score_value)

# Cache metrics
record_custom_metric("Leaderboard/CacheHit", 1)
record_custom_metric("Leaderboard/CacheMiss", 1)

# Performance metrics
record_custom_metric("Leaderboard/Latency", latency_ms)
```

### 7.2 Custom Events

```python
record_custom_event("ScoreSubmission", {
    "user_id": user_id,
    "score": score,
    "game_mode": game_mode,
    "total_score": total_score
})
```

### 7.3 Database Tracing

```python
with DatabaseTrace("get_top_players"):
    result = db.query(Leaderboard).all()
```

## 8. Security Implementation

### 8.1 Rate Limiting

**Algorithm**: Sliding window rate limiting

```python
class RateLimitMiddleware:
    def __init__(self, requests_per_minute=1000):
        self.limit = requests_per_minute
        self.requests = defaultdict(list)  # IP -> timestamps
    
    def check_rate_limit(self, ip, current_time):
        # Remove old requests (> 1 minute)
        one_minute_ago = current_time - 60
        self.requests[ip] = [
            ts for ts in self.requests[ip] 
            if ts > one_minute_ago
        ]
        
        # Check limit
        if len(self.requests[ip]) >= self.limit:
            return False
        
        # Record request
        self.requests[ip].append(current_time)
        return True
```

**Time Complexity**: O(N) where N is requests in window  
**Space Complexity**: O(N) for request tracking

### 8.2 Input Validation

**Score Validation:**
```python
class ScoreSubmission(BaseModel):
    user_id: int = Field(..., gt=0)
    score: int = Field(..., ge=0, le=1000000)
    game_mode: Optional[str] = Field(default="solo")
    
    @validator('game_mode')
    def validate_game_mode(cls, v):
        if v not in ['solo', 'team']:
            raise ValueError("game_mode must be 'solo' or 'team'")
        return v
```

### 8.3 SQL Injection Prevention

**Method**: Parameterized queries

```python
# Safe - uses parameterized query
db.execute(
    text("SELECT * FROM users WHERE id = :user_id"),
    {"user_id": user_id}
)

# Never do this:
# db.execute(f"SELECT * FROM users WHERE id = {user_id}")  # UNSAFE
```

## 9. Testing Strategy

### 9.1 Unit Tests

**Coverage Areas:**
- API endpoint logic
- Validation functions
- Cache operations
- Error handling

### 9.2 Integration Tests

**Coverage Areas:**
- End-to-end API flows
- Database transactions
- Cache integration
- Concurrent operations

### 9.3 Load Tests

**Tools**: Custom load simulator script

**Metrics Tracked:**
- Request latency (p50, p95, p99)
- Throughput (requests/second)
- Error rate
- Cache hit ratio

## 10. Deployment Details

### 10.1 Container Configuration

**Backend Container:**
- Base: Python 3.11-slim
- Port: 8000
- Health check: `/api/leaderboard/health`

**Frontend Container:**
- Base: Node 20-alpine
- Port: 3000
- Build: Vite dev server

**Database Container:**
- Base: PostgreSQL 15-alpine
- Port: 5432
- Volume: `postgres_data` (persistent)

**Redis Container:**
- Base: Redis 7-alpine
- Port: 6379
- No persistence (cache only)

### 10.2 Environment Variables

```bash
# Backend
DATABASE_URL=postgresql://admin:password@postgres:5432/leaderboard
REDIS_URL=redis://redis:6379
NEW_RELIC_LICENSE_KEY=your_key_here
API_HOST=0.0.0.0
API_PORT=8000

# Frontend
VITE_API_URL=http://localhost:8000
```

## 11. Error Handling Details

### 11.1 Exception Hierarchy

```
Exception
├── HTTPException (FastAPI)
│   ├── 400 BadRequest
│   ├── 404 NotFound
│   ├── 422 ValidationError
│   └── 500 InternalServerError
└── DatabaseException
    ├── ConnectionError
    └── TransactionError
```

### 11.2 Error Recovery

**Database Errors:**
- Automatic retry for transient errors
- Transaction rollback on failure
- Logging for debugging

**Cache Errors:**
- Graceful degradation (continue without cache)
- Log warning, don't fail request

## 12. Future Enhancements

### 12.1 Planned Improvements

1. **WebSocket Support**
   - Real-time leaderboard updates
   - Push notifications for rank changes

2. **GraphQL API**
   - Flexible querying
   - Reduced over-fetching

3. **Message Queue**
   - Async score processing
   - Event-driven architecture

4. **Database Sharding**
   - Horizontal scaling
   - User-based sharding

### 12.2 Performance Targets

- Score Submission: < 30ms p95 (current: ~50ms)
- Top Players: < 5ms p95 cache hit (current: ~10ms)
- Player Rank: < 30ms p95 (current: ~50ms)
- Throughput: 2000+ req/s (current: 1000+ req/s)

---

**Document Version**: 1.0  
**Last Updated**: February 2026  
**Author**: LeaderForge Development Team
