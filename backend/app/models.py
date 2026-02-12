from sqlalchemy import Column, Integer, String, BigInteger, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class GameSession(Base):
    """
    Game session model representing a single game play session.
    
    Stores individual game scores with metadata for analytics and leaderboard aggregation.
    """
    __tablename__ = "game_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Integer, nullable=False, index=True)
    game_mode = Column(String(50), nullable=False, default="solo", index=True)
    played_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)
    
    # Composite index for common query patterns
    __table_args__ = (
        Index('idx_game_sessions_user_score', user_id, score.desc()),
        Index('idx_game_sessions_mode_score', game_mode, score.desc()),
    )


class Leaderboard(Base):
    """Leaderboard model with aggregated scores."""
    __tablename__ = "leaderboard"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    username = Column(String(50), nullable=False)
    total_score = Column(BigInteger, nullable=False, index=True)
    session_count = Column(Integer, nullable=False)
    last_updated = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Create descending index for fast top-N queries
    __table_args__ = (
        Index('idx_leaderboard_score_desc', total_score.desc()),
    )
