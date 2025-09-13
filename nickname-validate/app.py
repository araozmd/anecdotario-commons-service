"""
Nickname Validation Lambda Function
Self-contained nickname validation service for users, orgs, campaigns, etc.
"""
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def create_success_response(data: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create protocol-agnostic success response for internal Lambda communication"""
    response = {
        "success": True,
        "data": data
    }
    
    # Build metadata
    response_metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "function_name": "nickname-validate"
    }
    
    if metadata:
        response_metadata.update(metadata)
    
    response["metadata"] = response_metadata
    
    return response


def create_failure_response(error_code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create protocol-agnostic failure response for internal Lambda communication"""
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message
        }
    }
    
    if details:
        response["error"]["details"] = details
    
    # Build metadata
    response["metadata"] = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "function_name": "nickname-validate"
    }
    
    return response


# Reserved words for different entity types
RESERVED_WORDS = {
    'common': [
        'admin', 'administrator', 'root', 'system', 'api', 'www', 'mail', 'email',
        'support', 'help', 'info', 'contact', 'about', 'terms', 'privacy', 'legal',
        'security', 'null', 'undefined', 'true', 'false', 'test', 'demo', 'example'
    ],
    'user': [
        'me', 'user', 'users', 'profile', 'account', 'settings', 'login', 'logout',
        'register', 'signup', 'signin', 'dashboard', 'home', 'notifications'
    ],
    'org': [
        'org', 'organization', 'company', 'business', 'enterprise', 'team',
        'group', 'community', 'public', 'official', 'verified'
    ],
    'campaign': [
        'campaign', 'campaigns', 'story', 'stories', 'collection', 'archive',
        'memory', 'memories', 'anecdote', 'anecdotes'
    ]
}


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
    
    # Check if this is a rules request
    if body.get('get_rules'):
        entity_type = body.get('entity_type', 'user')
        return {'get_rules': True, 'entity_type': entity_type}
    
    # Validate nickname request
    if 'nickname' not in body or not body['nickname']:
        raise ValueError("Missing required field: nickname")
    
    entity_type = body.get('entity_type', 'user')
    
    # Validate entity_type
    valid_entity_types = ['user', 'org', 'campaign']
    if entity_type not in valid_entity_types:
        raise ValueError(f"Invalid entity_type. Must be one of: {', '.join(valid_entity_types)}")
    
    return body


def validate_nickname(nickname: str, entity_type: str) -> Dict[str, Any]:
    """Validate nickname according to rules"""
    errors = []
    hints = []
    
    # Length validation
    if len(nickname) < 3:
        errors.append("too_short")
        hints.append("Nickname must be at least 3 characters long")
    elif len(nickname) > 30:
        errors.append("too_long")
        hints.append("Nickname must be no more than 30 characters long")
    
    # Character validation
    if not re.match(r'^[a-zA-Z0-9_.-]+$', nickname):
        errors.append("invalid_characters")
        hints.append("Nickname can only contain letters, numbers, underscores, dots, and hyphens")
    
    # Start/end validation
    if nickname.startswith(('.', '-', '_')) or nickname.endswith(('.', '-', '_')):
        errors.append("invalid_start_end")
        hints.append("Nickname cannot start or end with dots, hyphens, or underscores")
    
    # Consecutive special characters
    if re.search(r'[._-]{2,}', nickname):
        errors.append("consecutive_special")
        hints.append("Nickname cannot have consecutive dots, hyphens, or underscores")
    
    # Reserved words check
    reserved_for_entity = RESERVED_WORDS.get('common', []) + RESERVED_WORDS.get(entity_type, [])
    if nickname.lower() in [word.lower() for word in reserved_for_entity]:
        errors.append("reserved_word")
        hints.append(f"'{nickname}' is a reserved word and cannot be used")
    
    # Profanity check (basic)
    profanity_words = ['fuck', 'shit', 'damn', 'bitch', 'ass', 'hell']
    if any(word in nickname.lower() for word in profanity_words):
        errors.append("inappropriate")
        hints.append("Nickname contains inappropriate language")
    
    # Numeric only check
    if nickname.isdigit():
        errors.append("numeric_only")
        hints.append("Nickname cannot be only numbers")
    
    is_valid = len(errors) == 0
    
    return {
        'valid': is_valid,
        'errors': errors,
        'hints': hints,
        'nickname': nickname,
        'entity_type': entity_type
    }


def get_validation_rules(entity_type: str) -> Dict[str, Any]:
    """Get validation rules for entity type"""
    return {
        'entity_type': entity_type,
        'rules': {
            'min_length': 3,
            'max_length': 30,
            'allowed_characters': 'Letters, numbers, underscores, dots, and hyphens',
            'pattern': '^[a-zA-Z0-9_.-]+$',
            'restrictions': [
                'Cannot start or end with dots, hyphens, or underscores',
                'Cannot have consecutive dots, hyphens, or underscores',
                'Cannot be only numbers',
                'Cannot contain inappropriate language',
                'Cannot be a reserved word'
            ]
        },
        'reserved_words': RESERVED_WORDS.get('common', []) + RESERVED_WORDS.get(entity_type, []),
        'examples': {
            'valid': ['john_doe', 'user123', 'my-company', 'story.collection'],
            'invalid': ['ab', '.user', 'user.', 'user..name', '123456', 'admin']
        }
    }


def lambda_handler(event, context):
    """
    Nickname validation handler supporting two operation modes
    
    Mode 1 - Validate nickname:
    {"nickname": "test_user", "entity_type": "user"}
    
    Mode 2 - Get validation rules:
    {"get_rules": true, "entity_type": "user"}
    """
    
    try:
        # Validate input
        params = validate_input(event)
        
        if params.get('get_rules'):
            # Mode 2: Return validation rules
            entity_type = params.get('entity_type', 'user')
            rules = get_validation_rules(entity_type)
            
            print(f"Returning validation rules for entity type: {entity_type}")
            return create_success_response(rules, {"operation_mode": "get_rules"})
        
        else:
            # Mode 1: Validate nickname
            nickname = params['nickname']
            entity_type = params.get('entity_type', 'user')
            
            print(f"Validating nickname: {nickname} for entity type: {entity_type}")
            
            validation_result = validate_nickname(nickname, entity_type)
            
            response_data = {
                'valid': validation_result['valid'],
                'nickname': nickname,
                'entity_type': entity_type
            }
            
            execution_metadata = {
                'operation_mode': 'validate_nickname',
                'validation_rules_applied': len(validation_result.get('errors', [])) + (1 if validation_result['valid'] else 0)
            }
            
            if not validation_result['valid']:
                response_data['validation_errors'] = {
                    'errors': validation_result['errors'],
                    'hints': validation_result['hints']
                }
            
            print(f"Nickname validation completed: {validation_result['valid']}")
            return create_success_response(response_data, execution_metadata)
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "required_fields": ["nickname"],
                "optional_fields": ["entity_type", "get_rules"]
            }
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Nickname validation failed due to internal error",
            {"error_details": str(e)}
        )