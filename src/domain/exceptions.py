class DomainError(Exception):
    """Base exception for domain and service errors."""


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class ValidationError(DomainError):
    """Raised when business validation fails."""
