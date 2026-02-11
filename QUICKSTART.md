# LeaderForge - Quick Start Guide

## Getting Started in 5 Minutes

### Step 1: Start the Services

```bash
# Navigate to project directory
cd LeaderForge

# Start all services with Docker Compose
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps
```

### Step 2: Verify Services are Running

```bash
# Check backend health
curl http://localhost:8000/api/health

# Expected response:
# {"status": "healthy", "database": "ok", "cache": "ok", ...}
```

### Step 3: Populate Database (Optional but Recommended)

```bash
# This will generate 1M users and 5M game sessions
# Takes approximately 5-10 minutes
docker-compose exec backend python scripts/populate_data.py

# Or with smaller dataset for quick testing (10K users, 50K sessions):
# Modify the script or run a custom command
```

### Step 4: Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Step 5: Test the APIs

#### Submit a Score
```bash
curl -X POST http://localhost:8000/api/scores \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "score": 5000}'
```

#### Get Top 10 Players
```bash
curl http://localhost:8000/api/leaderboard/top?limit=10
```

#### Get Player Rank
```bash
curl http://localhost:8000/api/leaderboard/rank/1
```

### Step 6: Run Load Tests

```bash
# Test with 100 concurrent users for 60 seconds
docker-compose exec backend python scripts/load_simulator.py http://backend:8000 100 60
```

## Development Workflow

### Backend Development

```bash
# Enter backend container
docker-compose exec backend bash

# Run tests
pytest tests/ -v

# Check logs
docker-compose logs -f backend
```

### Frontend Development

```bash
# Enter frontend container
docker-compose exec frontend sh

# Install new package
npm install <package-name>

# Check logs
docker-compose logs -f frontend
```

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U admin -d leaderboard

# Run SQL queries
SELECT COUNT(*) FROM users;
SELECT * FROM leaderboard ORDER BY total_score DESC LIMIT 10;
```

### Redis Access

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check cached keys
KEYS leaderboard:*

# Get cache value
GET leaderboard:top:10
```

## Stopping the Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Rebuild container
docker-compose build backend
docker-compose up -d backend
```

### Database connection error
```bash
# Ensure PostgreSQL is healthy
docker-compose ps postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Frontend can't connect to backend
```bash
# Check if backend is running
curl http://localhost:8000/api/health

# Check Docker network
docker network inspect leaderforge_leaderforge_network
```

## Next Steps

1. Review the [HLD](docs/HLD.md) for architecture details
2. Review the [LLD](docs/LLD.md) for implementation details
3. Review the [Performance Report](docs/PERFORMANCE.md) for optimization insights
4. Set up New Relic monitoring (see README.md)
5. Run comprehensive tests (see backend/tests/)
6. Customize the frontend design
7. Add authentication and authorization
8. Deploy to production

## Useful Commands

```bash
# View all logs
docker-compose logs -f

# Restart a specific service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build

# Execute command in container
docker-compose exec backend <command>

# Stop specific service
docker-compose stop frontend

# Remove all containers and volumes
docker-compose down -v
```

## Performance Tips

1. **First Run**: Initial requests may be slower due to cache warming
2. **Load Data**: Populate database for realistic testing
3. **Cache Warming**: Top queries are cached after first request
4. **Monitoring**: Use New Relic for detailed performance insights

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review logs: `docker-compose logs -f`
3. Check GitHub issues (if repository is public)
4. Contact: [Your contact information]

Happy coding! 🚀
