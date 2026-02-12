"""
Leaderboard API endpoints for score submission and ranking retrieval.

This module implements the core leaderboard functionality including:
- Score submission with atomic updates
- Top players retrieval with caching
- Player rank lookup with percentile calculation
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Path
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models import User, GameSession, Leaderboard
from app.schemas import (
    ScoreSubmission, ScoreResponse, TopPlayersResponse, 
    PlayerRankResponse, LeaderboardEntry, ErrorResponse
)
from app.cache import cache
from app.config import get_settings

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])
settings = get_settings()


@router.post(
    "/submit",
    response_model=ScoreResponse,
    status_code=200,
    responses={
        200: {
            "description": "Score submitted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "user_id": 123,
                        "new_total_score": 5000,
                        "current_rank": 42,
                        "message": "Score submitted successfully. Current rank: 42"
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "User with ID 999999 not found",
                        "status_code": 404
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation Error",
                        "detail": [
                            {
                                "loc": ["body", "score"],
                                "msg": "ensure this value is less than or equal to 1000000",
                                "type": "value_error.number.not_le"
                            }
                        ],
                        "message": "Invalid request data. Please check your input."
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "message": "An unexpected error occurred. Please try again later."
                    }
                }
            }
        }
    },
    summary="Submit a game score",
    description="""
    Submit a new game score for a user.
    
    This endpoint handles score submission with atomic database operations:
    - Validates user exists
    - Inserts game session record
    - Updates leaderboard aggregation atomically
    - Invalidates relevant caches
    - Returns updated rank and total score
    
    **Performance**: Sub-50ms p95 latency
    
    **Rate Limit**: 1000 requests per minute per IP
    """
)
async def submit_score(
    submission: ScoreSubmission,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit a new game score for a user.
    
    This endpoint handles score submission with atomic database operations:
    1. Validates user exists
    2. Inserts game session record
    3. Updates leaderboard aggregation atomically
    4. Invalidates relevant caches
    5. Returns updated rank and total score
    
    Args:
        submission: ScoreSubmission schema containing user_id and score
        request: FastAPI request object for logging
        db: Database session dependency
        
    Returns:
        ScoreResponse with success status, new total score, and current rank
        
    Raises:
        HTTPException: 404 if user not found, 500 on database errors
    """
    try:
        logger.info(
            f"Score submission request: user_id={submission.user_id}, "
            f"score={submission.score}, client_ip={request.client.host if request.client else 'unknown'}"
        )
        
        # Verify user exists
        user = db.query(User).filter(User.id == submission.user_id).first()
        if not user:
            logger.warning(f"Score submission failed: User {submission.user_id} not found")
            raise HTTPException(
                status_code=404, 
                detail=f"User with ID {submission.user_id} not found"
            )
        
        # Insert game session within transaction
        game_session = GameSession(
            user_id=submission.user_id,
            score=submission.score,
            game_mode=submission.game_mode or 'solo'
        )
        db.add(game_session)
        
        # Atomic upsert: Update or insert leaderboard entry using raw SQL for performance
        upsert_query = text("""
            INSERT INTO leaderboard (user_id, username, total_score, session_count, last_updated)
            VALUES (:user_id, :username, :score, 1, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                total_score = leaderboard.total_score + :score,
                session_count = leaderboard.session_count + 1,
                last_updated = NOW()
            RETURNING total_score, session_count
        """)
        
        result = db.execute(
            upsert_query,
            {
                "user_id": submission.user_id,
                "username": user.username,
                "score": submission.score
            }
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=500, detail="Failed to update leaderboard")
        
        new_total_score = row[0]
        session_count = row[1]
        
        # Commit transaction atomically
        db.commit()
        logger.debug(
            f"Score submitted successfully: user_id={submission.user_id}, "
            f"new_total_score={new_total_score}, session_count={session_count}"
        )
        
        # Invalidate caches after successful commit
        try:
            cache.invalidate_user_cache(submission.user_id)
            cache.invalidate_top_cache()
        except Exception as cache_error:
            logger.warning(f"Cache invalidation failed: {cache_error}")
            # Don't fail the request if cache invalidation fails
        
        # Get current rank using window function
        rank_query = text("""
            SELECT rank FROM (
                SELECT user_id, RANK() OVER (ORDER BY total_score DESC) as rank
                FROM leaderboard
            ) ranked
            WHERE user_id = :user_id
        """)
        rank_result = db.execute(rank_query, {"user_id": submission.user_id})
        rank_row = rank_result.fetchone()
        current_rank = rank_row[0] if rank_row else None
        
        logger.info(
            f"Score submission completed: user_id={submission.user_id}, "
            f"rank={current_rank}, total_score={new_total_score}"
        )
        
        return ScoreResponse(
            success=True,
            user_id=submission.user_id,
            new_total_score=new_total_score,
            current_rank=current_rank,
            message=f"Score submitted successfully. Current rank: {current_rank}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Rollback transaction on error
        db.rollback()
        logger.error(
            f"Score submission failed: user_id={submission.user_id}, "
            f"error={str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing your score submission"
        )


@router.get(
    "/top",
    response_model=TopPlayersResponse,
    status_code=200,
    responses={
        200: {
            "description": "Top players retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "top_players": [
                            {
                                "rank": 1,
                                "user_id": 456,
                                "username": "player1",
                                "total_score": 100000,
                                "session_count": 50
                            },
                            {
                                "rank": 2,
                                "user_id": 789,
                                "username": "player2",
                                "total_score": 95000,
                                "session_count": 45
                            }
                        ],
                        "total_players": 1000000,
                        "timestamp": "2026-02-12T10:30:00"
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation Error",
                        "detail": [
                            {
                                "loc": ["query", "limit"],
                                "msg": "ensure this value is greater than or equal to 1",
                                "type": "value_error.number.not_ge"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Internal server error"
        }
    },
    summary="Get top players",
    description="""
    Retrieve the top N players sorted by total_score.
    
    This endpoint implements intelligent caching:
    - Checks Redis cache first for sub-10ms response times
    - Falls back to database query if cache miss
    - Results are cached for 30 seconds to balance freshness and performance
    
    **Performance**:
    - Cache hit: < 10ms p95 latency
    - Cache miss: < 100ms p95 latency
    
    **Rate Limit**: 1000 requests per minute per IP
    """
)
async def get_top_players(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of top players to retrieve (1-100)",
        example=10
    ),
    db: Session = Depends(get_db)
):
    """
    Retrieve the top N players sorted by total_score.
    
    This endpoint implements intelligent caching:
    - Checks Redis cache first for sub-10ms response times
    - Falls back to database query if cache miss
    - Results are cached for 30 seconds to balance freshness and performance
    
    Args:
        limit: Number of top players to retrieve (default: 10, max: 100)
        db: Database session dependency
        
    Returns:
        TopPlayersResponse containing list of top players, total player count, and timestamp
        
    Performance:
        - Cache hit: < 10ms p95 latency
        - Cache miss: < 100ms p95 latency
    """
    cache_key = f"leaderboard:top:{limit}"
    
    # Try cache first for optimal performance
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.debug(f"Cache hit for top players: limit={limit}")
        return TopPlayersResponse(**cached_data)
    
    logger.debug(f"Cache miss for top players: limit={limit}, querying database")
    
    try:
        # Query database with optimized index on total_score DESC
        top_players = db.query(Leaderboard)\
            .order_by(Leaderboard.total_score.desc())\
            .limit(limit)\
            .all()
        
        # Get total player count for context
        total_players = db.query(Leaderboard).count()
        
        # Build response entries with rank calculation
        entries = [
            LeaderboardEntry(
                rank=idx + 1,
                user_id=player.user_id,
                username=player.username,
                total_score=player.total_score,
                session_count=player.session_count
            )
            for idx, player in enumerate(top_players)
        ]
        
        response_data = {
            "top_players": [entry.model_dump() for entry in entries],
            "total_players": total_players,
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache the result for future requests
        try:
            cache.set(cache_key, response_data, settings.cache_ttl_top)
        except Exception as cache_error:
            logger.warning(f"Failed to cache top players: {cache_error}")
            # Continue without caching if Redis is unavailable
        
        logger.info(f"Retrieved top {len(entries)} players from database")
        
        return TopPlayersResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Failed to retrieve top players: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving top players"
        )


@router.get(
    "/rank/{user_id}",
    response_model=PlayerRankResponse,
    status_code=200,
    responses={
        200: {
            "description": "Player rank retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": 123,
                        "username": "player123",
                        "rank": 42,
                        "total_score": 5000,
                        "session_count": 10,
                        "percentile": 95.8
                    }
                }
            }
        },
        404: {
            "description": "Player not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Player with ID 999999 not found in leaderboard. They may not have submitted any scores yet.",
                        "status_code": 404
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "User ID must be a positive integer",
                        "status_code": 422
                    }
                }
            }
        },
        500: {
            "description": "Internal server error"
        }
    },
    summary="Get player rank",
    description="""
    Fetch the current rank and statistics for a specific player.
    
    This endpoint calculates the player's rank using efficient SQL window functions
    and includes percentile calculation. Results are cached for 60 seconds.
    
    **Performance**:
    - Cache hit: < 10ms p95 latency
    - Cache miss: < 50ms p95 latency
    
    **Rate Limit**: 1000 requests per minute per IP
    """
)
async def get_player_rank(
    user_id: int = Path(..., gt=0, description="The ID of the user to look up", example=123),
    db: Session = Depends(get_db)
):
    """
    Fetch the current rank and statistics for a specific player.
    
    This endpoint calculates the player's rank using efficient SQL window functions
    and includes percentile calculation. Results are cached for 60 seconds.
    
    Args:
        user_id: The ID of the user to look up
        db: Database session dependency
        
    Returns:
        PlayerRankResponse containing rank, total_score, session_count, and percentile
        
    Raises:
        HTTPException: 404 if player not found in leaderboard
        
    Performance:
        - Cache hit: < 10ms p95 latency
        - Cache miss: < 50ms p95 latency
    """
    if user_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="User ID must be a positive integer"
        )
    
    cache_key = f"leaderboard:rank:{user_id}"
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.debug(f"Cache hit for player rank: user_id={user_id}")
        return PlayerRankResponse(**cached_data)
    
    logger.debug(f"Cache miss for player rank: user_id={user_id}, querying database")
    
    try:
        # Efficient rank calculation using window function
        # This single query calculates rank and total count in one pass
        rank_query = text("""
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
        """)
        
        result = db.execute(rank_query, {"user_id": user_id})
        row = result.fetchone()
        
        if not row:
            logger.warning(f"Player rank lookup failed: User {user_id} not found in leaderboard")
            raise HTTPException(
                status_code=404,
                detail=f"Player with ID {user_id} not found in leaderboard. "
                       "They may not have submitted any scores yet."
            )
        
        # Calculate percentile: (total_count - rank) / total_count * 100
        # Higher percentile means better performance
        total_count = row[5]
        rank = row[2]
        percentile = ((total_count - rank) / total_count * 100) if total_count > 0 else 0
        
        response_data = {
            "user_id": row[0],
            "username": row[1],
            "rank": rank,
            "total_score": row[3],
            "session_count": row[4],
            "percentile": round(percentile, 2)
        }
        
        # Cache the result
        try:
            cache.set(cache_key, response_data, settings.cache_ttl_rank)
        except Exception as cache_error:
            logger.warning(f"Failed to cache player rank: {cache_error}")
            # Continue without caching if Redis is unavailable
        
        logger.info(
            f"Player rank retrieved: user_id={user_id}, rank={rank}, "
            f"percentile={percentile:.2f}%"
        )
        
        return PlayerRankResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to retrieve player rank: user_id={user_id}, error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving player rank"
        )


@router.get(
    "/health",
    status_code=200,
    responses={
        200: {
            "description": "Health check response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "database": "ok",
                        "cache": "ok",
                        "timestamp": "2026-02-12T10:30:00"
                    }
                }
            }
        }
    },
    summary="Health check",
    description="""
    Health check endpoint for monitoring system status.
    
    Checks the health of:
    - Database connectivity
    - Redis cache connectivity
    
    Returns overall system health status.
    """
)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for monitoring system status.
    
    Checks the health of:
    - Database connectivity
    - Redis cache connectivity
    
    Returns:
        JSON object with status of each component and overall system health
    """
    health_status = {
        "status": "healthy",
        "database": "ok",
        "cache": "ok",
        "timestamp": datetime.now().isoformat()
    }
    
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["database"] = "error"
        health_status["status"] = "degraded"
    
    # Check Redis cache connectivity
    try:
        if cache.ping():
            health_status["cache"] = "ok"
        else:
            health_status["cache"] = "error"
            health_status["status"] = "degraded"
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        health_status["cache"] = "error"
        health_status["status"] = "degraded"
    
    return health_status
