"""
Centralized error handling system for the commons service
Provides consistent error logging, monitoring, and response formatting
"""
import json
import traceback
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from .constants import HTTPConstants, ErrorMessages
from .exceptions import CommonsServiceError, ERROR_CODE_MAPPING
from .utils import create_error_response

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Centralized error handler providing consistent error processing,
    logging, and response generation across all Lambda functions
    """
    
    def __init__(self, include_traceback: bool = False, enable_monitoring: bool = True):
        """
        Initialize error handler
        
        Args:
            include_traceback: Whether to include traceback in responses (dev only)
            enable_monitoring: Whether to enable error monitoring/alerting
        """
        self.include_traceback = include_traceback
        self.enable_monitoring = enable_monitoring
        
        # Configure logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def handle_exception(self, 
                        exception: Exception, 
                        event: Dict[str, Any], 
                        context: Any = None,
                        operation: str = None) -> Dict[str, Any]:
        """
        Handle exception and generate appropriate response
        
        Args:
            exception: The exception that occurred
            event: Lambda event object
            context: Lambda context object (optional)
            operation: Description of operation that failed (optional)
            
        Returns:
            Lambda response dictionary
        """
        error_id = self._generate_error_id()
        
        # Extract error details
        error_type, status_code, message, details = self._extract_error_details(exception)
        
        # Add context information
        context_info = self._extract_context_info(event, context, operation)
        details.update(context_info)
        details['error_id'] = error_id
        
        # Log the error
        self._log_error(exception, error_id, context_info, operation)
        
        # Send monitoring alert if enabled
        if self.enable_monitoring:
            self._send_monitoring_alert(exception, error_id, context_info)
        
        # Include traceback if requested (dev environment)
        if self.include_traceback:
            details['traceback'] = traceback.format_exc()
        
        return create_error_response(status_code, message, event, details)
    
    def handle_validation_error(self, 
                               field_errors: Dict[str, str], 
                               event: Dict[str, Any],
                               operation: str = None) -> Dict[str, Any]:
        """
        Handle validation errors with detailed field-specific messages
        
        Args:
            field_errors: Dictionary of field -> error message mappings
            event: Lambda event object
            operation: Description of operation that failed (optional)
            
        Returns:
            Lambda response dictionary
        """
        error_id = self._generate_error_id()
        
        details = {
            'error_id': error_id,
            'field_errors': field_errors,
            'total_errors': len(field_errors)
        }
        
        # Add operation context
        if operation:
            details['operation'] = operation
        
        # Create user-friendly message
        field_names = list(field_errors.keys())
        if len(field_names) == 1:
            message = f"Validation failed for field: {field_names[0]}"
        else:
            message = f"Validation failed for {len(field_names)} fields: {', '.join(field_names)}"
        
        # Log validation error
        logger.warning(f"Validation error [{error_id}]: {message}", extra={
            'error_id': error_id,
            'field_errors': field_errors,
            'operation': operation
        })
        
        return create_error_response(HTTPConstants.BAD_REQUEST, message, event, details)
    
    def handle_not_found_error(self, 
                              resource_type: str, 
                              resource_id: str, 
                              event: Dict[str, Any],
                              suggestions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle resource not found errors with helpful suggestions
        
        Args:
            resource_type: Type of resource (photo, entity, etc.)
            resource_id: ID of the resource that wasn't found
            event: Lambda event object
            suggestions: Optional suggestions for resolving the issue
            
        Returns:
            Lambda response dictionary
        """
        error_id = self._generate_error_id()
        
        message = f"{resource_type.title()} not found: {resource_id}"
        
        details = {
            'error_id': error_id,
            'resource_type': resource_type,
            'resource_id': resource_id
        }
        
        if suggestions:
            details['suggestions'] = suggestions
        
        logger.info(f"Resource not found [{error_id}]: {message}", extra=details)
        
        return create_error_response(HTTPConstants.NOT_FOUND, message, event, details)
    
    def _extract_error_details(self, exception: Exception) -> Tuple[str, int, str, Dict[str, Any]]:
        """
        Extract error type, status code, message, and details from exception
        
        Args:
            exception: The exception to analyze
            
        Returns:
            Tuple of (error_type, status_code, message, details)
        """
        error_type = type(exception).__name__
        
        if isinstance(exception, CommonsServiceError):
            # Custom service exceptions
            status_code = ERROR_CODE_MAPPING.get(type(exception), HTTPConstants.INTERNAL_SERVER_ERROR)
            message = exception.message
            details = exception.details.copy()
        else:
            # Generic exceptions
            status_code = HTTPConstants.INTERNAL_SERVER_ERROR
            message = ErrorMessages.INTERNAL_ERROR
            details = {'original_error': str(exception)}
        
        details['error_type'] = error_type
        return error_type, status_code, message, details
    
    def _extract_context_info(self, 
                             event: Dict[str, Any], 
                             context: Any = None, 
                             operation: str = None) -> Dict[str, Any]:
        """
        Extract context information for error logging
        
        Args:
            event: Lambda event object
            context: Lambda context object
            operation: Operation description
            
        Returns:
            Context information dictionary
        """
        context_info = {
            'timestamp': datetime.utcnow().isoformat(),
            'http_method': event.get('httpMethod'),
            'path': event.get('path'),
            'user_agent': event.get('headers', {}).get('User-Agent'),
            'source_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp')
        }
        
        if context:
            context_info.update({
                'function_name': getattr(context, 'function_name', 'unknown'),
                'request_id': getattr(context, 'aws_request_id', 'unknown'),
                'memory_limit': getattr(context, 'memory_limit_in_mb', 'unknown'),
                'remaining_time': getattr(context, 'get_remaining_time_in_millis', lambda: 0)()
            })
        
        if operation:
            context_info['operation'] = operation
        
        # Remove None values
        return {k: v for k, v in context_info.items() if v is not None}
    
    def _generate_error_id(self) -> str:
        """
        Generate unique error ID for tracking
        
        Returns:
            Unique error identifier
        """
        from uuid import uuid4
        return f"err_{uuid4().hex[:8]}"
    
    def _log_error(self, 
                   exception: Exception, 
                   error_id: str, 
                   context_info: Dict[str, Any],
                   operation: str = None):
        """
        Log error with structured information
        
        Args:
            exception: The exception that occurred
            error_id: Unique error identifier
            context_info: Context information
            operation: Operation description
        """
        log_data = {
            'error_id': error_id,
            'error_type': type(exception).__name__,
            'error_message': str(exception),
            'operation': operation,
            **context_info
        }
        
        if isinstance(exception, CommonsServiceError):
            # Service errors are expected - log as warning
            logger.warning(f"Service error [{error_id}]: {exception.message}", extra=log_data)
        else:
            # Unexpected errors - log as error with traceback
            logger.error(f"Unexpected error [{error_id}]: {str(exception)}", extra=log_data, exc_info=True)
    
    def _send_monitoring_alert(self, 
                              exception: Exception, 
                              error_id: str, 
                              context_info: Dict[str, Any]):
        """
        Send monitoring alert for critical errors
        
        Args:
            exception: The exception that occurred
            error_id: Unique error identifier
            context_info: Context information
        """
        # Only alert on unexpected errors
        if not isinstance(exception, CommonsServiceError):
            # In production, this would integrate with CloudWatch, SNS, or other monitoring
            logger.critical(f"ALERT - Unexpected error [{error_id}]: {str(exception)}", extra={
                'alert': True,
                'error_id': error_id,
                'error_type': type(exception).__name__,
                **context_info
            })


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler(include_traceback: bool = False, enable_monitoring: bool = True) -> ErrorHandler:
    """
    Get global error handler instance
    
    Args:
        include_traceback: Whether to include traceback in responses
        enable_monitoring: Whether to enable error monitoring
        
    Returns:
        Global ErrorHandler instance
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler(include_traceback, enable_monitoring)
    
    return _error_handler


def handle_error(exception: Exception, 
                event: Dict[str, Any], 
                context: Any = None,
                operation: str = None) -> Dict[str, Any]:
    """
    Convenience function for handling errors
    
    Args:
        exception: The exception that occurred
        event: Lambda event object
        context: Lambda context object
        operation: Operation description
        
    Returns:
        Lambda response dictionary
    """
    return get_error_handler().handle_exception(exception, event, context, operation)


def handle_validation_error(field_errors: Dict[str, str], 
                          event: Dict[str, Any],
                          operation: str = None) -> Dict[str, Any]:
    """
    Convenience function for handling validation errors
    
    Args:
        field_errors: Dictionary of field -> error message mappings
        event: Lambda event object
        operation: Operation description
        
    Returns:
        Lambda response dictionary
    """
    return get_error_handler().handle_validation_error(field_errors, event, operation)


def handle_not_found_error(resource_type: str, 
                         resource_id: str, 
                         event: Dict[str, Any],
                         suggestions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function for handling not found errors
    
    Args:
        resource_type: Type of resource
        resource_id: ID of the resource
        event: Lambda event object  
        suggestions: Optional suggestions
        
    Returns:
        Lambda response dictionary
    """
    return get_error_handler().handle_not_found_error(resource_type, resource_id, event, suggestions)