/**
 * Custom errors for R CLI SDK
 */

export class RError extends Error {
  statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = 'RError';
    this.statusCode = statusCode;
  }
}

export class AuthError extends RError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode);
    this.name = 'AuthError';
  }
}

export class RateLimitError extends RError {
  retryAfter?: number;

  constructor(message: string, retryAfter?: number) {
    super(message, 429);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

export class APIError extends RError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode);
    this.name = 'APIError';
  }
}
