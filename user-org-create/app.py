"""
User-Organization Create Lambda Function
Creates new users or organizations in the unified table
"""
import json
import os

# Add shared directory to path

from anecdotario_commons.decorators import standard_lambda_handler
from anecdotario_commons.services.service_container import get_service
from anecdotario_commons.utils import create_response
from anecdotario_commons.constants import HTTPConstants
from anecdotario_commons.exceptions import ValidationError, DuplicateEntityError
@standard_lambda_handler(
    required_fields=['nickname', 'full_name', 'user_type'],
    entity_validation=False,  # We'll validate user_type manually
    photo_type_validation=False,
    support_query_params=False,
    log_requests=True
)
def lambda_handler(event, context):
    """
    Create a new user or organization
    
    Expected request format:
    {
        "nickname": "john_doe",
        "full_name": "John Doe",
        "user_type": "user",           # Required: 'user' or 'organization'
        "avatar_thumbnail_url": "https://...",  # Optional
        "is_certified": false,         # Optional, default: false
        "email": "john@example.com",   # Optional
        "phone": "+1234567890",        # Optional  
        "website": "https://...",      # Optional
        "created_by": "admin_user"     # Optional
    }
    """
    # Extract validated parameters (decorators guarantee these exist)
    params = event['parsed_body']
    
    # Extract required fields
    nickname = params['nickname']
    full_name = params['full_name']
    user_type = params['user_type']
    
    # Extract optional fields
    avatar_thumbnail_url = params.get('avatar_thumbnail_url')
    is_certified = params.get('is_certified', False)
    email = params.get('email')
    phone = params.get('phone')
    website = params.get('website')
    created_by = params.get('created_by')
    
    # Validate user_type manually
    valid_user_types = ['user', 'organization']
    if user_type not in valid_user_types:
        return create_response(
            HTTPConstants.BAD_REQUEST,
            json.dumps({
                'success': False,
                'error': f'Invalid user_type. Must be one of: {", ".join(valid_user_types)}',
                'valid_user_types': valid_user_types
            }),
            event
        )
    
    print(f"Creating {user_type}: {nickname} ({full_name})")
    
    # Get user-org service from container (dependency injection)
    user_org_service = get_service('user_org_service')
    
    try:
        # Create the entity
        result = user_org_service.create_entity(
            nickname=nickname,
            full_name=full_name,
            user_type=user_type,
            avatar_thumbnail_url=avatar_thumbnail_url,
            is_certified=is_certified,
            created_by=created_by,
            email=email,
            phone=phone,
            website=website
        )
        
        print(f"Successfully created {user_type}: {result['nickname']}")
        
        # Return success response
        response_data = {
            'success': True,
            'message': f'{user_type.title()} created successfully',
            'entity': result
        }
        
        return create_response(
            HTTPConstants.CREATED,
            json.dumps(response_data),
            event
        )
        
    except ValidationError as e:
        print(f"Validation error creating {user_type}: {str(e)}")
        
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
        
    except DuplicateEntityError as e:
        print(f"Duplicate nickname error: {str(e)}")
        
        return create_response(
            HTTPConstants.CONFLICT,
            json.dumps({
                'success': False,
                'error': str(e),
                'error_type': 'duplicate_entity',
                'nickname': nickname
            }),
            event
        )
        
    except Exception as e:
        print(f"Unexpected error creating {user_type}: {str(e)}")
        raise  # Let the decorator handle it