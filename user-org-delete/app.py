"""
User-Organization Delete Lambda Function
Deletes user or organization data (soft delete by default)
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.services.service_container import get_service
from shared.utils import create_success_response, create_failure_response
from shared.exceptions import EntityNotFoundError
from datetime import datetime
from typing import Dict, Any, Optional
def validate_input(event: dict) -> Dict[str, Any]:
    """Validate input parameters"""
    # Handle both direct Lambda invocation and API Gateway formats
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")
    else:
        body = event
    
    # Check required fields
    if 'nickname' not in body or not body['nickname']:
        raise ValueError("Missing required field: nickname")
    
    return body


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
    try:
        # Validate input parameters
        params = validate_input(event)
    
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
        deletion_type = 'permanent' if permanent else 'soft'
        
        response_data = {
            'nickname': nickname,
            'deletion_type': deletion_type,
            'entity_type': entity_type,
            'operation': 'delete'
        }
        
        if permanent:
            response_data.update({
                'permanently_deleted': True,
                'deleted_at': result.get('deleted_at')
            })
        else:
            response_data.update({
                'deactivated': True,
                'status': 'inactive',
                'deactivated_at': result.get('deactivated_at')
            })
        
        execution_metadata = {
            'deletion_type': deletion_type,
            'entity_type': entity_type
        }
        
        # Add any additional result data to metadata
        if result:
            execution_metadata.update(result)
        
        print(f"Successfully performed {deletion_type} deletion of {entity_type}: {nickname}")
        return create_success_response(response_data, execution_metadata)
        
    except EntityNotFoundError as e:
        print(f"Entity not found for deletion: {str(e)}")
        
        return create_failure_response(
            "NOT_FOUND",
            str(e),
            {
                'nickname': nickname,
                'operation': 'delete'
            }
        )
        
    except ValueError as e:
        print(f"Input validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "required_fields": ["nickname"],
                "optional_fields": ["permanent"]
            }
        )
    except Exception as e:
        print(f"Unexpected error deleting entity: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Entity deletion failed due to internal error",
            {"error_details": str(e)}
        )