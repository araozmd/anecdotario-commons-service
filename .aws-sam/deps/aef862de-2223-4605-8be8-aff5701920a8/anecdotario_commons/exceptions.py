"""
Custom exceptions for the commons service
Provides structured error handling and better debugging
"""
from typing import Dict, Any, Optional


class CommonsServiceError(Exception):
    """Base exception for commons service errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization"""
        return {
            'error': self.message,
            'details': self.details,
            'type': self.__class__.__name__
        }


class ValidationError(CommonsServiceError):
    """Raised when input validation fails"""
    pass


class ImageProcessingError(CommonsServiceError):
    """Raised when image processing fails"""
    pass


class StorageError(CommonsServiceError):
    """Raised when storage operations fail"""
    pass


class ConfigurationError(CommonsServiceError):
    """Raised when configuration is invalid or missing"""
    pass


class EntityNotFoundError(CommonsServiceError):
    """Raised when an entity is not found"""
    pass


class DuplicateEntityError(CommonsServiceError):
    """Raised when trying to create a duplicate entity"""
    pass


class PermissionError(CommonsServiceError):
    """Raised when user lacks permission for operation"""
    pass


class RateLimitError(CommonsServiceError):
    """Raised when rate limits are exceeded"""
    pass


# Error code mappings for consistent HTTP status codes
ERROR_CODE_MAPPING = {
    ValidationError: 400,
    ImageProcessingError: 400,
    ConfigurationError: 500,
    EntityNotFoundError: 404,
    DuplicateEntityError: 409,
    PermissionError: 403,
    RateLimitError: 429,
    StorageError: 500,
    CommonsServiceError: 500,
}