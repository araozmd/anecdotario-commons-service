"""
Nickname Validation Lambda Function
Validates nicknames for users, orgs, and other entities with detailed error hints
"""
import json
import os

# Add shared directory to path

from anecdotario_commons.decorators import validate_query_or_body, validate_entity_type, handle_exceptions, cors_enabled, log_request
from anecdotario_commons.validators.nickname import nickname_validator
from anecdotario_commons.utils import create_response, create_error_response
from anecdotario_commons.constants import HTTPConstants, EntityConstants
import functools
def nickname_validation_handler(func):
    """Custom composite decorator for nickname validation handler"""
    
    @functools.wraps(func)
    @log_request()
    @cors_enabled(['GET', 'POST'])
    @handle_exceptions()
    @validate_entity_type(EntityConstants.VALID_ENTITY_TYPES)
    @validate_query_or_body([])  # No required fields - conditional validation
    def wrapper(event, context):
        return func(event, context)
    
    return wrapper
@nickname_validation_handler
def lambda_handler(event, context):
    """
    Nickname validation handler supporting two operation modes
    
    Mode 1 - Validate nickname:
    {"nickname": "test_user", "entity_type": "user"}
    
    Mode 2 - Get validation rules:
    {"get_rules": true, "entity_type": "user"}
    """
    # Get parameters from query or body (handled by decorators)
    params = event.get('parsed_params', {})
    
    # Extract parameters
    nickname = params.get('nickname', '').strip()
    entity_type = params.get('entity_type', 'user').lower()
    get_rules = str(params.get('get_rules', '')).lower() in ('true', '1', 'yes')
    
    if get_rules:
        # Mode 2: Return validation rules
        print(f"Validation rules requested for {entity_type}")
        
        rules = nickname_validator.get_validation_rules(entity_type)
        
        response_data = {
            'success': True,
            'message': 'Validation rules retrieved successfully',
            'entity_type': entity_type,
            'rules': rules
        }
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
    
    # Mode 1: Validate nickname
    if not nickname:
        return create_error_response(
            HTTPConstants.BAD_REQUEST,
            'Nickname is required for validation',
            event,
            {
                'usage_validate': 'POST with {"nickname": "test_user", "entity_type": "user"}',
                'usage_rules': 'POST with {"get_rules": true, "entity_type": "user"}'
            }
        )
    
    print(f"Validating nickname '{nickname}' for {entity_type}")
    
    # Validate nickname using the enhanced validator
    validation_result = nickname_validator.validate(nickname, entity_type)
    
    # Create enhanced response with all validation details
    response_data = {
        'success': True,
        'valid': validation_result['valid'],
        'original': validation_result['original'],
        'normalized': validation_result['normalized'],
        'entity_type': validation_result['entity_type'],
        'errors': validation_result['errors'],
        'warnings': validation_result['warnings'],
        'hints': validation_result['hints']
    }
    
    # Add status-specific fields
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
        HTTPConstants.OK,  # Always 200 OK, check 'valid' field for result
        json.dumps(response_data),
        event
    )