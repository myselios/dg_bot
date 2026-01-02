"""
Domain Exceptions

Custom exceptions for domain layer errors.
"""


class DomainError(Exception):
    """Base exception for domain errors."""
    pass


class InvalidOrderError(DomainError):
    """Raised when order is in invalid state."""
    pass


class InvalidPositionError(DomainError):
    """Raised when position operation is invalid."""
    pass


class InsufficientFundsError(DomainError):
    """Raised when there are insufficient funds."""
    pass


class RiskLimitExceededError(DomainError):
    """Raised when risk limits are exceeded."""
    pass


class CurrencyMismatchError(DomainError):
    """Raised when currencies don't match."""
    pass
