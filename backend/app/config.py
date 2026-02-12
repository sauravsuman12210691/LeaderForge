from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database
    database_url: str = "postgresql://admin:password@localhost:5432/leaderboard"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_top: int = 30  # seconds
    cache_ttl_rank: int = 60  # seconds
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",  # For Swagger UI
        "http://127.0.0.1:8000",  # For Swagger UI
    ]
    
    # New Relic
    new_relic_license_key: str = ""
    new_relic_app_name: str = "LeaderForge"
    
    # Performance
    rate_limit_requests: int = 1000
    rate_limit_window: int = 60  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
