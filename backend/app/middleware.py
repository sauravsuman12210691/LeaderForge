"""
Middleware for request rate limiting and security headers.

Provides protection against abuse and ensures API security best practices.
"""
import time
import logging
from collections import defaultdict
from typing import Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent API abuse.
    
    Implements sliding window rate limiting per IP address.
    """
    
    def __init__(self, app, requests_per_minute: int = 100):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application instance
            requests_per_minute: Maximum requests allowed per minute per IP
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)  # IP -> list of request timestamps
        self.cleanup_interval = 60  # Clean up old entries every 60 seconds
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and apply rate limiting.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from next handler or rate limit error
        """
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Clean up old entries periodically
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Check rate limit
        if not self._check_rate_limit(client_ip, current_time):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return Response(
                content='{"error": "Rate limit exceeded", "message": "Too many requests. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0"
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self._get_remaining_requests(client_ip, current_time)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _check_rate_limit(self, client_ip: str, current_time: float) -> bool:
        """Check if request is within rate limit."""
        # Remove requests older than 1 minute
        one_minute_ago = current_time - 60
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if ts > one_minute_ago
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return False
        
        # Record this request
        self.requests[client_ip].append(current_time)
        return True
    
    def _get_remaining_requests(self, client_ip: str, current_time: float) -> int:
        """Get remaining requests for client IP."""
        one_minute_ago = current_time - 60
        recent_requests = [
            ts for ts in self.requests.get(client_ip, []) if ts > one_minute_ago
        ]
        return max(0, self.requests_per_minute - len(recent_requests))
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove entries older than 1 minute to free memory."""
        one_minute_ago = current_time - 60
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                ts for ts in self.requests[ip] if ts > one_minute_ago
            ]
            if not self.requests[ip]:
                del self.requests[ip]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Implements OWASP security best practices.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response with security headers added
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
