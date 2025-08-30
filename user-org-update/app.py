"""
User-Organization Update Lambda Function
Updates user or organization data (nickname and user_type are immutable)
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
from exceptions import ValidationError, EntityNotFoundError


@standard_lambda_handler(
    required_fields=['nickname'],  # Only nickname is required for updates
    entity_validation=False,
    photo_type_validation=False,
    support_query_params=False,
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
    params = event['parsed_body']
    
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
        result = None
        operations_performed = []
        
        # Standard field updates
        if any([full_name is not None, avatar_thumbnail_url is not None, 
               email is not None, phone is not None, website is not None]):
            
            result = user_org_service.update_entity(
                nickname=nickname,
                full_name=full_name,
                avatar_thumbnail_url=avatar_thumbnail_url,
                email=email,
                phone=phone,
                website=website
            )
            operations_performed.append('basic_info_updated')
        
        # Certification update
        if certification:
            is_certified = certification.get('is_certified', False)
            certified_by = certification.get('certified_by')
            
            cert_result = user_org_service.set_certification_status(
                nickname=nickname,
                is_certified=is_certified,
                certified_by=certified_by
            )
            
            if result:
                result.update(cert_result)
            else:
                result = cert_result
            
            operations_performed.append('certification_updated')
        
        # Statistics update
        if stats_update:
            followers_delta = stats_update.get('followers_delta', 0)
            following_delta = stats_update.get('following_delta', 0)
            posts_delta = stats_update.get('posts_delta', 0)
            
            stats_result = user_org_service.update_stats(
                nickname=nickname,
                followers_delta=followers_delta,
                following_delta=following_delta,
                posts_delta=posts_delta
            )
            
            if result:
                result.update(stats_result)
            else:
                result = stats_result
            
            operations_performed.append('stats_updated')
        
        # If no operations were performed, just return current entity data
        if not operations_performed:
            result = user_org_service.get_entity(nickname)
            operations_performed.append('entity_retrieved')
        
        print(f"Successfully updated entity: {nickname} (operations: {', '.join(operations_performed)})")
        
        # Return success response
        response_data = {
            'success': True,
            'message': 'Entity updated successfully',
            'operations_performed': operations_performed,
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