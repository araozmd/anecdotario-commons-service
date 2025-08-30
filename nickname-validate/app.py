"""
Nickname Validation Lambda Function
Validates nicknames for users, orgs, and other entities with detailed error hints
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from validators.nickname import nickname_validator
from utils import create_response, create_error_response


def lambda_handler(event, context):
    """
    Nickname validation handler
    
    Expected request format:
    {
        "nickname": "test_user",
        "entity_type": "user|org",  # Optional, defaults to 'user'
        "get_rules": false          # Optional, return validation rules instead
    }
    
    Or for getting rules:
    {
        "get_rules": true,
        "entity_type": "user"       # Optional
    }
    """
    try:
        print(f"Nickname validation request received")
        
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
        nickname = params.get('nickname', '').strip()
        entity_type = params.get('entity_type', 'user').lower()
        get_rules = str(params.get('get_rules', '')).lower() in ('true', '1', 'yes')
        
        # Validate entity type
        valid_entity_types = ['user', 'org', 'campaign']
        if entity_type not in valid_entity_types:
            return create_error_response(
                400,
                f'Invalid entity_type. Must be one of: {", ".join(valid_entity_types)}',
                event,
                {'valid_types': valid_entity_types}
            )
        
        if get_rules:
            # Return validation rules
            rules = nickname_validator.get_validation_rules(entity_type)
            
            response_data = {
                'message': 'Validation rules retrieved successfully',
                'entity_type': entity_type,
                'rules': rules
            }
            
            print(f"Validation rules requested for {entity_type}")
            
            return create_response(
                200,
                json.dumps(response_data),
                event,
                ['GET', 'POST']
            )
        
        if not nickname:
            return create_error_response(
                400,
                'Nickname is required for validation',
                event,
                {'usage': 'POST with {"nickname": "test_user", "entity_type": "user"}'}
            )
        
        # Validate nickname
        print(f"Validating nickname '{nickname}' for {entity_type}")
        
        validation_result = nickname_validator.validate(nickname, entity_type)
        
        # Enhanced response with errors, warnings, and normalized version
        response_data = {
            'valid': validation_result['valid'],
            'original': validation_result['original'],
            'normalized': validation_result['normalized'],
            'entity_type': validation_result['entity_type'],
            'errors': validation_result['errors'],
            'warnings': validation_result['warnings'],
            'hints': validation_result['hints']
        }
        
        # Add legacy fields for backward compatibility
        if validation_result['valid']:
            response_data['message'] = 'Nickname is valid'
            response_data['validation_passed'] = True
            print(f"Nickname validation passed: {nickname} (normalized: {validation_result['normalized']})")
        else:
            # For backward compatibility, join errors into single error message
            response_data['error'] = '; '.join(validation_result['errors']) if validation_result['errors'] else None
            response_data['validation_failed'] = True
            print(f"Nickname validation failed: {validation_result['errors']}")
        
        return create_response(
            200,  # Always 200 OK, check 'valid' field for result
            json.dumps(response_data),
            event,
            ['POST', 'GET']
        )
        
    except Exception as e:
        print(f"Unexpected error in nickname validation: {str(e)}")
        return create_error_response(
            500,
            'Internal server error',
            event,
            {'details': str(e)}
        )