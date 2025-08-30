"""
User-Organization Get/Read Lambda Function
Retrieves user or organization data with flexible query options
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from decorators import validate_query_or_body, handle_exceptions, cors_enabled, log_request
from services.service_container import get_service
from utils import create_response, create_error_response
from constants import HTTPConstants
from exceptions import EntityNotFoundError
import functools


def user_org_get_handler(func):
    """Custom composite decorator for user-org get handler"""
    
    @functools.wraps(func)
    @log_request(operation='user_org_get')
    @cors_enabled(['GET', 'POST'])
    @handle_exceptions(operation='user_org_get')
    @validate_query_or_body([])  # No required fields - conditional validation
    def wrapper(event, context):
        return func(event, context)
    
    return wrapper


@user_org_get_handler
def lambda_handler(event, context):
    """
    Get user/organization data with flexible query options
    
    Supports multiple operation modes:
    
    Mode 1 - Get specific entity:
    GET /?nickname=john_doe
    POST {"nickname": "john_doe"}
    
    Mode 2 - List entities with filtering:  
    GET /?user_type=user&limit=20
    POST {"user_type": "organization", "limit": 10}
    
    Mode 3 - Search entities:
    GET /?search=john&limit=5
    POST {"search": "acme", "limit": 10}
    
    Mode 4 - Get certified entities:
    GET /?certified=true
    POST {"certified": true}
    """
    # Get parameters from query or body (handled by decorator)
    params = event.get('parsed_params', {})
    
    # Extract parameters
    nickname = params.get('nickname')
    user_type = params.get('user_type')
    search = params.get('search')
    certified = str(params.get('certified', '')).lower() in ('true', '1', 'yes')
    limit = min(int(params.get('limit', 50)), 100)  # Cap at 100
    last_evaluated_key = params.get('last_evaluated_key')
    public_only = str(params.get('public_only', 'true')).lower() in ('true', '1', 'yes')
    
    # Get user-org service from container (dependency injection)
    user_org_service = get_service('user_org_service')
    
    try:
        if nickname:
            # Mode 1: Get specific entity
            print(f"Getting entity by nickname: {nickname}")
            
            try:
                if public_only:
                    result = user_org_service.get_public_entity(nickname)
                else:
                    result = user_org_service.get_entity(nickname)
                
                response_data = {
                    'success': True,
                    'entity': result
                }
                
            except EntityNotFoundError as e:
                return create_error_response(
                    HTTPConstants.NOT_FOUND,
                    str(e),
                    event,
                    {'nickname': nickname}
                )
                
        elif search:
            # Mode 3: Search entities
            print(f"Searching entities with: {search}")
            
            results = user_org_service.search_entities(search, limit)
            
            response_data = {
                'success': True,
                'search_query': search,
                'entities': results,
                'total_returned': len(results),
                'limit': limit
            }
            
        elif certified:
            # Mode 4: Get certified entities
            print(f"Getting certified entities (limit: {limit})")
            
            results = user_org_service.get_certified_entities(limit)
            
            response_data = {
                'success': True,
                'certified_entities': results,
                'total_returned': len(results),
                'limit': limit
            }
            
        else:
            # Mode 2: List entities with optional filtering
            print(f"Listing entities (type: {user_type or 'all'}, limit: {limit})")
            
            # Validate user_type if provided
            if user_type and user_type not in ['user', 'organization']:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    'Invalid user_type. Must be "user" or "organization"',
                    event,
                    {'valid_user_types': ['user', 'organization']}
                )
            
            results = user_org_service.list_entities(
                user_type=user_type,
                limit=limit,
                last_evaluated_key=last_evaluated_key
            )
            
            # Adjust response based on user_type
            if user_type == 'user':
                response_data = {
                    'success': True,
                    'users': results.get('users', []),
                    'total_returned': results.get('total_returned', 0),
                    'last_evaluated_key': results.get('last_evaluated_key'),
                    'limit': limit
                }
            elif user_type == 'organization':
                response_data = {
                    'success': True,
                    'organizations': results.get('organizations', []),
                    'total_returned': results.get('total_returned', 0),
                    'last_evaluated_key': results.get('last_evaluated_key'),
                    'limit': limit
                }
            else:
                response_data = {
                    'success': True,
                    'entities': results.get('entities', []),
                    'total_returned': results.get('total_returned', 0),
                    'last_evaluated_key': results.get('last_evaluated_key'),
                    'limit': limit
                }
        
        print(f"Successfully processed request")
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
        
    except Exception as e:
        print(f"Unexpected error in user-org get: {str(e)}")
        raise  # Let the decorator handle it