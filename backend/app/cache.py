"""
Redis cache manager for leaderboard data caching.

Provides high-performance caching layer with intelligent invalidation
strategies to ensure data consistency while maximizing cache hit rates.
"""
import json
import logging
import redis
from typing import Optional, Any
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheManager:
    """
    Redis cache manager with connection pooling and error handling.
    
    Features:
    - Connection pooling for high concurrency
    - Automatic JSON serialization/deserialization
    - Graceful degradation when Redis is unavailable
    - Pattern-based cache invalidation
    """
    
    def __init__(self):
        """Initialize Redis client with connection pooling."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=50,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis cache initialized: {settings.redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {str(e)}")
            self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Deserialized value if found, None otherwise
        """
        if not self.redis_client:
            return None
            
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except redis.RedisError as e:
            logger.warning(f"Cache get error for key '{key}': {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Cache deserialization error for key '{key}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected cache get error: {str(e)}", exc_info=True)
            return None
    
    def set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
            
        try:
            serialized = json.dumps(value, default=str)  # Handle datetime objects
            return self.redis_client.setex(key, ttl, serialized)
        except redis.RedisError as e:
            logger.warning(f"Cache set error for key '{key}': {str(e)}")
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"Cache serialization error for key '{key}': {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected cache set error: {str(e)}", exc_info=True)
            return False
    
    def delete(self, *keys: str) -> int:
        """
        Delete one or more keys from cache.
        
        Args:
            *keys: Variable number of cache keys to delete
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client or not keys:
            return 0
            
        try:
            return self.redis_client.delete(*keys)
        except redis.RedisError as e:
            logger.warning(f"Cache delete error: {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected cache delete error: {str(e)}", exc_info=True)
            return 0
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Warning: This operation can be slow on large datasets.
        Consider using SCAN for production environments.
        
        Args:
            pattern: Redis key pattern (e.g., "leaderboard:top:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0
            
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.debug(f"Deleted {deleted} keys matching pattern '{pattern}'")
                return deleted
            return 0
        except redis.RedisError as e:
            logger.warning(f"Cache delete_pattern error for '{pattern}': {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected cache delete_pattern error: {str(e)}", exc_info=True)
            return 0
    
    def invalidate_user_cache(self, user_id: int) -> None:
        """
        Invalidate all cache entries for a specific user.
        
        Called after score submission to ensure fresh data on next request.
        
        Args:
            user_id: User ID whose cache should be invalidated
        """
        self.delete(
            f"leaderboard:rank:{user_id}",
            f"leaderboard:score:{user_id}"
        )
        logger.debug(f"Invalidated cache for user_id={user_id}")
    
    def invalidate_top_cache(self) -> None:
        """
        Invalidate top players cache.
        
        Called after score submission to ensure leaderboard reflects latest rankings.
        """
        deleted = self.delete_pattern("leaderboard:top:*")
        logger.debug(f"Invalidated top players cache ({deleted} keys)")
    
    def ping(self) -> bool:
        """
        Check if Redis is available.
        
        Returns:
            True if Redis is reachable, False otherwise
        """
        if not self.redis_client:
            return False
            
        try:
            return self.redis_client.ping()
        except Exception:
            return False


# Global cache instance
cache = CacheManager()
