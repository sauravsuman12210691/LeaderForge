from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional


class ScoreSubmission(BaseModel):
    """Schema for score submission request."""
    user_id: int = Field(..., gt=0, description="User ID must be positive")
    score: int = Field(..., ge=0, description="Score must be non-negative")
    
    @validator('score')
    def validate_score(cls, v):
        if v > 1000000:
            raise ValueError('Score cannot exceed 1,000,000')
        return v


class ScoreResponse(BaseModel):
    """Schema for score submission response."""
    success: bool
    user_id: int
    new_total_score: int
    current_rank: Optional[int]
    message: str


class LeaderboardEntry(BaseModel):
    """Schema for a single leaderboard entry."""
    rank: int
    user_id: int
    username: str
    total_score: int
    session_count: int
    
    class Config:
        from_attributes = True


class TopPlayersResponse(BaseModel):
    """Schema for top players response."""
    top_players: list[LeaderboardEntry]
    total_players: int
    timestamp: datetime


class PlayerRankResponse(BaseModel):
    """Schema for player rank response."""
    user_id: int
    username: str
    rank: int
    total_score: int
    session_count: int
    percentile: float
    
    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    detail: Optional[str] = None
