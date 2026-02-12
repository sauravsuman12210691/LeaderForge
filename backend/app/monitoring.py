"""
Monitoring and instrumentation utilities for New Relic APM.

Provides decorators and context managers for tracking performance metrics,
database queries, and custom business metrics.
"""
import functools
import inspect
import logging
from typing import Callable, Any
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Try to import New Relic, but don't fail if not available
try:
    import newrelic.agent
    NEW_RELIC_AVAILABLE = True
except ImportError:
    NEW_RELIC_AVAILABLE = False
    logger.info("New Relic not available - monitoring disabled")


def monitor_transaction(name: str = None):
    """
    Decorator to monitor function execution as a New Relic transaction.
    
    Args:
        name: Custom transaction name (defaults to function name)
        
    Usage:
        @monitor_transaction("submit_score")
        async def submit_score(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Check if function is async using inspect module
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not NEW_RELIC_AVAILABLE or not settings.new_relic_license_key:
                    return await func(*args, **kwargs)
                
                transaction_name = name or f"{func.__module__}.{func.__name__}"
                
                try:
                    with newrelic.agent.FunctionTrace(transaction_name):
                        return await func(*args, **kwargs)
                except Exception as e:
                    logger.debug(f"New Relic tracing error: {e}")
                    return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not NEW_RELIC_AVAILABLE or not settings.new_relic_license_key:
                    return func(*args, **kwargs)
                
                transaction_name = name or f"{func.__module__}.{func.__name__}"
                
                try:
                    with newrelic.agent.FunctionTrace(transaction_name):
                        return func(*args, **kwargs)
                except Exception as e:
                    logger.debug(f"New Relic tracing error: {e}")
                    return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def record_custom_metric(metric_name: str, value: float):
    """
    Record a custom metric in New Relic.
    
    Args:
        metric_name: Name of the metric (e.g., "Leaderboard/CacheHitRate")
        value: Metric value
    """
    if NEW_RELIC_AVAILABLE and settings.new_relic_license_key:
        try:
            newrelic.agent.record_custom_metric(metric_name, value)
        except Exception as e:
            logger.debug(f"Failed to record custom metric: {e}")


def record_custom_event(event_type: str, attributes: dict):
    """
    Record a custom event in New Relic.
    
    Args:
        event_type: Type of event (e.g., "ScoreSubmission")
        attributes: Dictionary of event attributes
    """
    if NEW_RELIC_AVAILABLE and settings.new_relic_license_key:
        try:
            newrelic.agent.record_custom_event(event_type, attributes)
        except Exception as e:
            logger.debug(f"Failed to record custom event: {e}")


class DatabaseTrace:
    """
    Context manager for tracking database query performance.
    
    Usage:
        with DatabaseTrace("get_top_players"):
            # database query here
            pass
    """
    
    def __init__(self, operation_name: str):
        """
        Initialize database trace context.
        
        Args:
            operation_name: Name of the database operation
        """
        self.operation_name = operation_name
        self.trace = None
    
    def __enter__(self):
        if NEW_RELIC_AVAILABLE and settings.new_relic_license_key:
            try:
                self.trace = newrelic.agent.DatastoreTrace(
                    product="PostgreSQL",
                    target="leaderboard",
                    operation=self.operation_name
                )
                self.trace.__enter__()
            except Exception as e:
                logger.debug(f"Failed to start database trace: {e}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.trace:
            try:
                self.trace.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.debug(f"Failed to end database trace: {e}")


class CacheTrace:
    """
    Context manager for tracking cache operations.
    
    Usage:
        with CacheTrace("get", "leaderboard:top:10"):
            # cache operation here
            pass
    """
    
    def __init__(self, operation: str, key: str):
        """
        Initialize cache trace context.
        
        Args:
            operation: Cache operation type ("get", "set", "delete")
            key: Cache key being accessed
        """
        self.operation = operation
        self.key = key
    
    def __enter__(self):
        if NEW_RELIC_AVAILABLE and settings.new_relic_license_key:
            try:
                record_custom_metric(f"Cache/{self.operation.capitalize()}", 1)
            except Exception:
                pass
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
