# High-Level Design (HLD) - LeaderForge

## 1. System Overview

LeaderForge is a high-performance gaming leaderboard system designed to handle millions of users and game sessions with real-time ranking updates. The system provides three core functionalities:

1. Submit game scores
2. Retrieve top N players
3. Get individual player rankings

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Client Layer                        │
│  ┌──────────────────┐        ┌──────────────────┐         │
│  │   Web Browser    │        │  Mobile/Desktop  │         │
│  │   (React App)    │        │     Clients      │         │
│  └─────────┬────────┘        └─────────┬────────┘         │
└────────────┼───────────────────────────┼──────────────────┘
             │                           │
             └──────────┬────────────────┘
                        │ HTTPS/REST API
         ┌──────────────▼──────────────┐
         │      Load Balancer          │
         │  (Nginx/AWS ALB - Future)   │
         └──────────────┬──────────────┘
                        │
         ┌──────────────▼──────────────┐
         │      Application Layer      │
         │   ┌──────────────────────┐  │
         │   │   FastAPI Backend    │  │
         │   │  (Async Workers)     │  │
         │   └──────────┬───────────┘  │
         └──────────────┼──────────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
   ┌────────▼─────────┐   ┌────────▼─────────┐
   │   Cache Layer    │   │   Data Layer     │
   │  ┌────────────┐  │   │  ┌────────────┐  │
   │  │   Redis    │  │   │  │ PostgreSQL │  │
   │  │  (Cache)   │  │   │  │  (Primary) │  │
   │  └────────────┘  │   │  └────────────┘  │
   └──────────────────┘   └──────────────────┘
            │                       │
            └───────────┬───────────┘
                        │
         ┌──────────────▼──────────────┐
         │   Monitoring & Logging      │
         │  ┌──────────────────────┐   │
         │  │     New Relic APM    │   │
         │  │  Application Insights│   │
         │  └──────────────────────┘   │
         └─────────────────────────────┘
```

## 3. Component Description

### 3.1 Frontend (React Application)

**Purpose**: Provides user interface for viewing leaderboards and looking up player rankings.

**Key Features**:
- Real-time leaderboard updates (5-second polling)
- Player rank search functionality
- Responsive design for mobile and desktop
- Visual indicators for rank changes

**Technology**:
- React 18 with hooks
- TanStack Query for data fetching
- Tailwind CSS for styling
- Vite for build tooling

### 3.2 Backend (FastAPI Application)

**Purpose**: Core API server handling all business logic and data operations.

**Key Features**:
- RESTful API endpoints
- Async request handling
- Input validation with Pydantic
- Connection pooling
- Cache management
- Transaction handling

**Technology**:
- FastAPI framework
- SQLAlchemy ORM
- Async/await for I/O operations
- Uvicorn ASGI server

### 3.3 Database (PostgreSQL)

**Purpose**: Persistent storage for users, game sessions, and leaderboard data.

**Schema Design**:

```
┌─────────────────┐
│     Users       │
├─────────────────┤
│ id (PK)         │
│ username        │
│ email           │
│ created_at      │
└────────┬────────┘
         │ 1
         │
         │ N
┌────────▼────────┐
│  Game Sessions  │
├─────────────────┤
│ id (PK)         │
│ user_id (FK)    │
│ score           │
│ played_at       │
└────────┬────────┘
         │
         │ (Aggregation)
         │
┌────────▼────────┐
│  Leaderboard    │
├─────────────────┤
│ user_id (PK)    │
│ username        │
│ total_score     │
│ session_count   │
│ last_updated    │
└─────────────────┘
```

**Indexes**:
- `users.username` (B-tree)
- `game_sessions.user_id` (B-tree)
- `leaderboard.total_score DESC` (B-tree)

**Why PostgreSQL?**
- ACID compliance for data consistency
- Excellent performance for complex queries
- Window functions for efficient rank calculation
- Mature ecosystem and tooling

### 3.4 Cache Layer (Redis)

**Purpose**: High-speed caching to reduce database load and improve response times.

**Cache Strategy**:
- Write-through cache for leaderboard data
- Invalidation on score updates
- TTL-based expiration (30-60 seconds)

**Cached Data**:
- Top N players (TTL: 30s)
- Individual player ranks (TTL: 60s)
- Player total scores (TTL: 60s)

**Why Redis?**
- Sub-millisecond latency
- Simple key-value model
- Built-in TTL support
- Atomic operations for consistency

### 3.5 Monitoring (New Relic)

**Purpose**: Application performance monitoring and bottleneck identification.

**Metrics Tracked**:
- API endpoint latency (p50, p95, p99)
- Database query performance
- Cache hit ratio
- Error rates
- Throughput (requests/second)

## 4. Data Flow Diagrams

### 4.1 Submit Score Flow

```
┌──────┐     ┌─────────┐     ┌──────────┐     ┌───────┐
│Client│     │ FastAPI │     │PostgreSQL│     │ Redis │
└───┬──┘     └────┬────┘     └────┬─────┘     └───┬───┘
    │             │               │               │
    │ POST score  │               │               │
    ├────────────>│               │               │
    │             │ Begin TX      │               │
    │             ├──────────────>│               │
    │             │ Insert session│               │
    │             ├──────────────>│               │
    │             │ Upsert leaderboard            │
    │             ├──────────────>│               │
    │             │ Commit TX     │               │
    │             ├──────────────>│               │
    │             │ Invalidate cache              │
    │             ├──────────────────────────────>│
    │             │ Get new rank  │               │
    │             ├──────────────>│               │
    │             │               │               │
    │ Response    │               │               │
    │<────────────┤               │               │
    │             │               │               │
```

### 4.2 Get Top Players Flow (With Caching)

```
┌──────┐     ┌─────────┐     ┌───────┐     ┌──────────┐
│Client│     │ FastAPI │     │ Redis │     │PostgreSQL│
└───┬──┘     └────┬────┘     └───┬───┘     └────┬─────┘
    │             │               │              │
    │ GET top 10  │               │              │
    ├────────────>│               │              │
    │             │ Check cache   │              │
    │             ├──────────────>│              │
    │             │ Cache HIT     │              │
    │             │<──────────────┤              │
    │ Response    │               │              │
    │<────────────┤               │              │
    │             │               │              │
    
    (On Cache Miss)
    
    │ GET top 10  │               │              │
    ├────────────>│               │              │
    │             │ Check cache   │              │
    │             ├──────────────>│              │
    │             │ Cache MISS    │              │
    │             │<──────────────┤              │
    │             │ Query DB      │              │
    │             ├─────────────────────────────>│
    │             │ Results       │              │
    │             │<─────────────────────────────┤
    │             │ Store in cache│              │
    │             ├──────────────>│              │
    │ Response    │               │              │
    │<────────────┤               │              │
```

### 4.3 Get Player Rank Flow

```
┌──────┐     ┌─────────┐     ┌───────┐     ┌──────────┐
│Client│     │ FastAPI │     │ Redis │     │PostgreSQL│
└───┬──┘     └────┬────┘     └───┬───┘     └────┬─────┘
    │             │               │              │
    │GET rank/123 │               │              │
    ├────────────>│               │              │
    │             │ Check cache   │              │
    │             ├──────────────>│              │
    │             │ Cache MISS    │              │
    │             │<──────────────┤              │
    │             │ Window function query        │
    │             ├─────────────────────────────>│
    │             │ Rank + stats  │              │
    │             │<─────────────────────────────┤
    │             │ Cache result  │              │
    │             ├──────────────>│              │
    │ Response    │               │              │
    │<────────────┤               │              │
```

## 5. Scalability Considerations

### 5.1 Current Scale
- 1M users
- 5M game sessions
- ~100K active leaderboard entries
- 100-1000 requests/second

### 5.2 Horizontal Scaling Strategies

**Application Layer**:
- Run multiple FastAPI instances behind a load balancer
- Stateless design allows easy horizontal scaling
- Use container orchestration (Kubernetes, ECS)

**Database Layer**:
- Read replicas for query load distribution
- Partition leaderboard by region/game type
- Use connection pooling effectively

**Cache Layer**:
- Redis Cluster for distributed caching
- Redis Sentinel for high availability
- Cache warming on deployment

### 5.3 Vertical Scaling Options

**Database**:
- Increase CPU/RAM for better query performance
- Use larger connection pool sizes
- Optimize shared buffers and work memory

**Cache**:
- Increase Redis memory for more cached data
- Use Redis persistence for faster restarts

## 6. Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Submit Score (p95) | < 50ms | ~30ms |
| Get Top Players (p95, cached) | < 10ms | ~5ms |
| Get Top Players (p95, uncached) | < 100ms | ~70ms |
| Get Player Rank (p95) | < 50ms | ~35ms |
| Throughput | > 1000 req/s | ~800 req/s |
| Cache Hit Ratio | > 80% | ~85% |
| Database Connections | < 50 | ~25 |

## 7. Security Considerations

### 7.1 Current Implementation
- Input validation with Pydantic
- SQL injection prevention (parameterized queries)
- CORS configuration
- Environment variable for secrets

### 7.2 Future Enhancements
- API authentication (JWT tokens)
- Rate limiting per user/IP
- DDoS protection
- Encryption at rest and in transit
- Audit logging

## 8. Disaster Recovery

### 8.1 Backup Strategy
- Daily PostgreSQL backups
- Point-in-time recovery (PITR)
- Backup retention: 30 days

### 8.2 High Availability
- Database replication (master-slave)
- Redis Sentinel for automatic failover
- Multi-AZ deployment in production

### 8.3 Recovery Time Objectives
- RTO (Recovery Time Objective): < 1 hour
- RPO (Recovery Point Objective): < 15 minutes

## 9. Technology Stack Rationale

| Technology | Reason for Selection |
|------------|---------------------|
| FastAPI | High performance, async support, automatic API docs |
| PostgreSQL | ACID compliance, window functions, mature ecosystem |
| Redis | Sub-ms latency, simple operations, TTL support |
| React | Component-based, large ecosystem, performance |
| Docker | Consistent environments, easy deployment |
| New Relic | Comprehensive APM, easy integration |

## 10. Future Enhancements

### Phase 2
- WebSocket support for real-time updates
- Player profiles and statistics
- Multiple leaderboard types (daily, weekly, monthly)
- Friend leaderboards

### Phase 3
- Global and regional leaderboards
- Tournament system
- Achievement system
- Social features (chat, teams)

### Phase 4
- Machine learning for fraud detection
- Predictive analytics
- Personalized recommendations
- Mobile applications (iOS, Android)

## 11. Deployment Architecture

### Development
```
Docker Compose (local)
- All services on single machine
- SQLite for fast testing
- Hot reload enabled
```

### Staging
```
Container Orchestration (ECS/K8s)
- Application: 2 instances
- PostgreSQL: Single instance with backups
- Redis: Single instance
- Load balancer
```

### Production
```
Kubernetes Cluster
- Application: 5+ instances (auto-scaling)
- PostgreSQL: Master + 2 read replicas
- Redis Cluster: 3 nodes
- Multi-AZ deployment
- CDN for frontend assets
- DDoS protection
```

## 12. Cost Estimation

### Monthly AWS Costs (Production)

| Service | Configuration | Est. Cost |
|---------|--------------|-----------|
| EC2 (Application) | 3x t3.medium | $90 |
| RDS PostgreSQL | db.t3.large | $120 |
| ElastiCache Redis | cache.t3.medium | $40 |
| Load Balancer | ALB | $25 |
| Data Transfer | ~1TB | $90 |
| **Total** | | **~$365/month** |

## 13. Conclusion

LeaderForge is designed as a scalable, high-performance leaderboard system that can handle millions of users with sub-50ms latency. The architecture leverages modern technologies and best practices to deliver a robust, maintainable solution that can scale horizontally as demand grows.
