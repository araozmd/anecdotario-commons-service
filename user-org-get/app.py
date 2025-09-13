"""
User-Organization Get/Read Lambda Function
Retrieves user or organization data with flexible query options
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.services.service_container import get_service
from shared.utils import create_success_response, create_failure_response
from shared.exceptions import EntityNotFoundError
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
    
    # No required fields for get operations - all are optional
    return body


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
    try:
        # Validate input parameters
        params = validate_input(event)
    
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
                return create_failure_response(
                    "NOT_FOUND",
                    f"Entity '{nickname}' not found",
                    {'nickname': nickname, 'operation': 'get_by_nickname'}
                )
            
            response_data = {
                'entity': result,
                'operation_mode': 'get_by_nickname',
                'nickname': nickname
            }
            
            execution_metadata = {
                'query_type': 'get_by_nickname',
                'found_entity_type': result.get('user_type')
            }
            
        elif search:
            # Mode 2: Search entities
            print(f"Searching entities with: {search}")
            
            results = user_org_service.search_entities(
                query=search,
                limit=limit
            )
            
            response_data = {
                'entities': results['results'],
                'operation_mode': 'search_entities',
                'search_query': search,
                'total_returned': len(results['results']),
                'limit': limit
            }
            
            execution_metadata = {
                'query_type': 'search_entities',
                'results_count': len(results['results'])
            }
            
        else:
            # Mode 3: List entities with optional filtering
            print(f"Listing entities (type: {user_type or 'all'}, limit: {limit})")
            
            # Validate user_type if provided
            if user_type and user_type not in ['user', 'organization']:
                return create_failure_response(
                    "VALIDATION_ERROR",
                    'Invalid user_type. Must be "user" or "organization"',
                    {
                        'valid_user_types': ['user', 'organization'],
                        'provided_user_type': user_type
                    }
                )
            
            results = user_org_service.search_entities(
                query="",  # Empty query to get all
                entity_type=user_type,
                limit=limit
            )
            
            response_data = {
                'entities': results['results'],
                'operation_mode': 'list_entities',
                'total_returned': len(results['results']),
                'entity_type': user_type,
                'limit': limit
            }
            
            execution_metadata = {
                'query_type': 'list_entities',
                'filter_entity_type': user_type,
                'results_count': len(results['results'])
            }
        
        print(f"Successfully processed request")
        
        return create_success_response(response_data, execution_metadata)
        
    except ValueError as e:
        print(f"Input validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "supported_operations": ["get_by_nickname", "search_entities", "list_entities"]
            }
        )
    except Exception as e:
        print(f"Unexpected error in user-org get: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Entity retrieval failed due to internal error",
            {"error_details": str(e)}
        )