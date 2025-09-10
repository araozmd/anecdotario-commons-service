"""
Lambda validation decorators for commons-service
"""
import json
import time
from functools import wraps
from typing import List, Optional, Callable, Any
from .constants import HTTPConstants, EntityConstants
from .validation_utils import validate_required_fields
from .utils import create_error_response, validate_entity_type, validate_photo_type
from .logger import logger


def direct_lambda_handler(
    required_fields: List[str] = None,
    entity_validation: bool = False,
    photo_type_validation: bool = False,
    valid_entity_types: List[str] = None,
    valid_photo_types: List[str] = None,
    log_requests: bool = True,
    max_request_size: int = 6 * 1024 * 1024  # 6MB default
):
    """
    Decorator for direct Lambda invocation handlers with comprehensive validation
    
    Args:
        required_fields: List of required fields in the event
        entity_validation: Whether to validate entity_type field
        photo_type_validation: Whether to validate photo_type field
        valid_entity_types: List of valid entity types (default from constants)
        valid_photo_types: List of valid photo types (default from constants)
        log_requests: Whether to log request start/end
        max_request_size: Maximum request size in bytes
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event, context):
            start_time = time.time()
            function_name = getattr(func, '__name__', 'unknown')
            
            if log_requests:
                logger.log_lambda_start(function_name, event, context)
            
            try:
                # Validate request size
                if isinstance(event, dict) and 'image' in event:
                    image_data = event.get('image', '')
                    if len(image_data.encode('utf-8')) > max_request_size:
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Request too large. Maximum size: {max_request_size // (1024*1024)}MB',
                            event
                        )
                
                # Validate required fields
                if required_fields:
                    missing_fields = validate_required_fields(event, required_fields)
                    if missing_fields:
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Missing required fields: {", ".join(missing_fields)}',
                            event,
                            {'missing_fields': missing_fields}
                        )
                
                # Validate entity_type if required
                if entity_validation and 'entity_type' in event:
                    entity_type = event.get('entity_type', '').lower()
                    valid_types = valid_entity_types or EntityConstants.ALL_ENTITY_TYPES
                    
                    if not validate_entity_type(entity_type, valid_types):
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Invalid entity_type. Must be one of: {", ".join(valid_types)}',
                            event,
                            {'valid_entity_types': valid_types}
                        )
                
                # Validate photo_type if required
                if photo_type_validation and 'photo_type' in event:
                    photo_type = event.get('photo_type', '').lower()
                    entity_type = event.get('entity_type', '').lower()
                    
                    if not validate_photo_type(photo_type, entity_type):
                        # Get context-specific valid types
                        if entity_type == 'user':
                            context_valid_types = EntityConstants.USER_PHOTO_TYPES
                        elif entity_type == 'org':
                            context_valid_types = EntityConstants.ORG_PHOTO_TYPES
                        elif entity_type == 'campaign':
                            context_valid_types = EntityConstants.CAMPAIGN_PHOTO_TYPES
                        else:
                            context_valid_types = valid_photo_types or EntityConstants.ALL_PHOTO_TYPES
                        
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Invalid photo_type for {entity_type}. Must be one of: {", ".join(context_valid_types)}',
                            event,
                            {'valid_photo_types': context_valid_types}
                        )
                
                # Call the actual handler
                result = func(event, context)
                
                # Log successful completion
                if log_requests:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_lambda_end(function_name, True, duration_ms)
                
                return result
            
            except ValueError as e:
                # Validation or parsing errors
                if log_requests:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_lambda_end(function_name, False, duration_ms, error=str(e))
                
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    str(e),
                    event
                )
            
            except Exception as e:
                # Unexpected errors
                if log_requests:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_lambda_end(function_name, False, duration_ms, error=str(e))
                
                logger.error(f"Unexpected error in {function_name}", error=e)
                
                return create_error_response(
                    HTTPConstants.INTERNAL_SERVER_ERROR,
                    'Internal server error occurred',
                    event
                )
        
        return wrapper
    return decorator


def api_gateway_handler(
    required_fields: List[str] = None,
    entity_validation: bool = False,
    photo_type_validation: bool = False,
    valid_entity_types: List[str] = None,
    valid_photo_types: List[str] = None,
    log_requests: bool = True,
    require_auth: bool = True
):
    """
    Decorator for API Gateway handlers with JWT validation
    
    Args:
        required_fields: List of required fields in the request body
        entity_validation: Whether to validate entity_type field
        photo_type_validation: Whether to validate photo_type field
        valid_entity_types: List of valid entity types
        valid_photo_types: List of valid photo types
        log_requests: Whether to log request start/end
        require_auth: Whether to require JWT authentication
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event, context):
            start_time = time.time()
            function_name = getattr(func, '__name__', 'unknown')
            
            if log_requests:
                logger.log_lambda_start(function_name, event, context)
            
            try:
                # Parse request body
                body = {}
                if event.get('body'):
                    try:
                        body = json.loads(event['body'])
                    except json.JSONDecodeError:
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            'Invalid JSON in request body',
                            event
                        )
                
                # Extract user claims from JWT (validated by API Gateway)
                user_claims = {}
                if require_auth:
                    request_context = event.get('requestContext', {})
                    authorizer = request_context.get('authorizer', {})
                    user_claims = authorizer.get('claims', {})
                    
                    if not user_claims:
                        return create_error_response(
                            HTTPConstants.UNAUTHORIZED,
                            'Authentication required',
                            event
                        )
                
                # Add parsed body and user claims to event
                event['parsed_body'] = body
                event['user_claims'] = user_claims
                
                # Validate required fields in body
                if required_fields:
                    missing_fields = validate_required_fields(body, required_fields)
                    if missing_fields:
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Missing required fields: {", ".join(missing_fields)}',
                            event,
                            {'missing_fields': missing_fields}
                        )
                
                # Validate entity_type if required
                if entity_validation and 'entity_type' in body:
                    entity_type = body.get('entity_type', '').lower()
                    valid_types = valid_entity_types or EntityConstants.ALL_ENTITY_TYPES
                    
                    if not validate_entity_type(entity_type, valid_types):
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Invalid entity_type. Must be one of: {", ".join(valid_types)}',
                            event,
                            {'valid_entity_types': valid_types}
                        )
                
                # Validate photo_type if required
                if photo_type_validation and 'photo_type' in body:
                    photo_type = body.get('photo_type', '').lower()
                    entity_type = body.get('entity_type', '').lower()
                    
                    if not validate_photo_type(photo_type, entity_type):
                        # Get context-specific valid types
                        if entity_type == 'user':
                            context_valid_types = EntityConstants.USER_PHOTO_TYPES
                        elif entity_type == 'org':
                            context_valid_types = EntityConstants.ORG_PHOTO_TYPES
                        elif entity_type == 'campaign':
                            context_valid_types = EntityConstants.CAMPAIGN_PHOTO_TYPES
                        else:
                            context_valid_types = valid_photo_types or EntityConstants.ALL_PHOTO_TYPES
                        
                        return create_error_response(
                            HTTPConstants.BAD_REQUEST,
                            f'Invalid photo_type for {entity_type}. Must be one of: {", ".join(context_valid_types)}',
                            event,
                            {'valid_photo_types': context_valid_types}
                        )
                
                # Call the actual handler
                result = func(event, context)
                
                # Log successful completion
                if log_requests:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_lambda_end(function_name, True, duration_ms)
                
                return result
            
            except ValueError as e:
                # Validation or parsing errors
                if log_requests:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_lambda_end(function_name, False, duration_ms, error=str(e))
                
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    str(e),
                    event
                )
            
            except Exception as e:
                # Unexpected errors
                if log_requests:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_lambda_end(function_name, False, duration_ms, error=str(e))
                
                logger.error(f"Unexpected error in {function_name}", error=e)
                
                return create_error_response(
                    HTTPConstants.INTERNAL_SERVER_ERROR,
                    'Internal server error occurred',
                    event
                )
        
        return wrapper
    return decorator


def validate_request_size(max_size_mb: int = 6):
    """
    Decorator to validate request size
    
    Args:
        max_size_mb: Maximum request size in megabytes
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event, context):
            max_size_bytes = max_size_mb * 1024 * 1024
            
            # Check image data size if present
            if isinstance(event, dict) and 'image' in event:
                image_data = event.get('image', '')
                if len(image_data.encode('utf-8')) > max_size_bytes:
                    return create_error_response(
                        HTTPConstants.BAD_REQUEST,
                        f'Request too large. Maximum size: {max_size_mb}MB',
                        event
                    )
            
            # Check overall event size
            event_size = len(json.dumps(event).encode('utf-8'))
            if event_size > max_size_bytes:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    f'Request too large. Maximum size: {max_size_mb}MB',
                    event
                )
            
            return func(event, context)
        
        return wrapper
    return decorator


def rate_limit(requests_per_second: float = 10.0):
    """
    Simple rate limiting decorator (per Lambda instance)
    
    Args:
        requests_per_second: Maximum requests per second
    """
    def decorator(func: Callable) -> Callable:
        last_request_time = 0
        min_interval = 1.0 / requests_per_second
        
        @wraps(func)
        def wrapper(event, context):
            nonlocal last_request_time
            
            current_time = time.time()
            time_since_last = current_time - last_request_time
            
            if time_since_last < min_interval:
                return create_error_response(
                    HTTPConstants.TOO_MANY_REQUESTS,
                    'Rate limit exceeded. Please try again later.',
                    event
                )
            
            last_request_time = current_time
            return func(event, context)
        
        return wrapper
    return decorator