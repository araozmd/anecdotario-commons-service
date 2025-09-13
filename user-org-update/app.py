"""
User-Organization Update Lambda Function
Updates user or organization data (nickname and user_type are immutable)
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.services.service_container import get_service
from shared.utils import create_success_response, create_failure_response
from shared.exceptions import ValidationError, EntityNotFoundError
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
    Update user or organization data
    
    Expected request format:
    {
        "nickname": "john_doe",          # Required: identifies the entity to update
        "full_name": "John Doe Updated", # Optional
        "avatar_thumbnail_url": "https://...", # Optional
        "email": "newemail@example.com", # Optional
        "phone": "+1234567890",          # Optional
        "website": "https://newsite.com", # Optional
        
        # Special operations (separate endpoints ideally, but supported here)
        "certification": {               # Optional: update certification
            "is_certified": true,
            "certified_by": "admin_user"
        },
        "stats_update": {                # Optional: update statistics
            "followers_delta": 1,
            "following_delta": 0, 
            "posts_delta": 1
        }
    }
    
    Note: nickname and user_type cannot be changed after creation
    """
    try:
        # Validate input parameters
        params = validate_input(event)
    
    nickname = params['nickname']
    
    # Extract optional update fields
    full_name = params.get('full_name')
    avatar_thumbnail_url = params.get('avatar_thumbnail_url')
    email = params.get('email')
    phone = params.get('phone')
    website = params.get('website')
    
    # Special operations
    certification = params.get('certification')
    stats_update = params.get('stats_update')
    
    print(f"Updating entity: {nickname}")
    
    # Get user-org service from container (dependency injection)
    user_org_service = get_service('user_org_service')
    
    try:
        # Prepare updates dictionary with only non-None values
        updates = {}
        if full_name is not None:
            updates['full_name'] = full_name
        if avatar_thumbnail_url is not None:
            updates['avatar_thumbnail_url'] = avatar_thumbnail_url
        if email is not None:
            updates['email'] = email
        if phone is not None:
            updates['phone'] = phone
        if website is not None:
            updates['website'] = website
        
        # Handle certification
        if certification:
            updates['is_certified'] = certification.get('is_certified', False)
        
        if not updates:
            return create_failure_response(
                "VALIDATION_ERROR",
                "No fields provided for update",
                {
                    'updatable_fields': ['full_name', 'avatar_thumbnail_url', 'email', 'phone', 'website', 'certification'],
                    'nickname': nickname
                }
            )
        
        # Update the entity
        result = user_org_service.update_entity(
            nickname=nickname,
            updates=updates,
            updated_by=params.get('updated_by')
        )
        
        print(f"Successfully updated entity: {nickname}")
        
        # Return success response
        response_data = {
            'entity': result,
            'nickname': nickname,
            'updated_fields': list(updates.keys()),
            'operation': 'update'
        }
        
        execution_metadata = {
            'updated_field_count': len(updates.keys()),
            'updated_by': params.get('updated_by')
        }
        
        print(f"Successfully updated entity: {nickname}")
        return create_success_response(response_data, execution_metadata)
        
    except EntityNotFoundError as e:
        print(f"Entity not found: {str(e)}")
        
        return create_failure_response(
            "NOT_FOUND",
            str(e),
            {
                'nickname': nickname,
                'operation': 'update'
            }
        )
        
    except ValidationError as e:
        print(f"Validation error updating entity: {str(e)}")
        
        details = {'nickname': nickname}
        
        # Include validation details if available
        if hasattr(e, 'details') and e.details:
            details.update(e.details)
        
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            details
        )
        
    except ValueError as e:
        print(f"Input validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "required_fields": ["nickname"],
                "updatable_fields": ["full_name", "avatar_thumbnail_url", "email", "phone", "website", "certification"]
            }
        )
    except Exception as e:
        print(f"Unexpected error updating entity: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Entity update failed due to internal error",
            {"error_details": str(e)}
        )