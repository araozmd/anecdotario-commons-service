"""
Photo Refresh Lambda Function
Regenerates presigned URLs for protected photo versions
"""
import json
import os

# Add shared directory to path

from anecdotario_commons.decorators import validate_query_or_body, handle_exceptions, cors_enabled, log_request
from anecdotario_commons.services.service_container import get_service
from anecdotario_commons.utils import create_response, create_error_response
from anecdotario_commons.constants import HTTPConstants, TimeConstants
from anecdotario_commons.exceptions import ValidationError
import functools
def photo_refresh_handler(func):
    """Custom composite decorator for photo refresh handler"""
    
    @functools.wraps(func)
    @log_request()
    @cors_enabled(['GET', 'POST'])
    @handle_exceptions()
    @validate_query_or_body([])  # No required fields - conditional validation
    def wrapper(event, context):
        return func(event, context)
    
    return wrapper
@photo_refresh_handler
def lambda_handler(event, context):
    """
    Photo URL refresh handler supporting three operation modes
    
    Mode 1 - Refresh by photo ID:
    {"photo_id": "photo_123", "expires_in": 604800}
    
    Mode 2 - Refresh entity photos:
    {"entity_type": "user", "entity_id": "john", "photo_type": "profile", "expires_in": 604800}
    
    Mode 3 - Get current photo:
    {"entity_type": "user", "entity_id": "john", "photo_type": "profile", "get_current": true}
    """
    # Get parameters from query or body (handled by decorator)
    params = event.get('parsed_params', {})
    
    # Extract parameters
    photo_id = params.get('photo_id')
    entity_type = params.get('entity_type')
    entity_id = params.get('entity_id')
    photo_type = params.get('photo_type', 'profile')
    get_current = params.get('get_current', '').lower() in ('true', '1', 'yes')
    
    # Parse and validate expires_in
    expires_in = _parse_expires_in(params.get('expires_in'))
    
    # Get photo service from container (dependency injection)
    photo_service = get_service('photo_service')
    
    try:
        if photo_id:
            # Mode 1: Refresh specific photo by ID
            print(f"Refreshing photo by ID: {photo_id}")
            
            try:
                result = photo_service.refresh_photo_urls(photo_id)
                
                response_data = {
                    'success': True,
                    'message': 'Photo URLs refreshed successfully',
                    'photo_id': photo_id,
                    'urls': result['urls'],
                    'expires_in': expires_in or TimeConstants.MAX_PRESIGNED_URL_EXPIRY,
                    'generated_at': result['generated_at']
                }
                
            except ValidationError as e:
                return create_error_response(
                    HTTPConstants.NOT_FOUND,
                    str(e),
                    event,
                    {'photo_id': photo_id}
                )
                
        elif entity_type and entity_id:
            if get_current:
                # Mode 3: Get current photo with fresh URLs
                print(f"Getting current photo: {entity_type}/{entity_id}/{photo_type}")
                
                try:
                    result = photo_service.get_current_entity_photo(
                        entity_type, entity_id, photo_type, expires_in
                    )
                    
                    response_data = {
                        'success': True,
                        'message': 'Current photo retrieved successfully',
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'photo_type': photo_type,
                        'photo': result['photo_info'],
                        'urls': result['urls'],
                        'expires_in': result['expires_in'],
                        'generated_at': result['generated_at']
                    }
                    
                except ValidationError as e:
                    return create_error_response(
                        HTTPConstants.NOT_FOUND,
                        str(e),
                        event,
                        {
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'photo_type': photo_type
                        }
                    )
            else:
                # Mode 2: Refresh entity photos
                print(f"Refreshing entity photos: {entity_type}/{entity_id}/{photo_type or 'all'}")
                
                result = photo_service.refresh_entity_photo_urls(
                    entity_type, entity_id, photo_type, expires_in
                )
                
                if result['photos_found'] == 0:
                    return create_error_response(
                        HTTPConstants.NOT_FOUND,
                        'No photos found for the specified entity',
                        event,
                        {
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'photo_type': photo_type
                        }
                    )
                
                response_data = {
                    'success': True,
                    'message': 'Entity photo URLs refreshed successfully',
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'photo_type': photo_type,
                    'photos_found': result['photos_found'],
                    'photos_refreshed': len(result['photos_refreshed']),
                    'photos': result['photos_refreshed'],
                    'expires_in': expires_in or TimeConstants.MAX_PRESIGNED_URL_EXPIRY,
                    'errors': result['errors'] if result['errors'] else None
                }
        else:
            return create_error_response(
                HTTPConstants.BAD_REQUEST,
                'Must provide either photo_id or entity_type+entity_id',
                event,
                {
                    'usage_mode_1': 'photo_id for single photo refresh',
                    'usage_mode_2': 'entity_type+entity_id for entity photos',
                    'usage_mode_3': 'entity_type+entity_id+get_current=true for current photo'
                }
            )
        
        print(f"Photo refresh completed successfully")
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
        
    except Exception as e:
        print(f"Unexpected error in photo refresh: {str(e)}")
        raise  # Let the decorator handle it
def _parse_expires_in(expires_in_str):
    """
    Parse and validate expires_in parameter
    
    Args:
        expires_in_str: String value of expires_in parameter
        
    Returns:
        Validated expires_in value or None for default
    """
    if not expires_in_str:
        return None
    
    try:
        expires_in = int(expires_in_str)
        
        # Validate expiry time bounds
        if expires_in > TimeConstants.MAX_PRESIGNED_URL_EXPIRY:
            return TimeConstants.MAX_PRESIGNED_URL_EXPIRY
        elif expires_in < TimeConstants.MIN_PRESIGNED_URL_EXPIRY:
            return TimeConstants.MIN_PRESIGNED_URL_EXPIRY
        
        return expires_in
        
    except (ValueError, TypeError):
        return None