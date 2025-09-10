"""
User-Organization Get/Read Lambda Function
Retrieves user or organization data with flexible query options
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.decorators import direct_lambda_handler
from shared.services.service_container import get_service
from shared.utils import create_response, create_error_response
from shared.constants import HTTPConstants
from shared.exceptions import EntityNotFoundError


@direct_lambda_handler(
    required_fields=[],  # No required fields - conditional validation
    entity_validation=False,  # Manual validation based on operation
    photo_type_validation=False,
    log_requests=True
)
def lambda_handler(event, context):
    """
    Get user/organization data with flexible query options
    
    Supports multiple operation modes:
    
    Mode 1 - Get specific entity:
    {"nickname": "john_doe"}
    
    Mode 2 - Search entities:
    {"search": "john", "limit": 5}
    
    Mode 3 - List entities by type:
    {"user_type": "user", "limit": 20}
    """
    # Get parameters from event (direct invocation)
    params = event
    
    # Extract parameters
    nickname = params.get('nickname')
    user_type = params.get('user_type')
    search = params.get('search')
    limit = min(int(params.get('limit', 20)), 100)  # Cap at 100
    
    # Get user-org service from container (dependency injection)
    user_org_service = get_service('user_org_service')
    
    try:
        if nickname:
            # Mode 1: Get specific entity
            print(f"Getting entity by nickname: {nickname}")
            
            result = user_org_service.get_entity(nickname)
            if not result:
                return create_error_response(
                    HTTPConstants.NOT_FOUND,
                    f"Entity '{nickname}' not found",
                    event,
                    {'nickname': nickname}
                )
            
            response_data = {
                'success': True,
                'entity': result
            }
            
        elif search:
            # Mode 2: Search entities
            print(f"Searching entities with: {search}")
            
            results = user_org_service.search_entities(
                query=search,
                limit=limit
            )
            
            response_data = {
                'success': True,
                'search_query': search,
                'entities': results['results'],
                'total_returned': len(results['results']),
                'limit': limit
            }
            
        else:
            # Mode 3: List entities with optional filtering
            print(f"Listing entities (type: {user_type or 'all'}, limit: {limit})")
            
            # Validate user_type if provided
            if user_type and user_type not in ['user', 'organization']:
                return create_error_response(
                    HTTPConstants.BAD_REQUEST,
                    'Invalid user_type. Must be "user" or "organization"',
                    event,
                    {'valid_user_types': ['user', 'organization']}
                )
            
            results = user_org_service.search_entities(
                query="",  # Empty query to get all
                entity_type=user_type,
                limit=limit
            )
            
            response_data = {
                'success': True,
                'entities': results['results'],
                'total_returned': len(results['results']),
                'entity_type': user_type,
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