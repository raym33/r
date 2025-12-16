"""
Rate limiting middleware for R CLI API.

Provides token bucket rate limiting with configurable limits per client.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int  # Maximum tokens
    refill_rate: float  # Tokens per second
    tokens: float = field(default=0)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Returns True if successful, False if rate limited.
        """
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_retry_after(self, tokens: int = 1) -> float:
        """Get seconds until enough tokens are available."""
        self._refill()
        if self.tokens >= tokens:
            return 0
        needed = tokens - self.tokens
        return needed / self.refill_rate


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Requests per minute for different tiers
    requests_per_minute: int = 60
    requests_per_hour: int = 1000

    # Burst capacity (allows short bursts over the limit)
    burst_multiplier: float = 1.5

    # Cost multipliers for different operations
    chat_cost: int = 1
    chat_stream_cost: int = 2
    tool_call_cost: int = 3

    # Separate limits for heavy operations
    heavy_requests_per_minute: int = 10

    @property
    def tokens_per_second(self) -> float:
        """Calculate token refill rate."""
        return self.requests_per_minute / 60.0

    @property
    def bucket_capacity(self) -> int:
        """Calculate bucket capacity with burst."""
        return int(self.requests_per_minute * self.burst_multiplier)


# Default configurations for different tiers
RATE_LIMIT_TIERS: dict[str, RateLimitConfig] = {
    "free": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        heavy_requests_per_minute=5,
    ),
    "standard": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        heavy_requests_per_minute=10,
    ),
    "premium": RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=5000,
        heavy_requests_per_minute=30,
    ),
    "unlimited": RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=100000,
        heavy_requests_per_minute=100,
    ),
}


class RateLimiter:
    """Rate limiter with per-client buckets."""

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        self.default_config = default_config or RATE_LIMIT_TIERS["standard"]
        self.buckets: dict[str, TokenBucket] = {}
        self.heavy_buckets: dict[str, TokenBucket] = {}
        self.client_configs: dict[str, RateLimitConfig] = {}

    def get_bucket(self, client_id: str) -> TokenBucket:
        """Get or create a bucket for a client."""
        if client_id not in self.buckets:
            config = self.client_configs.get(client_id, self.default_config)
            self.buckets[client_id] = TokenBucket(
                capacity=config.bucket_capacity,
                refill_rate=config.tokens_per_second,
            )
        return self.buckets[client_id]

    def get_heavy_bucket(self, client_id: str) -> TokenBucket:
        """Get or create a heavy operation bucket for a client."""
        if client_id not in self.heavy_buckets:
            config = self.client_configs.get(client_id, self.default_config)
            self.heavy_buckets[client_id] = TokenBucket(
                capacity=int(config.heavy_requests_per_minute * 1.5),
                refill_rate=config.heavy_requests_per_minute / 60.0,
            )
        return self.heavy_buckets[client_id]

    def set_client_config(self, client_id: str, config: RateLimitConfig):
        """Set custom config for a client."""
        self.client_configs[client_id] = config
        # Reset buckets to apply new config
        self.buckets.pop(client_id, None)
        self.heavy_buckets.pop(client_id, None)

    def set_client_tier(self, client_id: str, tier: str):
        """Set client to a predefined tier."""
        if tier in RATE_LIMIT_TIERS:
            self.set_client_config(client_id, RATE_LIMIT_TIERS[tier])

    def check_rate_limit(
        self,
        client_id: str,
        cost: int = 1,
        heavy: bool = False,
    ) -> tuple[bool, Optional[float]]:
        """
        Check if request is allowed.

        Returns:
            (allowed, retry_after) - retry_after is seconds until next allowed request
        """
        bucket = self.get_heavy_bucket(client_id) if heavy else self.get_bucket(client_id)

        if bucket.consume(cost):
            return True, None
        else:
            retry_after = bucket.get_retry_after(cost)
            return False, retry_after

    def get_remaining(self, client_id: str) -> dict:
        """Get remaining rate limit info for a client."""
        bucket = self.get_bucket(client_id)
        heavy_bucket = self.get_heavy_bucket(client_id)
        config = self.client_configs.get(client_id, self.default_config)

        bucket._refill()
        heavy_bucket._refill()

        return {
            "remaining": int(bucket.tokens),
            "limit": config.requests_per_minute,
            "reset_seconds": (config.bucket_capacity - bucket.tokens) / config.tokens_per_second,
            "heavy_remaining": int(heavy_bucket.tokens),
            "heavy_limit": config.heavy_requests_per_minute,
        }

    def cleanup_old_buckets(self, max_age_seconds: int = 3600):
        """Remove buckets that haven't been used recently."""
        now = time.time()
        to_remove = []

        for client_id, bucket in self.buckets.items():
            if now - bucket.last_refill > max_age_seconds:
                to_remove.append(client_id)

        for client_id in to_remove:
            self.buckets.pop(client_id, None)
            self.heavy_buckets.pop(client_id, None)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Paths that are considered heavy operations
HEAVY_PATHS = {
    "/v1/chat",
    "/v1/skills/call",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or get_rate_limiter()

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Try to get from auth header (API key or JWT subject)
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")

        if api_key:
            return f"key:{api_key[:16]}"  # Use prefix of API key

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return f"jwt:{token[:16]}"  # Use prefix of token

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _get_cost(self, request: Request) -> tuple[int, bool]:
        """Get the cost of this request and whether it's heavy."""
        path = request.url.path
        method = request.method

        # Check if heavy operation
        is_heavy = path in HEAVY_PATHS and method == "POST"

        # Determine cost
        cost = 1
        if path == "/v1/chat":
            # Check if streaming (would need to parse body, simplified here)
            cost = 2
        elif path == "/v1/skills/call":
            cost = 3

        return cost, is_heavy

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/", "/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        client_id = self._get_client_id(request)
        cost, is_heavy = self._get_cost(request)

        allowed, retry_after = self.rate_limiter.check_rate_limit(
            client_id, cost=cost, heavy=is_heavy
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                    "message": f"Too many requests. Please wait {retry_after:.1f} seconds.",
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        # Add rate limit headers to response
        response = await call_next(request)

        remaining = self.rate_limiter.get_remaining(client_id)
        response.headers["X-RateLimit-Limit"] = str(remaining["limit"])
        response.headers["X-RateLimit-Remaining"] = str(remaining["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(remaining["reset_seconds"]))

        return response


def rate_limit_dependency(
    cost: int = 1,
    heavy: bool = False,
):
    """
    Create a FastAPI dependency for rate limiting specific endpoints.

    Usage:
        @app.post("/expensive", dependencies=[Depends(rate_limit_dependency(cost=5))])
        async def expensive_endpoint():
            ...
    """

    async def check_rate_limit(request: Request):
        rate_limiter = get_rate_limiter()

        # Get client ID from request
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")

        if api_key:
            client_id = f"key:{api_key[:16]}"
        elif auth_header.startswith("Bearer "):
            client_id = f"jwt:{auth_header[7:23]}"
        else:
            client_host = request.client.host if request.client else "unknown"
            client_id = f"ip:{client_host}"

        allowed, retry_after = rate_limiter.check_rate_limit(client_id, cost=cost, heavy=heavy)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    return check_rate_limit
