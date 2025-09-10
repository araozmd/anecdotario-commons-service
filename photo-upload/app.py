"""
Photo Upload Lambda Function
Entity-agnostic photo upload service for users, orgs, campaigns, etc.
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.decorators import direct_lambda_handler
from shared.services.service_container import get_service
from shared.utils import create_response
from shared.constants import HTTPConstants


@direct_lambda_handler(
    required_fields=['image', 'entity_type', 'entity_id', 'photo_type'],
    entity_validation=True,
    photo_type_validation=True,
    log_requests=True
)
def lambda_handler(event, context):
    """
    Clean photo upload handler using decorators and service layer
    All validation is handled by decorators, business logic is separated
    
    Expected request format:
    {
        "image": "data:image/jpeg;base64,...",
        "entity_type": "user|org|campaign",
        "entity_id": "nickname_or_id",
        "photo_type": "profile|logo|banner|gallery",
        "uploaded_by": "user_id",
        "upload_source": "user-service|org-service"
    }
    """
    # Extract validated parameters directly from payload (decorators guarantee these exist and are valid)
    params = event
    
    image_data = params['image']
    entity_type = params['entity_type']
    entity_id = params['entity_id']
    photo_type = params['photo_type']
    uploaded_by = params.get('uploaded_by')
    upload_source = params.get('upload_source', 'unknown')
    
    print(f"Processing photo upload: {entity_type}/{entity_id}/{photo_type}")
    
    # Get photo service from container (dependency injection)
    photo_service = get_service('photo_service')
    
    # Business logic - delegate to service layer
    result = photo_service.upload_photo(
        image_data=image_data,
        entity_type=entity_type,
        entity_id=entity_id,
        photo_type=photo_type,
        uploaded_by=uploaded_by,
        upload_source=upload_source
    )
    
    # Return success response
    response_data = {
        'success': True,
        'message': 'Photo uploaded successfully',
        'photo_id': result['photo_id'],
        'entity_type': entity_type,
        'entity_id': entity_id,
        'photo_type': photo_type,
        'urls': result['urls'],
        'metadata': result['metadata'],
        'cleanup_result': result.get('cleanup_result', {})
    }
    
    print(f"Photo upload completed successfully: {result['photo_id']}")
    
    return create_response(
        HTTPConstants.OK,
        json.dumps(response_data),
        event
    )

