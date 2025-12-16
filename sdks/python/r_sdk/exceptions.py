"""Exceptions for R CLI SDK."""


class RError(Exception):
    """Base exception for R CLI SDK."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthError(RError):
    """Authentication or authorization error."""

    pass


class RateLimitError(RError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class APIError(RError):
    """General API error."""

    pass
