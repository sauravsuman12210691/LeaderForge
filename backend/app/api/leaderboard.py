from fastapi import APIRouter, Depends, HTTPException, Query
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

router = APIRouter(prefix="/api", tags=["leaderboard"])
settings = get_settings()


@router.post("/scores", response_model=ScoreResponse)
async def submit_score(
    submission: ScoreSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit a new game score for a user.
    
    This endpoint:
    1. Inserts the game session
    2. Updates the leaderboard aggregation
    3. Invalidates relevant caches
    4. Returns the new rank
    """
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == submission.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Start transaction
        # Insert game session
        game_session = GameSession(
            user_id=submission.user_id,
            score=submission.score
        )
        db.add(game_session)
        
        # Update or insert leaderboard entry using raw SQL for better performance
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
            {"user_id": submission.user_id, "username": user.username, "score": submission.score}
        )
        row = result.fetchone()
        new_total_score = row[0]
        
        db.commit()
        
        # Invalidate caches
        cache.invalidate_user_cache(submission.user_id)
        cache.invalidate_top_cache()
        
        # Get current rank
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
        
        return ScoreResponse(
            success=True,
            user_id=submission.user_id,
            new_total_score=new_total_score,
            current_rank=current_rank,
            message=f"Score submitted successfully. Current rank: {current_rank}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit score: {str(e)}")


@router.get("/leaderboard/top", response_model=TopPlayersResponse)
async def get_top_players(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get top N players by total score.
    
    Results are cached in Redis for better performance.
    """
    cache_key = f"leaderboard:top:{limit}"
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return TopPlayersResponse(**cached_data)
    
    # Query database
    top_players = db.query(Leaderboard)\
        .order_by(Leaderboard.total_score.desc())\
        .limit(limit)\
        .all()
    
    # Get total player count
    total_players = db.query(Leaderboard).count()
    
    # Build response
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
    
    # Cache the result
    cache.set(cache_key, response_data, settings.cache_ttl_top)
    
    return TopPlayersResponse(**response_data)


@router.get("/leaderboard/rank/{user_id}", response_model=PlayerRankResponse)
async def get_player_rank(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get rank and stats for a specific player.
    
    Calculates rank using SQL window functions and caches the result.
    """
    cache_key = f"leaderboard:rank:{user_id}"
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return PlayerRankResponse(**cached_data)
    
    # Query with rank calculation
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
        raise HTTPException(status_code=404, detail="Player not found in leaderboard")
    
    # Calculate percentile
    percentile = ((row[5] - row[2]) / row[5]) * 100 if row[5] > 0 else 0
    
    response_data = {
        "user_id": row[0],
        "username": row[1],
        "rank": row[2],
        "total_score": row[3],
        "session_count": row[4],
        "percentile": round(percentile, 2)
    }
    
    # Cache the result
    cache.set(cache_key, response_data, settings.cache_ttl_rank)
    
    return PlayerRankResponse(**response_data)


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Check database
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except:
        db_status = "error"
    
    # Check Redis
    redis_status = "ok" if cache.ping() else "error"
    
    return {
        "status": "healthy" if db_status == "ok" and redis_status == "ok" else "degraded",
        "database": db_status,
        "cache": redis_status,
        "timestamp": datetime.now().isoformat()
    }
