"""
User-Organization Create Lambda Function
Creates new users or organizations in the unified table
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.services.service_container import get_service
from shared.utils import create_success_response, create_failure_response
from shared.exceptions import ValidationError, DuplicateEntityError
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
    required_fields = ['nickname', 'full_name', 'user_type']
    for field in required_fields:
        if field not in body or not body[field]:
            raise ValueError(f"Missing required field: {field}")
    
    return body


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
    try:
        # Validate input parameters
        params = validate_input(event)
    
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
            return create_failure_response(
                "VALIDATION_ERROR",
                f'Invalid user_type. Must be one of: {", ".join(valid_user_types)}',
                {'valid_user_types': valid_user_types, 'provided_user_type': user_type}
            )
    
        print(f"Creating {user_type}: {nickname} ({full_name})")
        
        # Get user-org service from container (dependency injection)
        user_org_service = get_service('user_org_service')
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
            'entity': result,
            'user_type': user_type,
            'operation': 'create'
        }
        
        execution_metadata = {
            'created_entity_type': user_type,
            'created_nickname': result.get('nickname')
        }
        
        print(f"Successfully created {user_type}: {result['nickname']}")
        return create_success_response(response_data, execution_metadata)
        
    except ValidationError as e:
        print(f"Validation error creating {user_type}: {str(e)}")
        
        details = {'user_type': user_type, 'nickname': nickname}
        
        # Include validation details if available
        if hasattr(e, 'details') and e.details:
            details.update(e.details)
        
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            details
        )
        
    except DuplicateEntityError as e:
        print(f"Duplicate nickname error: {str(e)}")
        
        return create_failure_response(
            "DUPLICATE_ENTITY",
            str(e),
            {
                'nickname': nickname,
                'user_type': user_type,
                'conflict_type': 'nickname_already_exists'
            }
        )
        
    except ValueError as e:
        print(f"Input validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "required_fields": ["nickname", "full_name", "user_type"]
            }
        )
    except Exception as e:
        print(f"Unexpected error creating entity: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Entity creation failed due to internal error",
            {"error_details": str(e)}
        )