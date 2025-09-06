"""
Photo Delete Lambda Function
Entity-agnostic photo deletion service for users, orgs, campaigns, etc.
"""
import json
import os

# Add shared directory to path

from anecdotario_commons.decorators import direct_lambda_handler
from anecdotario_commons.services.service_container import get_service
from anecdotario_commons.utils import create_response, create_error_response
from anecdotario_commons.constants import HTTPConstants
from anecdotario_commons.exceptions import ValidationError
@direct_lambda_handler(
    required_fields=[],  # Conditional validation based on operation mode
    entity_validation=False,  # Manual validation based on mode
    log_requests=True
)
def lambda_handler(event, context):
    """
    Photo deletion handler supporting two operation modes
    
    Mode 1 - Delete by photo ID:
    {"photo_id": "photo_123"}
    
    Mode 2 - Delete entity photos:
    {"entity_type": "user", "entity_id": "john", "photo_type": "profile"}
    """
    # Get parameters directly from payload (direct invocation)
    body = event
    
    # Determine deletion mode
    photo_id = body.get('photo_id')
    entity_type = body.get('entity_type')
    entity_id = body.get('entity_id')
    photo_type = body.get('photo_type')
    
    # Get photo service from container (dependency injection)
    photo_service = get_service('photo_service')
    
    try:
        if photo_id:
            # Mode 1: Delete specific photo by ID
            print(f"Deleting photo by ID: {photo_id}")
            
            try:
                result = photo_service.delete_photo_by_id(photo_id)
                
                response_data = {
                    'success': True,
                    'message': 'Photo deleted successfully',
                    'photo_id': photo_id,
                    'deleted_files_count': len(result['deleted_files']),
                    'deleted_files': result['deleted_files'],
                    'errors': result['deletion_errors'] if result['deletion_errors'] else None
                }
                
            except ValidationError as e:
                return create_error_response(
                    HTTPConstants.NOT_FOUND,
                    str(e),
                    event,
                    {'photo_id': photo_id}
                )
                
        elif entity_type and entity_id:
            # Mode 2: Delete entity photos
            print(f"Deleting entity photos: {entity_type}/{entity_id}/{photo_type or 'all'}")
            
            result = photo_service.delete_entity_photos(entity_type, entity_id, photo_type)
            
            if result['photos_deleted'] == 0 and not result['deletion_errors']:
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
                'message': 'Entity photos deleted successfully',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'photo_type': photo_type,
                'photos_deleted': result['photos_deleted'],
                'deleted_files_count': len(result['s3_files_deleted']),
                'deleted_files': result['s3_files_deleted'],
                'photos_processed': result['photos_processed'],
                'errors': result['deletion_errors'] if result['deletion_errors'] else None
            }
            
        else:
            return create_error_response(
                HTTPConstants.BAD_REQUEST,
                'Must provide either photo_id or entity_type+entity_id',
                event,
                {
                    'usage_mode_1': 'POST with {"photo_id": "id"}',
                    'usage_mode_2': 'POST with {"entity_type": "user", "entity_id": "nickname"}'
                }
            )
        
        print(f"Photo deletion completed successfully")
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
        
    except Exception as e:
        print(f"Unexpected error in photo deletion: {str(e)}")
        raise  # Let the decorator handle it