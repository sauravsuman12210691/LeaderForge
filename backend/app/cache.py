import json
import redis
from typing import Optional, Any
from app.config import get_settings

settings = get_settings()


class CacheManager:
    """Redis cache manager with connection pooling."""
    
    def __init__(self):
        self.redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in cache with TTL."""
        try:
            serialized = json.dumps(value)
            return self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys from cache."""
        try:
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Cache delete error: {e}")
            return 0
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
            return 0
    
    def invalidate_user_cache(self, user_id: int) -> None:
        """Invalidate all cache entries for a user."""
        self.delete(
            f"leaderboard:rank:{user_id}",
            f"leaderboard:score:{user_id}"
        )
    
    def invalidate_top_cache(self) -> None:
        """Invalidate top players cache."""
        self.delete_pattern("leaderboard:top:*")
    
    def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            return self.redis_client.ping()
        except:
            return False


# Global cache instance
cache = CacheManager()
