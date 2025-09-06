"""
Decorators for Lambda function validation and error handling
Reduces code duplication and provides consistent validation patterns
"""
import json
import functools
from typing import List, Dict, Any, Callable, Optional, Union
from .constants import HTTPConstants, ErrorMessages, EntityConstants
from .exceptions import ValidationError, CommonsServiceError, ERROR_CODE_MAPPING
from .utils import create_response, create_error_response
from .error_handler import get_error_handler
from .logger import get_logger
import logging
import time

logger = logging.getLogger(__name__)


def validate_request_body(required_fields: List[str], optional_fields: Optional[List[str]] = None):
    """
    Decorator to validate Lambda request body and extract fields
    
    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Decorator function that validates and injects parsed body
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                # Check for request body
                if not event.get('body'):
                    return create_error_response(
                        HTTPConstants.BAD_REQUEST,
                        ErrorMessages.NO_BODY,
                        event
                    )
                
                # Parse JSON body
                try:
                    body = json.loads(event['body'])
                except json.JSONDecodeError:
                    return create_error_response(
                        HTTPConstants.BAD_REQUEST,
                        ErrorMessages.INVALID_JSON,
                        event
                    )
                
                # Validate required fields
                for field in required_fields:
                    if not body.get(field):
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            ErrorMessages.MISSING_FIELD.format(field=field),
                            event,
                            {'missing_field': field, 'required_fields': required_fields}
                        )
                
                # Inject parsed body into event
                event['parsed_body'] = body
                
                return func(event, context)
                
            except Exception as e:
                logger.error(f"Request validation error: {str(e)}")
                return create_error_response(
                    HTTPConstants.INTERNAL_SERVER_ERROR,
                    ErrorMessages.INTERNAL_ERROR,
                    event
                )
        
        return wrapper
    return decorator


def validate_query_or_body(required_fields: List[str], optional_fields: Optional[List[str]] = None):
    """
    Decorator to validate Lambda request supporting both query parameters and body
    
    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Decorator function that validates and injects parsed parameters
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                params = {}
                
                # Try to parse body first
                if event.get('body'):
                    try:
                        params = json.loads(event['body'])
                    except json.JSONDecodeError:
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            ErrorMessages.INVALID_JSON,
                            event
                        )
                
                # Merge with query parameters (query takes precedence)
                query_params = event.get('queryStringParameters') or {}
                params.update(query_params)
                
                # Validate required fields
                for field in required_fields:
                    if not params.get(field):
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            ErrorMessages.MISSING_FIELD.format(field=field),
                            event,
                            {'missing_field': field, 'required_fields': required_fields}
                        )
                
                # Inject parsed parameters into event
                event['parsed_params'] = params
                
                return func(event, context)
                
            except Exception as e:
                logger.error(f"Parameter validation error: {str(e)}")
                return create_error_response(
                    HTTPConstants.INTERNAL_SERVER_ERROR,
                    ErrorMessages.INTERNAL_ERROR,
                    event
                )
        
        return wrapper
    return decorator


def validate_entity_type(valid_types: Optional[List[str]] = None):
    """
    Decorator to validate entity_type parameter
    
    Args:
        valid_types: List of valid entity types (defaults to all supported types)
        
    Returns:
        Decorator function that validates entity_type
    """
    if valid_types is None:
        valid_types = EntityConstants.VALID_ENTITY_TYPES
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Get entity_type from parsed params or body
            params = event.get('parsed_params') or event.get('parsed_body', {})
            entity_type = params.get('entity_type', '').lower()
            
            if entity_type not in valid_types:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    ErrorMessages.INVALID_ENTITY_TYPE.format(valid_types=', '.join(valid_types)),
                    event,
                    {'invalid_value': entity_type, 'valid_types': valid_types}
                )
            
            # Normalize entity_type in params
            params['entity_type'] = entity_type
            
            return func(event, context)
        
        return wrapper
    return decorator


def validate_photo_type():
    """
    Decorator to validate photo_type parameter based on entity_type
    
    Returns:
        Decorator function that validates photo_type
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Get parameters from parsed params or body
            params = event.get('parsed_params') or event.get('parsed_body', {})
            entity_type = params.get('entity_type')
            photo_type = params.get('photo_type')
            
            if not photo_type:
                # photo_type might be optional for some operations
                return func(event, context)
            
            valid_types = EntityConstants.VALID_PHOTO_TYPES.get(entity_type, [])
            if photo_type not in valid_types:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    ErrorMessages.INVALID_PHOTO_TYPE.format(
                        entity_type=entity_type,
                        valid_types=', '.join(valid_types)
                    ),
                    event,
                    {'invalid_value': photo_type, 'valid_types': valid_types}
                )
            
            return func(event, context)
        
        return wrapper
    return decorator


def handle_exceptions(include_traceback: bool = False, operation: str = None):
    """
    Decorator to handle exceptions consistently across Lambda functions
    
    Args:
        include_traceback: Whether to include traceback in error response (dev only)
        
    Returns:
        Decorator function that handles exceptions
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                return func(event, context)
            
            except Exception as e:
                # Use centralized error handler
                error_handler = get_error_handler(include_traceback)
                return error_handler.handle_exception(e, event, context, operation)
        
        return wrapper
    return decorator


def log_request(log_body: bool = False, log_response: bool = False, operation: str = None):
    """
    Decorator to log Lambda requests and responses
    
    Args:
        log_body: Whether to log request body (be careful with sensitive data)
        log_response: Whether to log response body
        
    Returns:
        Decorator function that logs requests/responses
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Use structured logger
            structured_logger = get_logger(func.__module__)
            
            # Set request context
            structured_logger.set_context(
                function_name=getattr(context, 'function_name', 'unknown'),
                request_id=getattr(context, 'aws_request_id', 'unknown'),
                operation=operation
            )
            
            # Log request start with performance timing
            start_time = time.time()
            structured_logger.log_request_start(event, context)
            
            try:
                # Execute function
                response = func(event, context)
                
                # Calculate duration and log completion
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_request_end(response, duration_ms, context)
                
                # Log performance metrics
                structured_logger.log_performance_metric(
                    'request_duration_ms',
                    duration_ms,
                    'milliseconds',
                    operation=operation or 'unknown'
                )
                
                return response
                
            except Exception as e:
                # Log error with timing
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.error(f"Request failed: {str(e)}", 
                                      duration_ms=duration_ms,
                                      error_type=type(e).__name__)
                raise
            finally:
                # Clear request context
                structured_logger.clear_context()
        
        return wrapper
    return decorator


def cors_enabled(allowed_methods: Optional[List[str]] = None, allowed_origins: str = '*'):
    """
    Decorator to add CORS headers to responses
    
    Args:
        allowed_methods: List of allowed HTTP methods
        allowed_origins: Allowed origins (default: '*')
        
    Returns:
        Decorator function that adds CORS headers
    """
    if allowed_methods is None:
        allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Handle preflight OPTIONS request
            if event.get('httpMethod') == 'OPTIONS':
                return {
                    'statusCode': HTTPConstants.OK,
                    'headers': {
                        'Access-Control-Allow-Origin': allowed_origins,
                        'Access-Control-Allow-Methods': ', '.join(allowed_methods),
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
                        'Access-Control-Allow-Credentials': 'true'
                    },
                    'body': ''
                }
            
            # Execute function and add CORS headers to response
            response = func(event, context)
            
            if 'headers' not in response:
                response['headers'] = {}
            
            response['headers'].update({
                'Access-Control-Allow-Origin': allowed_origins,
                'Access-Control-Allow-Methods': ', '.join(allowed_methods),
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
                'Access-Control-Allow-Credentials': 'true'
            })
            
            return response
        
        return wrapper
    return decorator


# Direct invocation decorators for internal microservice communication
def validate_direct_payload(required_fields: List[str], optional_fields: Optional[List[str]] = None):
    """
    Decorator to validate direct Lambda invocation payload (no API Gateway transformation)
    
    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names (for documentation)
        
    Returns:
        Decorator function that validates direct payload fields
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                # For direct invocation, event IS the payload (no body parsing needed)
                if not isinstance(event, dict):
                    return create_error_response(
                        HTTPConstants.BAD_REQUEST,
                        "Invalid payload format - expected JSON object",
                        event
                    )
                
                # Validate required fields
                for field in required_fields:
                    if not event.get(field):
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            ErrorMessages.MISSING_FIELD.format(field=field),
                            event,
                            {'missing_field': field, 'required_fields': required_fields}
                        )
                
                # Inject validated payload (event is already the payload)
                event['validated_payload'] = event
                
                return func(event, context)
                
            except Exception as e:
                logger.error(f"Direct payload validation error: {str(e)}")
                return create_error_response(
                    HTTPConstants.INTERNAL_SERVER_ERROR,
                    ErrorMessages.INTERNAL_ERROR,
                    event
                )
        
        return wrapper
    return decorator


def validate_direct_entity_type(valid_types: Optional[List[str]] = None):
    """
    Decorator to validate entity_type parameter from direct invocation payload
    
    Args:
        valid_types: List of valid entity types (defaults to all supported types)
        
    Returns:
        Decorator function that validates entity_type
    """
    if valid_types is None:
        valid_types = EntityConstants.VALID_ENTITY_TYPES
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Get entity_type directly from event (direct invocation payload)
            entity_type = event.get('entity_type', '').lower()
            
            if entity_type not in valid_types:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    ErrorMessages.INVALID_ENTITY_TYPE.format(valid_types=', '.join(valid_types)),
                    event,
                    {'invalid_value': entity_type, 'valid_types': valid_types}
                )
            
            # Normalize entity_type in payload
            event['entity_type'] = entity_type
            
            return func(event, context)
        
        return wrapper
    return decorator


def validate_direct_photo_type():
    """
    Decorator to validate photo_type parameter from direct invocation payload based on entity_type
    
    Returns:
        Decorator function that validates photo_type
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Get parameters directly from event (direct invocation payload)
            entity_type = event.get('entity_type')
            photo_type = event.get('photo_type')
            
            if not photo_type:
                # photo_type might be optional for some operations
                return func(event, context)
            
            valid_types = EntityConstants.VALID_PHOTO_TYPES.get(entity_type, [])
            if photo_type not in valid_types:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    ErrorMessages.INVALID_PHOTO_TYPE.format(
                        entity_type=entity_type,
                        valid_types=', '.join(valid_types)
                    ),
                    event,
                    {'invalid_value': photo_type, 'valid_types': valid_types}
                )
            
            return func(event, context)
        
        return wrapper
    return decorator


def direct_lambda_handler(required_fields: List[str], 
                         entity_validation: bool = True,
                         photo_type_validation: bool = False,
                         log_requests: bool = True,
                         valid_entity_types: Optional[List[str]] = None):
    """
    Composite decorator for direct Lambda invocation handlers (internal microservice communication)
    
    This decorator is designed for Lambda-to-Lambda invocation only, not API Gateway events.
    No CORS, no body parsing, no query parameters - just direct JSON payload validation.
    
    Args:
        required_fields: Required payload fields
        entity_validation: Whether to validate entity_type
        photo_type_validation: Whether to validate photo_type
        log_requests: Whether to log requests
        valid_entity_types: Valid entity types (defaults to all)
    
    Returns:
        Composite decorator for direct invocation
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in reverse order (outermost first)
        decorated_func = func
        
        # Core validation - direct payload
        decorated_func = validate_direct_payload(required_fields)(decorated_func)
        
        # Entity validation
        if entity_validation:
            decorated_func = validate_direct_entity_type(valid_entity_types)(decorated_func)
        
        # Photo type validation
        if photo_type_validation:
            decorated_func = validate_direct_photo_type()(decorated_func)
        
        # Exception handling
        decorated_func = handle_exceptions(operation='direct_lambda_invocation')(decorated_func)
        
        # Logging (no CORS for internal communication)
        if log_requests:
            decorated_func = log_request(operation='direct_lambda_invocation')(decorated_func)
        
        return decorated_func
    
    return decorator


# Commonly used decorator combinations
def flexible_lambda_handler(conditional_validation: bool = True,
                           log_requests: bool = True):
    """
    Flexible decorator for Lambda handlers with conditional validation
    Useful for handlers that support multiple operation modes
    
    Args:
        conditional_validation: Whether to allow conditional field validation
        log_requests: Whether to log requests
        
    Returns:
        Composite decorator
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in reverse order (outermost first)
        decorated_func = func
        
        # Basic request body parsing (no field validation)
        decorated_func = validate_request_body([])(decorated_func)
        
        # Exception handling
        decorated_func = handle_exceptions(operation='flexible_lambda_request')(decorated_func)
        
        # CORS
        decorated_func = cors_enabled()(decorated_func)
        
        # Logging
        if log_requests:
            decorated_func = log_request(operation='flexible_lambda_request')(decorated_func)
        
        return decorated_func
    
    return decorator


def standard_lambda_handler(required_fields: List[str], 
                           entity_validation: bool = True,
                           photo_type_validation: bool = False,
                           support_query_params: bool = False,
                           log_requests: bool = True):
    """
    Composite decorator for standard Lambda handler validation
    
    Args:
        required_fields: Required request fields
        entity_validation: Whether to validate entity_type
        photo_type_validation: Whether to validate photo_type
        support_query_params: Whether to support query parameters
        log_requests: Whether to log requests
    
    Returns:
        Composite decorator
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in reverse order (outermost first)
        decorated_func = func
        
        # Core validation
        if support_query_params:
            decorated_func = validate_query_or_body(required_fields)(decorated_func)
        else:
            decorated_func = validate_request_body(required_fields)(decorated_func)
        
        # Entity validation
        if entity_validation:
            decorated_func = validate_entity_type()(decorated_func)
        
        # Photo type validation
        if photo_type_validation:
            decorated_func = validate_photo_type()(decorated_func)
        
        # Exception handling
        decorated_func = handle_exceptions(operation='standard_lambda_request')(decorated_func)
        
        # CORS
        decorated_func = cors_enabled()(decorated_func)
        
        # Logging
        if log_requests:
            decorated_func = log_request(operation='standard_lambda_request')(decorated_func)
        
        return decorated_func
    
    return decorator
