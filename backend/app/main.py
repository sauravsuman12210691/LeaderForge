from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.database import init_db
from app.api.leaderboard import router as leaderboard_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown."""
    # Startup
    print("Initializing database...")
    init_db()
    print("Application started successfully!")
    
    yield
    
    # Shutdown
    print("Application shutting down...")


# Initialize New Relic if license key is provided
if settings.new_relic_license_key:
    try:
        import newrelic.agent
        newrelic.agent.initialize()
        print("New Relic agent initialized")
    except Exception as e:
        print(f"Failed to initialize New Relic: {e}")


# Create FastAPI application
app = FastAPI(
    title="LeaderForge API",
    description="High-performance gaming leaderboard system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(leaderboard_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to LeaderForge API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
