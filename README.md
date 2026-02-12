# LeaderForge - High-Performance Gaming Leaderboard System

A scalable, real-time gaming leaderboard system built with FastAPI, React, PostgreSQL, and Redis. Designed to handle millions of users and game sessions with sub-50ms API response times.

## Features

- **High Performance**: Sub-50ms p95 latency for score submissions
- **Real-time Updates**: Live leaderboard with 5-second refresh intervals
- **Scalable Architecture**: Handles 1M+ users and 5M+ game sessions
- **Intelligent Caching**: Redis-based caching with smart invalidation
- **Modern UI**: Beautiful React frontend with real-time updates
- **Comprehensive Monitoring**: New Relic APM integration
- **Security**: Rate limiting, security headers, input validation
- **Professional Logging**: Structured logging with file and console output
- **API Documentation**: Comprehensive Swagger/OpenAPI documentation

## Tech Stack

### Backend
- **FastAPI**: High-performance async Python web framework
- **PostgreSQL**: Robust relational database with optimized indexes
- **Redis**: In-memory caching for sub-10ms response times
- **SQLAlchemy**: ORM with connection pooling
- **New Relic**: Application performance monitoring
- **Python 3.11**: Modern Python with async/await support

### Frontend
- **React 18**: Modern UI with hooks
- **TanStack Query**: Efficient data fetching and caching
- **Tailwind CSS**: Utility-first styling
- **Vite**: Fast build tool and dev server
- **Axios**: HTTP client for API requests

### Infrastructure
- **Docker**: Containerized deployment
- **Docker Compose**: Multi-container orchestration

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)

### Run with Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd LeaderForge
```

2. Create environment file (optional):
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

3. Start all services:
```bash
docker-compose up -d
```

4. Wait for services to be healthy (check with `docker-compose ps`)

5. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- API Docs (ReDoc): http://localhost:8000/redoc

### Populate Database

Run the data population script to generate 1M users and 5M game sessions:

```bash
# From host machine
docker-compose exec backend python scripts/populate_data.py

# Or run locally
cd backend
python scripts/populate_data.py
```

This will take approximately 5-10 minutes depending on your machine.

## API Endpoints

All endpoints follow the `/api/leaderboard/*` pattern as per requirements.

### Submit Score
```http
POST /api/leaderboard/submit
Content-Type: application/json

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

### Get Top Players
```http
GET /api/leaderboard/top?limit=10
```

**Query Parameters:**
- `limit` (optional): Number of top players to retrieve (1-100, default: 10)

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

### Get Player Rank
```http
GET /api/leaderboard/rank/{user_id}
```

**Path Parameters:**
- `user_id`: The ID of the user to look up

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

### Health Check
```http
GET /api/leaderboard/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "ok",
  "cache": "ok",
  "timestamp": "2026-02-12T10:30:00"
}
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

The Swagger documentation includes:
- Detailed endpoint descriptions
- Request/response examples
- Error response examples
- Performance notes
- Rate limiting information

## Performance Testing

### Load Simulation

Run the load simulator to test performance under load:

```bash
# From Docker
docker-compose exec backend python scripts/load_simulator.py

# Or locally
cd backend
python scripts/load_simulator.py <base_url> <concurrent_users> <duration_seconds>

# Example: 100 concurrent users for 60 seconds
python scripts/load_simulator.py http://localhost:8000 100 60
```

### Performance Targets
- **Submit Score API**: < 50ms p95
- **Top Players API**: < 10ms p95 (cached), < 100ms (uncached)
- **Player Rank API**: < 50ms p95
- **Throughput**: 1000+ requests/second
- **Cache Hit Ratio**: > 80%

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  ┌──────────────┐              ┌──────────────┐            │
│  │   Web UI     │              │  Mobile App   │            │
│  │  (React)    │              │  (Future)     │            │
│  └──────┬───────┘              └──────┬───────┘            │
└─────────┼──────────────────────────────┼─────────────────────┘
          │                              │
          │         HTTP/REST API        │
          │                              │
┌─────────▼──────────────────────────────▼─────────────────────┐
│                    API Gateway Layer                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              FastAPI Backend Service                 │   │
│  │  • Rate Limiting                                     │   │
│  │  • Security Headers                                  │   │
│  │  • Request Validation                                │   │
│  │  • Error Handling                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────┬───────────────────────────────────────────────────┘
          │
          │
┌─────────▼───────────────────────────────────────────────────┐
│                  Application Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   API       │  │   Cache      │  │  Monitoring  │      │
│  │  Endpoints  │  │   Manager    │  │   (New Relic)│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────┬───────────────────────────────────────────────────┘
          │
          │
┌─────────▼───────────────────────────────────────────────────┐
│                    Data Layer                                 │
│  ┌──────────────┐              ┌──────────────┐            │
│  │  PostgreSQL  │              │    Redis     │            │
│  │  Database    │              │    Cache     │            │
│  │              │              │              │            │
│  │ • Users      │              │ • Top Players│            │
│  │ • Sessions   │              │ • Player Rank│            │
│  │ • Leaderboard│              │ • Metadata   │            │
│  └──────────────┘              └──────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

## Database Schema

### Users Table
- `id`: Primary key (SERIAL)
- `username`: Unique username (VARCHAR(50))
- `email`: Unique email (VARCHAR(100))
- `created_at`: Registration timestamp (TIMESTAMP)

### Game Sessions Table
- `id`: Primary key (SERIAL)
- `user_id`: Foreign key to users (INTEGER)
- `score`: Game score (INTEGER, 0 to 1,000,000)
- `game_mode`: Game mode - 'solo' or 'team' (VARCHAR(50))
- `played_at`: Session timestamp (TIMESTAMP)

**Indexes:**
- Index on `user_id` for user-specific queries
- Index on `score` for ranking queries
- Index on `game_mode` for mode-based analytics
- Composite indexes for common query patterns

### Leaderboard Table
- `user_id`: Primary key (INTEGER)
- `username`: Cached username (VARCHAR(50))
- `total_score`: Aggregated score (BIGINT)
- `session_count`: Total games played (INTEGER)
- `last_updated`: Last update timestamp (TIMESTAMP)

**Indexes:**
- Descending index on `total_score` for fast top-N queries

## Security Features

### Rate Limiting
- **Limit**: 1000 requests per minute per IP address
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- **Response**: 429 Too Many Requests when limit exceeded

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Input Validation
- Score validation (0 to 1,000,000)
- User ID validation (positive integers)
- Game mode validation ('solo' or 'team')
- SQL injection prevention via parameterized queries

## Caching Strategy

### Cache Keys
- `leaderboard:top:{limit}`: Top N players (TTL: 30s)
- `leaderboard:rank:{user_id}`: Player rank (TTL: 60s)
- `leaderboard:score:{user_id}`: Player total score (TTL: 60s)

### Cache Invalidation
- On score submission: Invalidate affected user's cache and top-N cache
- Pattern-based invalidation for top players cache
- Uses Redis atomic operations for consistency
- Graceful degradation when Redis is unavailable

## Logging

The application uses Python's `logging` module with:
- **Console Output**: Structured log messages to stdout
- **File Logging**: Logs written to `leaderforge.log`
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Structured Format**: Timestamp, logger name, level, message
- **Exception Logging**: Full stack traces for errors

View logs:
```bash
# Backend logs
docker-compose logs backend -f

# Or view log file
tail -f backend/leaderforge.log
```

## Development

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Set API URL (optional, defaults to relative URLs)
export VITE_API_URL=http://localhost:8000

# Run development server
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v

# Run specific test file
pytest tests/test_api.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Optimization Techniques

1. **Database Optimizations**
   - B-tree indexes on frequently queried columns
   - Descending index on `total_score` for fast top-N queries
   - Connection pooling (20 connections, 40 max overflow)
   - Materialized leaderboard table to avoid expensive aggregations
   - SQL window functions for efficient rank calculation

2. **Caching Optimizations**
   - Redis caching for hot data
   - Short TTLs (30-60s) to balance freshness and performance
   - Intelligent cache invalidation on writes
   - Graceful degradation when cache unavailable

3. **Application Optimizations**
   - Async endpoints for I/O operations
   - Prepared statements for common queries
   - Batch inserts for data population
   - Atomic database operations (UPSERT with ON CONFLICT)

4. **Concurrency Handling**
   - Database transactions for consistency
   - Upsert operations with ON CONFLICT
   - Row-level locking for leaderboard updates
   - Connection pooling for concurrent requests

## Monitoring with New Relic

1. Sign up for New Relic account: https://newrelic.com

2. Get your license key from Account Settings

3. Set environment variable:
```bash
export NEW_RELIC_LICENSE_KEY=your_license_key_here
```

Or add to `backend/.env`:
```
NEW_RELIC_LICENSE_KEY=your_license_key_here
```

4. Restart the backend service:
```bash
docker-compose restart backend
```

5. View metrics in New Relic dashboard

## Project Structure

```
LeaderForge/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── leaderboard.py    # API endpoints
│   │   ├── models.py             # Database models
│   │   ├── schemas.py            # Pydantic schemas
│   │   ├── database.py           # DB connection
│   │   ├── cache.py              # Redis operations
│   │   ├── config.py             # Configuration
│   │   ├── middleware.py        # Rate limiting & security
│   │   └── main.py               # FastAPI app
│   ├── scripts/
│   │   ├── populate_data.py      # Data generation
│   │   └── load_simulator.py     # Load testing
│   ├── tests/
│   │   └── test_api.py           # Unit tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Leaderboard.jsx   # Top 10 display
│   │   │   └── PlayerRank.jsx    # Rank lookup
│   │   ├── api/
│   │   │   └── client.js         # API client
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── HLD.md                    # High-level design
│   ├── LLD.md                    # Low-level design
│   └── PERFORMANCE.md            # Performance report
├── docker-compose.yml
└── README.md
```

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres

# Restart service
docker-compose restart postgres

# Connect to database
docker-compose exec postgres psql -U admin -d leaderboard
```

### Redis Connection Issues
```bash
# Check if Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# View logs
docker-compose logs redis

# Check Redis info
docker-compose exec redis redis-cli INFO
```

### Backend Issues
```bash
# View backend logs
docker-compose logs backend -f

# View recent logs
docker-compose logs backend --tail 100

# Restart backend
docker-compose restart backend

# Check health
curl http://localhost:8000/api/leaderboard/health

# Rebuild backend
docker-compose build backend
docker-compose up -d backend
```

### CORS Issues
If you encounter CORS errors:
1. Check that frontend is using relative URLs in Docker (via Vite proxy)
2. For local development, set `VITE_API_URL=http://localhost:8000`
3. Verify CORS origins in `backend/app/config.py`
4. Check browser console for specific CORS error messages

### Rebuild Without Database Reset
```bash
# Rebuild backend and frontend (database preserved)
docker-compose build backend frontend
docker-compose up -d backend frontend
```

## Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql://admin:password@postgres:5432/leaderboard
REDIS_URL=redis://redis:6379
NEW_RELIC_LICENSE_KEY=your_key_here
API_HOST=0.0.0.0
API_PORT=8000
```

### Frontend (.env)
```bash
VITE_API_URL=http://localhost:8000  # Optional, uses relative URLs if not set
```

## API Rate Limits

- **Default**: 1000 requests per minute per IP address
- **Headers**: Check `X-RateLimit-Limit` and `X-RateLimit-Remaining`
- **Exceeded**: Returns 429 Too Many Requests with `Retry-After` header

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest tests/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Authors

Built for LPU Project Assignment - Gaming Leaderboard System

## Acknowledgments

- FastAPI for the amazing web framework
- PostgreSQL for robust database performance
- Redis for blazing-fast caching
- React team for the modern UI library
- New Relic for application performance monitoring

## Documentation

Additional documentation available in the `docs/` directory:
- **HLD.md**: High-Level Design document
- **LLD.md**: Low-Level Design document
- **PERFORMANCE.md**: Performance analysis and metrics

For API documentation, visit http://localhost:8000/docs when the server is running.
