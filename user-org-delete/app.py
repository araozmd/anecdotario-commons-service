"""
User-Organization Delete Lambda Function
Deletes user or organization data (soft delete by default)
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from decorators import standard_lambda_handler
from services.service_container import get_service
from utils import create_response
from constants import HTTPConstants
from exceptions import EntityNotFoundError


@standard_lambda_handler(
    required_fields=['nickname'],
    entity_validation=False,
    photo_type_validation=False,
    support_query_params=False,
    log_requests=True
)
def lambda_handler(event, context):
    """
    Delete user or organization
    
    Expected request format:
    {
        "nickname": "john_doe",     # Required: entity to delete
        "permanent": false          # Optional: true for hard delete, false for soft delete (default)
    }
    
    Soft delete (default): Sets status to 'inactive', preserves data
    Hard delete: Permanently removes entity from database
    """
    # Extract validated parameters
    params = event['parsed_body']
    
    nickname = params['nickname']
    permanent = params.get('permanent', False)
    
    # Convert permanent to boolean if it's a string
    if isinstance(permanent, str):
        permanent = permanent.lower() in ('true', '1', 'yes')
    
    print(f"Deleting entity: {nickname} (permanent: {permanent})")
    
    # Get user-org service from container (dependency injection)
    user_org_service = get_service('user_org_service')
    
    try:
        # Get entity info before deletion (for logging and response)
        try:
            entity_info = user_org_service.get_entity(nickname)
            entity_type = entity_info.get('user_type', 'unknown')
        except EntityNotFoundError:
            # Entity doesn't exist, but we'll let the delete method handle the error
            entity_type = 'unknown'
        
        # Perform deletion
        result = user_org_service.delete_entity(nickname, permanent=permanent)
        
        deletion_type = 'permanent' if permanent else 'soft'
        print(f"Successfully performed {deletion_type} deletion of {entity_type}: {nickname}")
        
        # Return success response
        if permanent:
            response_data = {
                'success': True,
                'message': f'{entity_type.title()} permanently deleted',
                'nickname': nickname,
                'deletion_type': 'permanent',
                'permanently_deleted': True,
                'deleted_at': result.get('deleted_at')
            }
        else:
            response_data = {
                'success': True,
                'message': f'{entity_type.title()} deactivated',
                'nickname': nickname,
                'deletion_type': 'soft',
                'deactivated': True,
                'status': 'inactive',
                'deactivated_at': result.get('deactivated_at')
            }
        
        # Add any additional result data
        response_data.update(result)
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
        
    except EntityNotFoundError as e:
        print(f"Entity not found for deletion: {str(e)}")
        
        return create_response(
            HTTPConstants.NOT_FOUND,
            json.dumps({
                'success': False,
                'error': str(e),
                'error_type': 'entity_not_found',
                'nickname': nickname
            }),
            event
        )
        
    except Exception as e:
        print(f"Unexpected error deleting entity: {str(e)}")
        raise  # Let the decorator handle it