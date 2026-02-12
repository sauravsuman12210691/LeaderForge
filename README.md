# LeaderForge - High-Performance Gaming Leaderboard System

A scalable, real-time gaming leaderboard system built with FastAPI, React, PostgreSQL, and Redis. Designed to handle millions of users and game sessions with sub-50ms API response times.

## Features

- **High Performance**: Sub-50ms p95 latency for score submissions
- **Real-time Updates**: Live leaderboard with 5-second refresh intervals
- **Scalable Architecture**: Handles 1M+ users and 5M+ game sessions
- **Intelligent Caching**: Redis-based caching with smart invalidation
- **Modern UI**: Beautiful React frontend with real-time updates
- **Comprehensive Monitoring**: New Relic APM integration

## Tech Stack

### Backend
- **FastAPI**: High-performance async Python web framework
- **PostgreSQL**: Robust relational database with optimized indexes
- **Redis**: In-memory caching for sub-10ms response times
- **SQLAlchemy**: ORM with connection pooling
- **New Relic**: Application performance monitoring

### Frontend
- **React 18**: Modern UI with hooks
- **TanStack Query**: Efficient data fetching and caching
- **Tailwind CSS**: Utility-first styling
- **Vite**: Fast build tool and dev server

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

2. Create environment file:
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
- API Docs: http://localhost:8000/docs

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

### Submit Score
```http
POST /api/scores
Content-Type: application/json

{
  "user_id": 123,
  "score": 500
}
```

### Get Top Players
```http
GET /api/leaderboard/top?limit=10
```

### Get Player Rank
```http
GET /api/leaderboard/rank/{user_id}
```

### Health Check
```http
GET /api/health
```

## Performance Testing

### Load Simulations

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
┌─────────────┐
│   React     │ Frontend (Port 3000)
│  Frontend   │
└──────┬──────┘
       │ HTTP/WebSocket
┌──────▼──────┐
│   FastAPI   │ Backend (Port 8000)
│   Backend   │
└──────┬──────┘
       │
   ┌───┴───┬──────────┐
   │       │          │
┌──▼───┐ ┌▼───────┐ ┌▼─────────┐
│Redis │ │PostgreSQL│ │New Relic│
│Cache │ │Database  │ │   APM   │
└──────┘ └─────────┘ └─────────┘
```

## Database Schema

### Users Table
- `id`: Primary key
- `username`: Unique username
- `email`: Unique email
- `created_at`: Registration timestamp

### Game Sessions Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `score`: Game score
- `played_at`: Session timestamp

### Leaderboard Table
- `user_id`: Primary key
- `username`: Cached username
- `total_score`: Aggregated score
- `session_count`: Total games played
- `last_updated`: Last update timestamp

## Caching Strategy

### Cache Keys
- `leaderboard:top:{limit}`: Top N players (TTL: 30s)
- `leaderboard:rank:{user_id}`: Player rank (TTL: 60s)
- `leaderboard:score:{user_id}`: Player total score (TTL: 60s)

### Cache Invalidation
- On score submission: Invalidate affected user's cache and top-N cache
- Uses Redis atomic operations for consistency

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

# Run development server
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests (if implemented)
cd frontend
npm test
```

## Optimization Techniques

1. **Database Optimizations**
   - B-tree indexes on frequently queried columns
   - Descending index on `total_score` for fast top-N queries
   - Connection pooling (20 connections, 40 max overflow)
   - Materialized leaderboard table to avoid expensive aggregations

2. **Caching Optimizations**
   - Redis caching for hot data
   - Short TTLs (30-60s) to balance freshness and performance
   - Intelligent cache invalidation on writes
   - Pipeline operations for batch cache updates

3. **Application Optimizations**
   - Async endpoints for I/O operations
   - Prepared statements for common queries
   - Batch inserts for data population
   - SQL window functions for efficient rank calculation

4. **Concurrency Handling**
   - Database transactions for consistency
   - Upsert operations with ON CONFLICT
   - Row-level locking for leaderboard updates

## Monitoring with New Relic

1. Sign up for New Relic account: https://newrelic.com

2. Get your license key from Account Settings

3. Set environment variable:
```bash
export NEW_RELIC_LICENSE_KEY=your_license_key_here
```

4. Restart the backend service

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
```

### Redis Connection Issues
```bash
# Check if Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# View logs
docker-compose logs redis
```

### Backend Issues
```bash
# View backend logs
docker-compose logs backend -f

# Restart backend
docker-compose restart backend

# Check health
curl http://localhost:8000/api/health
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Authors

Built for LPU Project Assignment

## Acknowledgments

- FastAPI for the amazing web framework
- PostgreSQL for robust database performance
- Redis for blazing-fast caching
- React team for the modern UI library
