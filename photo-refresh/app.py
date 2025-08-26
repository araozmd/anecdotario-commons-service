"""
Photo Refresh Lambda Function
Regenerates presigned URLs for protected photo versions
"""
import json
import os
import sys
import boto3

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from config import config
from models.photo import Photo
from utils import create_response, create_error_response

# Initialize AWS clients
s3_client = boto3.client('s3')

# Load configuration
PRESIGNED_URL_EXPIRY = config.get_int_parameter('presigned-url-expiry', 604800)  # 7 days default


def refresh_photo_urls(photo_id: str, expires_in: int = None) -> dict:
    """
    Refresh presigned URLs for a specific photo
    
    Args:
        photo_id: Unique photo identifier
        expires_in: URL expiration time in seconds
        
    Returns:
        Refresh results dict
    """
    if expires_in is None:
        expires_in = PRESIGNED_URL_EXPIRY
    
    result = {
        'photo_found': False,
        'urls_refreshed': {},
        'photo_info': None,
        'errors': []
    }
    
    try:
        # Get photo from database
        photo = Photo.get(photo_id)
        result['photo_found'] = True
        result['photo_info'] = {
            'photo_id': photo.photo_id,
            'entity_type': photo.entity_type,
            'entity_id': photo.entity_id,
            'photo_type': photo.photo_type,
            'versions_count': photo.versions_count
        }
        
        # Generate presigned URLs
        urls = photo.generate_presigned_urls(s3_client, expires_in)
        result['urls_refreshed'] = urls
        
        print(f"Refreshed URLs for photo {photo_id}: {list(urls.keys())}")
        
    except Photo.DoesNotExist:
        result['errors'].append({
            'operation': 'photo_lookup',
            'error': 'Photo not found'
        })
    except Exception as e:
        result['errors'].append({
            'operation': 'url_refresh',
            'error': str(e)
        })
    
    return result


def refresh_entity_photo_urls(entity_type: str, entity_id: str, photo_type: str = None, expires_in: int = None) -> dict:
    """
    Refresh presigned URLs for all photos of an entity
    
    Args:
        entity_type: Type of entity ('user', 'org', etc.)
        entity_id: Entity identifier
        photo_type: Optional photo type filter
        expires_in: URL expiration time in seconds
        
    Returns:
        Refresh results dict
    """
    if expires_in is None:
        expires_in = PRESIGNED_URL_EXPIRY
    
    result = {
        'photos_found': 0,
        'photos_refreshed': [],
        'errors': []
    }
    
    try:
        # Get all photos for the entity
        photos = Photo.get_entity_photos(entity_type, entity_id, photo_type)
        result['photos_found'] = len(photos)
        
        if not photos:
            print(f"No photos found for {entity_type} {entity_id}")
            return result
        
        print(f"Refreshing URLs for {len(photos)} photos")
        
        # Refresh URLs for each photo
        for photo in photos:
            try:
                urls = photo.generate_presigned_urls(s3_client, expires_in)
                result['photos_refreshed'].append({
                    'photo_id': photo.photo_id,
                    'photo_type': photo.photo_type,
                    'urls': urls,
                    'expires_in': expires_in
                })
                print(f"Refreshed URLs for photo {photo.photo_id}")
                
            except Exception as e:
                result['errors'].append({
                    'operation': 'photo_url_refresh',
                    'photo_id': photo.photo_id,
                    'error': str(e)
                })
        
        print(f"URL refresh completed: {len(result['photos_refreshed'])} photos processed")
        
    except Exception as e:
        result['errors'].append({
            'operation': 'entity_url_refresh',
            'error': str(e)
        })
    
    return result


def get_current_entity_photo(entity_type: str, entity_id: str, photo_type: str, expires_in: int = None) -> dict:
    """
    Get the current (most recent) photo for an entity with fresh URLs
    
    Args:
        entity_type: Type of entity ('user', 'org', etc.)
        entity_id: Entity identifier
        photo_type: Photo type ('profile', 'logo', etc.)
        expires_in: URL expiration time in seconds
        
    Returns:
        Current photo info dict
    """
    if expires_in is None:
        expires_in = PRESIGNED_URL_EXPIRY
    
    result = {
        'photo_found': False,
        'photo_info': None,
        'urls': {},
        'errors': []
    }
    
    try:
        # Get current photo
        photo = Photo.get_current_photo(entity_type, entity_id, photo_type)
        
        if not photo:
            return result
        
        result['photo_found'] = True
        result['photo_info'] = photo.to_dict()
        
        # Generate fresh presigned URLs
        urls = photo.generate_presigned_urls(s3_client, expires_in)
        result['urls'] = urls
        
        print(f"Retrieved current {photo_type} for {entity_type} {entity_id}: {photo.photo_id}")
        
    except Exception as e:
        result['errors'].append({
            'operation': 'current_photo_lookup',
            'error': str(e)
        })
    
    return result


def lambda_handler(event, context):
    """
    Photo URL refresh handler
    
    Supports three modes:
    1. Refresh specific photo: {"photo_id": "photo_123", "expires_in": 604800}
    2. Refresh entity photos: {"entity_type": "user", "entity_id": "john", "photo_type": "profile", "expires_in": 604800}
    3. Get current photo: {"entity_type": "user", "entity_id": "john", "photo_type": "profile", "get_current": true}
    """
    try:
        print(f"Photo refresh request received")
        
        # Parse request body or query parameters
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return create_error_response(
                    400,
                    'Invalid JSON in request body',
                    event
                )
        
        # Also check query parameters for GET requests
        query_params = event.get('queryStringParameters') or {}
        
        # Merge body and query parameters (query takes precedence)
        params = {**body, **query_params}
        
        # Extract parameters
        photo_id = params.get('photo_id')
        entity_type = params.get('entity_type')
        entity_id = params.get('entity_id')
        photo_type = params.get('photo_type', 'profile')
        get_current = params.get('get_current', '').lower() in ('true', '1', 'yes')
        
        # Parse expires_in
        expires_in = None
        if params.get('expires_in'):
            try:
                expires_in = int(params['expires_in'])
                # Validate expiry time (max 7 days)
                if expires_in > 604800:
                    expires_in = 604800
                elif expires_in < 300:  # Min 5 minutes
                    expires_in = 300
            except (ValueError, TypeError):
                expires_in = None
        
        if photo_id:
            # Mode 1: Refresh specific photo by ID
            print(f"Refreshing photo by ID: {photo_id}")
            result = refresh_photo_urls(photo_id, expires_in)
            
            if not result['photo_found']:
                error_msg = result['errors'][0].get('error', 'Photo not found') if result['errors'] else 'Photo not found'
                return create_error_response(
                    404,
                    f'Photo not found: {error_msg}',
                    event,
                    {'photo_id': photo_id}
                )
            
            response_data = {
                'message': 'Photo URLs refreshed successfully',
                'photo_id': photo_id,
                'photo_info': result['photo_info'],
                'images': result['urls_refreshed'],
                'expires_in': expires_in or PRESIGNED_URL_EXPIRY,
                'errors': result['errors'] if result['errors'] else None
            }
            
        elif entity_type and entity_id:
            if get_current:
                # Mode 3: Get current photo with fresh URLs
                print(f"Getting current photo: {entity_type}/{entity_id}/{photo_type}")
                result = get_current_entity_photo(entity_type, entity_id, photo_type, expires_in)
                
                if not result['photo_found']:
                    return create_error_response(
                        404,
                        f'No {photo_type} photo found for {entity_type} {entity_id}',
                        event,
                        {'entity_type': entity_type, 'entity_id': entity_id, 'photo_type': photo_type}
                    )
                
                response_data = {
                    'message': 'Current photo retrieved successfully',
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'photo_type': photo_type,
                    'photo': result['photo_info'],
                    'images': result['urls'],
                    'expires_in': expires_in or PRESIGNED_URL_EXPIRY,
                    'errors': result['errors'] if result['errors'] else None
                }
            else:
                # Mode 2: Refresh entity photos
                print(f"Refreshing entity photos: {entity_type}/{entity_id}/{photo_type or 'all'}")
                result = refresh_entity_photo_urls(entity_type, entity_id, photo_type, expires_in)
                
                if result['photos_found'] == 0:
                    return create_error_response(
                        404,
                        'No photos found for the specified entity',
                        event,
                        {'entity_type': entity_type, 'entity_id': entity_id, 'photo_type': photo_type}
                    )
                
                response_data = {
                    'message': 'Entity photo URLs refreshed successfully',
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'photo_type': photo_type,
                    'photos_found': result['photos_found'],
                    'photos_refreshed': len(result['photos_refreshed']),
                    'photos': result['photos_refreshed'],
                    'expires_in': expires_in or PRESIGNED_URL_EXPIRY,
                    'errors': result['errors'] if result['errors'] else None
                }
        else:
            return create_error_response(
                400,
                'Must provide either photo_id or entity_type+entity_id',
                event,
                {'usage': 'POST/GET with {"photo_id": "id"} or {"entity_type": "user", "entity_id": "nickname", "photo_type": "profile"}'}
            )
        
        print(f"Photo refresh completed successfully")
        
        return create_response(
            200,
            json.dumps(response_data),
            event,
            ['GET', 'POST']
        )
        
    except Exception as e:
        print(f"Unexpected error in photo refresh: {str(e)}")
        return create_error_response(
            500,
            'Internal server error',
            event,
            {'details': str(e)}
        )