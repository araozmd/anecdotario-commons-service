"""
User-Org Search Lambda Function
Search across users and organizations by nickname or full name
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from shared.decorators import api_gateway_handler
from shared.services.service_container import get_service
from shared.utils import create_response, create_error_response
from shared.constants import HTTPConstants
@api_gateway_handler(
    required_fields=[],  # No required fields - query is optional
    entity_validation=False,
    photo_type_validation=False,
    log_requests=True,
    require_auth=True  # This is a public API endpoint
)
def lambda_handler(event, context):
    """
    Search users and organizations by query with pagination support
    
    Query Parameters:
    - q: Search query (minimum 2 characters, required)
    - limit: Maximum results per page (default 20, max 50)
    - page_token: Pagination token from previous response (optional)
    
    Examples:
    GET /search?q=john&limit=10
    GET /search?q=john&limit=10&page_token=eyJuaWNrbmFtZSI6ImpvaG4ifQ
    
    Returns all users/orgs where nickname or full_name contains the query
    Response includes pagination info for retrieving additional results
    """
    # Get query parameters (API Gateway format)
    query_params = event.get('queryStringParameters') or {}
    query = query_params.get('q', '').strip()
    
    # Get user-org service from container (dependency injection)
    user_org_service = get_service('user_org_service')
    
    # Validate query
    if not query:
        return create_error_response(
            HTTPConstants.BAD_REQUEST,
            'Query parameter "q" is required',
            event,
            {
                'usage': 'GET /search?q=john&limit=10&page_token=eyJuaWNrbmFtZSI6ImpvaG4ifQ',
                'requirements': 'Query must be at least 2 characters'
            }
        )
    
    if len(query) < 2:
        return create_error_response(
            HTTPConstants.BAD_REQUEST,
            'Query must be at least 2 characters long',
            event,
            {
                'provided_query': query,
                'min_length': 2
            }
        )
    
    # Parse limit parameter
    try:
        limit = int(query_params.get('limit', 20))
        if limit > 50:
            limit = 50  # Cap at 50 for performance
        elif limit < 1:
            limit = 20  # Default to 20
    except (ValueError, TypeError):
        limit = 20
    
    # Parse pagination token
    page_token = query_params.get('page_token')
    last_evaluated_key = None
    
    if page_token:
        try:
            import base64
            # Decode the pagination token
            decoded_token = base64.b64decode(page_token).decode('utf-8')
            last_evaluated_key = json.loads(decoded_token)
        except Exception as e:
            return create_error_response(
                HTTPConstants.BAD_REQUEST,
                'Invalid page_token parameter',
                event,
                {
                    'error': 'Page token must be a valid base64-encoded JSON',
                    'details': str(e)
                }
            )
    
    print(f"Searching entities with query='{query}', limit={limit}, page_token={'provided' if page_token else 'none'}")
    
    # Perform search using the UserOrg model
    try:
        search_result = UserOrg.search_entities(query, limit, last_evaluated_key)
        
        # Generate next page token if there are more results
        next_page_token = None
        if search_result.get('has_more') and search_result.get('last_evaluated_key'):
            import base64
            # Encode the last evaluated key as a base64 token
            token_data = json.dumps(search_result['last_evaluated_key'])
            next_page_token = base64.b64encode(token_data.encode('utf-8')).decode('utf-8')
        
        # Prepare response
        response_data = {
            'success': True,
            'query': query,
            'limit': limit,
            'total_found': search_result['total_found'],
            'has_more': search_result.get('has_more', False),
            'next_page_token': next_page_token,
            'results': search_result['results'],
            'pagination': {
                'current_page_size': len(search_result['results']),
                'requested_limit': limit,
                'has_more_pages': search_result.get('has_more', False),
                'items_scanned': search_result.get('items_scanned', 0)
            },
            'search_metadata': {
                'search_type': 'contains_match',
                'fields_searched': ['nickname', 'full_name'],
                'entity_types': ['user', 'organization'],
                'status_filter': 'active_only',
                'sorting': 'relevance_based'
            }
        }
        
        print(f"Search completed: {search_result['total_found']} results found, has_more: {search_result.get('has_more', False)}")
        
        return create_response(
            HTTPConstants.OK,
            json.dumps(response_data),
            event
        )
        
    except Exception as e:
        print(f"Search failed: {str(e)}")
        return create_error_response(
            HTTPConstants.INTERNAL_SERVER_ERROR,
            'Search operation failed',
            event,
            {
                'error_details': str(e),
                'query': query,
                'limit': limit
            }
        )