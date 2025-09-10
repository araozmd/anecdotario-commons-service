"""
User-Organization Update Lambda Function
Updates user or organization data (nickname and user_type are immutable)
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
from shared.exceptions import ValidationError, EntityNotFoundError
@direct_lambda_handler(
    required_fields=['nickname'],  # Only nickname is required for updates
    entity_validation=False,
    photo_type_validation=False,
    log_requests=True
)
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
    # Extract validated parameters
    params = event
    
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
            return create_response(
                HTTPConstants.BAD_REQUEST,
                json.dumps({
                    'success': False,
                    'error': 'No fields provided for update',
                    'updatable_fields': ['full_name', 'avatar_thumbnail_url', 'email', 'phone', 'website', 'certification']
                }),
                event
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
            'success': True,
            'message': 'Entity updated successfully',
            'nickname': nickname,
            'updated_fields': list(updates.keys()),
            'entity': result
        }
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
        
    except EntityNotFoundError as e:
        print(f"Entity not found: {str(e)}")
        
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
        
    except ValidationError as e:
        print(f"Validation error updating entity: {str(e)}")
        
        error_response = {
            'success': False,
            'error': str(e),
            'error_type': 'validation_error'
        }
        
        # Include validation details if available
        if hasattr(e, 'details') and e.details:
            error_response.update(e.details)
        
        return create_response(
            HTTPConstants.BAD_REQUEST,
            json.dumps(error_response),
            event
        )
        
    except Exception as e:
        print(f"Unexpected error updating entity: {str(e)}")
        raise  # Let the decorator handle it