"""
Application exceptions.
"""

from typing import Any, Optional


class DhaagaException(Exception):
    """Base exception for all Dhaaga errors."""

    def __init__(self, message: str, code: str = "unknown_error", details: Optional[Any] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class ConfigurationError(DhaagaException):
    """Configuration/environment error."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, "configuration_error", details)


class DatabaseError(DhaagaException):
    """Database operation error."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, "database_error", details)


class ExternalServiceError(DhaagaException):
    """External service (Shopify, LLM, Redis) error."""

    def __init__(self, message: str, service: str, details: Optional[Any] = None):
        details = details or {}
        details["service"] = service
        super().__init__(message, "external_service_error", details)


class ValidationError(DhaagaException):
    """Input validation error."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Any] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, "validation_error", details)


class NotFoundError(DhaagaException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str, details: Optional[Any] = None):
        details = details or {}
        details["resource"] = resource
        details["identifier"] = identifier
        super().__init__(
            f"{resource} not found: {identifier}",
            "not_found",
            details,
        )
