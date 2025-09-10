"""
Commons Service Exceptions
Custom exception classes for commons-service operations
"""


class CommonsServiceError(Exception):
    """Base exception for all commons service errors"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses"""
        result = {
            'error': self.__class__.__name__,
            'message': self.message
        }
        if self.error_code:
            result['error_code'] = self.error_code
        if self.details:
            result['details'] = self.details
        return result


class ValidationError(CommonsServiceError):
    """Raised when input validation fails"""
    
    def __init__(self, message: str, field: str = None, value: str = None, hints: list = None):
        self.field = field
        self.value = value
        self.hints = hints or []
        
        details = {}
        if field:
            details['field'] = field
        if value:
            details['value'] = value
        if hints:
            details['hints'] = hints
            
        super().__init__(message, 'VALIDATION_ERROR', details)


class EntityNotFoundError(CommonsServiceError):
    """Raised when an entity is not found"""
    
    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        
        message = f"{entity_type.capitalize()} '{entity_id}' not found"
        details = {
            'entity_type': entity_type,
            'entity_id': entity_id
        }
        
        super().__init__(message, 'ENTITY_NOT_FOUND', details)


class DuplicateEntityError(CommonsServiceError):
    """Raised when attempting to create a duplicate entity"""
    
    def __init__(self, entity_type: str, field: str, value: str):
        self.entity_type = entity_type
        self.field = field
        self.value = value
        
        message = f"{entity_type.capitalize()} with {field} '{value}' already exists"
        details = {
            'entity_type': entity_type,
            'field': field,
            'value': value
        }
        
        super().__init__(message, 'DUPLICATE_ENTITY', details)


class ImageProcessingError(CommonsServiceError):
    """Raised when image processing fails"""
    
    def __init__(self, message: str, operation: str = None, original_error: str = None):
        self.operation = operation
        self.original_error = original_error
        
        details = {}
        if operation:
            details['operation'] = operation
        if original_error:
            details['original_error'] = original_error
            
        super().__init__(message, 'IMAGE_PROCESSING_ERROR', details)


class S3OperationError(CommonsServiceError):
    """Raised when S3 operations fail"""
    
    def __init__(self, message: str, operation: str = None, bucket: str = None, key: str = None):
        self.operation = operation
        self.bucket = bucket
        self.key = key
        
        details = {}
        if operation:
            details['operation'] = operation
        if bucket:
            details['bucket'] = bucket
        if key:
            details['key'] = key
            
        super().__init__(message, 'S3_OPERATION_ERROR', details)


class DynamoDBError(CommonsServiceError):
    """Raised when DynamoDB operations fail"""
    
    def __init__(self, message: str, operation: str = None, table: str = None, original_error: str = None):
        self.operation = operation
        self.table = table
        self.original_error = original_error
        
        details = {}
        if operation:
            details['operation'] = operation
        if table:
            details['table'] = table
        if original_error:
            details['original_error'] = original_error
            
        super().__init__(message, 'DYNAMODB_ERROR', details)


class ConfigurationError(CommonsServiceError):
    """Raised when configuration is invalid or missing"""
    
    def __init__(self, message: str, config_key: str = None, config_source: str = None):
        self.config_key = config_key
        self.config_source = config_source
        
        details = {}
        if config_key:
            details['config_key'] = config_key
        if config_source:
            details['config_source'] = config_source
            
        super().__init__(message, 'CONFIGURATION_ERROR', details)


class AuthenticationError(CommonsServiceError):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 'AUTHENTICATION_ERROR')


class AuthorizationError(CommonsServiceError):
    """Raised when authorization fails"""
    
    def __init__(self, message: str = "Access denied", resource: str = None, action: str = None):
        self.resource = resource
        self.action = action
        
        details = {}
        if resource:
            details['resource'] = resource
        if action:
            details['action'] = action
            
        super().__init__(message, 'AUTHORIZATION_ERROR', details)


class RateLimitExceededError(CommonsServiceError):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", limit: int = None, retry_after: int = None):
        self.limit = limit
        self.retry_after = retry_after
        
        details = {}
        if limit:
            details['limit'] = limit
        if retry_after:
            details['retry_after_seconds'] = retry_after
            
        super().__init__(message, 'RATE_LIMIT_EXCEEDED', details)


class RequestTooLargeError(CommonsServiceError):
    """Raised when request payload is too large"""
    
    def __init__(self, message: str, max_size: int = None, actual_size: int = None):
        self.max_size = max_size
        self.actual_size = actual_size
        
        details = {}
        if max_size:
            details['max_size_bytes'] = max_size
        if actual_size:
            details['actual_size_bytes'] = actual_size
            
        super().__init__(message, 'REQUEST_TOO_LARGE', details)


class ServiceUnavailableError(CommonsServiceError):
    """Raised when a dependent service is unavailable"""
    
    def __init__(self, message: str, service: str = None, retry_after: int = None):
        self.service = service
        self.retry_after = retry_after
        
        details = {}
        if service:
            details['service'] = service
        if retry_after:
            details['retry_after_seconds'] = retry_after
            
        super().__init__(message, 'SERVICE_UNAVAILABLE', details)


class TimeoutError(CommonsServiceError):
    """Raised when an operation times out"""
    
    def __init__(self, message: str, operation: str = None, timeout_seconds: int = None):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        
        details = {}
        if operation:
            details['operation'] = operation
        if timeout_seconds:
            details['timeout_seconds'] = timeout_seconds
            
        super().__init__(message, 'TIMEOUT_ERROR', details)