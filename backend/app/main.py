"""
LeaderForge API - High-Performance Gaming Leaderboard System

Main application entry point with FastAPI setup, middleware configuration,
and lifecycle management.
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import init_db
from app.api.leaderboard import router as leaderboard_router
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('leaderforge.log')
    ]
)

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    Handles:
    - Database initialization
    - New Relic agent initialization
    - Graceful shutdown procedures
    """
    # Startup
    logger.info("=" * 60)
    logger.info("LeaderForge API Starting Up")
    logger.info("=" * 60)
    
    try:
        logger.info("Initializing database connection pool...")
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
        raise
    
    # Initialize New Relic monitoring if configured
    if settings.new_relic_license_key:
        try:
            import newrelic.agent
            newrelic.agent.initialize()
            logger.info("New Relic agent initialized successfully")
        except ImportError:
            logger.warning("New Relic package not installed. Monitoring disabled.")
        except Exception as e:
            logger.warning(f"New Relic initialization failed: {str(e)}")
    else:
        logger.info("New Relic monitoring not configured (license key not set)")
    
    logger.info("Application started successfully!")
    logger.info(f"API Documentation available at: http://{settings.api_host}:{settings.api_port}/docs")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("LeaderForge API Shutting Down")
    logger.info("=" * 60)
    logger.info("Application shutdown complete")


# OpenAPI metadata for Swagger documentation
tags_metadata = [
    {
        "name": "leaderboard",
        "description": "Leaderboard operations for score submission and ranking retrieval. These endpoints handle game score submissions, top players retrieval, and individual player rank lookups.",
    },
    {
        "name": "root",
        "description": "Root endpoint providing API information and health status.",
    },
]

# Create FastAPI application with enhanced OpenAPI metadata
app = FastAPI(
    title="LeaderForge API",
    description="""
    ## High-Performance Gaming Leaderboard System
    
    LeaderForge is a scalable, real-time gaming leaderboard system designed to handle millions of users and game sessions.
    
    ### Features
    - 🚀 **High Performance**: Sub-50ms p95 latency for score submissions
    - ⚡ **Real-time Updates**: Live leaderboard with intelligent caching
    - 📊 **Scalable**: Handles 1M+ users and 5M+ game sessions
    - 🔒 **Secure**: Rate limiting, input validation, and security headers
    - 📈 **Monitored**: Comprehensive APM with New Relic integration
    
    ### API Endpoints
    
    #### Score Submission
    Submit game scores with atomic database operations ensuring data consistency.
    
    #### Top Players
    Retrieve top-ranked players with intelligent Redis caching for optimal performance.
    
    #### Player Rank
    Get individual player rankings with percentile calculations.
    
    ### Rate Limiting
    API requests are rate-limited to 1000 requests per minute per IP address.
    
    ### Authentication
    Currently, the API does not require authentication. Rate limiting provides basic protection.
    
    ### Support
    For issues or questions, please refer to the project documentation.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=tags_metadata,
    contact={
        "name": "LeaderForge API Support",
        "url": "https://github.com/yourusername/LeaderForge",
    },
    license_info={
        "name": "MIT",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        },
        {
            "url": "https://api.leaderforge.com",
            "description": "Production server"
        },
    ],
)

# Add security headers middleware (first, so it wraps all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_requests
)

# Configure CORS middleware (last, so it can override headers if needed)
# Use regex pattern to allow localhost on any port for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://localhost:\d+|http://127\.0\.0\.1:\d+|http://.*\.localhost:\d+",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "Content-Type",
    ],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with detailed error messages."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "message": "Invalid request data. Please check your input."
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent error format."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with logging."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )


# Include routers
app.include_router(leaderboard_router)


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint providing API information.
    
    Returns basic API metadata and links to documentation.
    """
    return {
        "message": "Welcome to LeaderForge API",
        "version": "1.0.0",
        "description": "High-performance gaming leaderboard system",
        "docs": "/docs",
        "health": "/api/leaderboard/health",
        "endpoints": {
            "submit_score": "POST /api/leaderboard/submit",
            "get_top_players": "GET /api/leaderboard/top",
            "get_player_rank": "GET /api/leaderboard/rank/{user_id}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
        access_log=True
    )
