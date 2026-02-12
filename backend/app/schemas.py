from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional


class ScoreSubmission(BaseModel):
    """
    Schema for score submission request.
    
    Validates user_id and score according to business rules.
    
    Example:
        {
            "user_id": 123,
            "score": 500,
            "game_mode": "solo"
        }
    """
    user_id: int = Field(
        ...,
        gt=0,
        description="User ID must be a positive integer",
        example=123
    )
    score: int = Field(
        ...,
        ge=0,
        le=1000000,
        description="Score must be non-negative and cannot exceed 1,000,000",
        example=500
    )
    game_mode: Optional[str] = Field(
        default="solo",
        description="Game mode: 'solo' or 'team' (default: 'solo')",
        example="solo"
    )
    
    @validator('score')
    def validate_score(cls, v):
        """Validate score is within acceptable range."""
        if v > 1000000:
            raise ValueError('Score cannot exceed 1,000,000')
        return v
    
    @validator('game_mode')
    def validate_game_mode(cls, v):
        """Validate game mode is one of the allowed values."""
        if v and v not in ['solo', 'team']:
            raise ValueError("game_mode must be either 'solo' or 'team'")
        return v or 'solo'
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": 123,
                "score": 500,
                "game_mode": "solo"
            }
        }


class ScoreResponse(BaseModel):
    """
    Schema for score submission response.
    
    Example:
        {
            "success": true,
            "user_id": 123,
            "new_total_score": 5000,
            "current_rank": 42,
            "message": "Score submitted successfully. Current rank: 42"
        }
    """
    success: bool = Field(..., description="Whether the score submission was successful", example=True)
    user_id: int = Field(..., description="The user ID who submitted the score", example=123)
    new_total_score: int = Field(..., description="The user's new total score after this submission", example=5000)
    current_rank: Optional[int] = Field(None, description="The user's current rank in the leaderboard", example=42)
    message: str = Field(..., description="Human-readable message about the submission result", example="Score submitted successfully. Current rank: 42")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "user_id": 123,
                "new_total_score": 5000,
                "current_rank": 42,
                "message": "Score submitted successfully. Current rank: 42"
            }
        }


class LeaderboardEntry(BaseModel):
    """
    Schema for a single leaderboard entry.
    
    Example:
        {
            "rank": 1,
            "user_id": 456,
            "username": "player1",
            "total_score": 100000,
            "session_count": 50
        }
    """
    rank: int = Field(..., description="Player's rank in the leaderboard (1 = highest)", example=1)
    user_id: int = Field(..., description="Unique user identifier", example=456)
    username: str = Field(..., description="Player's username", example="player1")
    total_score: int = Field(..., description="Player's total aggregated score", example=100000)
    session_count: int = Field(..., description="Number of game sessions played", example=50)
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "rank": 1,
                "user_id": 456,
                "username": "player1",
                "total_score": 100000,
                "session_count": 50
            }
        }


class TopPlayersResponse(BaseModel):
    """
    Schema for top players response.
    
    Example:
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
    """
    top_players: list[LeaderboardEntry] = Field(..., description="List of top-ranked players")
    total_players: int = Field(..., description="Total number of players in the leaderboard", example=1000000)
    timestamp: datetime = Field(..., description="Timestamp when the leaderboard was retrieved", example="2026-02-12T10:30:00")
    
    class Config:
        schema_extra = {
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


class PlayerRankResponse(BaseModel):
    """
    Schema for player rank response.
    
    Example:
        {
            "user_id": 123,
            "username": "player123",
            "rank": 42,
            "total_score": 5000,
            "session_count": 10,
            "percentile": 95.8
        }
    """
    user_id: int = Field(..., description="Unique user identifier", example=123)
    username: str = Field(..., description="Player's username", example="player123")
    rank: int = Field(..., description="Player's current rank in the leaderboard", example=42)
    total_score: int = Field(..., description="Player's total aggregated score", example=5000)
    session_count: int = Field(..., description="Number of game sessions played", example=10)
    percentile: float = Field(..., description="Player's percentile ranking (higher is better)", example=95.8)
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "user_id": 123,
                "username": "player123",
                "rank": 42,
                "total_score": 5000,
                "session_count": 10,
                "percentile": 95.8
            }
        }


class ErrorResponse(BaseModel):
    """
    Schema for error responses.
    
    Example:
        {
            "error": "User not found",
            "detail": "User with ID 999999 not found",
            "status_code": 404
        }
    """
    error: str = Field(..., description="Error type or message", example="User not found")
    detail: Optional[str] = Field(None, description="Detailed error message", example="User with ID 999999 not found")
    status_code: Optional[int] = Field(None, description="HTTP status code", example=404)
    
    class Config:
        schema_extra = {
            "example": {
                "error": "User not found",
                "detail": "User with ID 999999 not found",
                "status_code": 404
            }
        }
