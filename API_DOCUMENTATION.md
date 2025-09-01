# Anecdotario Commons Service API Documentation

## Overview

The Commons Service provides shared functionality across the Anecdotario platform, including user/organization search, nickname validation, photo processing, and shared utilities.

## Base URLs

| Environment | URL |
|-------------|-----|
| **Production** | `https://1hheux7spg.execute-api.us-east-1.amazonaws.com/prod` |
| **Staging** | `https://1hheux7spg.execute-api.us-east-1.amazonaws.com/staging` |
| **Development** | `https://1hheux7spg.execute-api.us-east-1.amazonaws.com/dev` |

## API Endpoints

### 🔍 Search API

**Endpoint**: `GET /search`

Search for users and organizations by nickname or full name with pagination support.

#### Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `q` | string | ✅ Yes | Search query (min 2 chars) | `john` |
| `limit` | integer | ❌ No | Results per page (default: 20, max: 50) | `10` |
| `page_token` | string | ❌ No | Pagination token from previous response | `eyJuaWNrbmFtZSI6ImpvaG4ifQ` |

#### Example Requests

```bash
# Basic search
GET /search?q=john&limit=10

# Paginated search
GET /search?q=tech&limit=5&page_token=eyJuaWNrbmFtZSI6InRlY2hfc3RhcnR1cCJ9
```

#### Response Format

```json
{
  "success": true,
  "query": "john",
  "limit": 10,
  "total_found": 3,
  "has_more": false,
  "next_page_token": null,
  "results": [
    {
      "nickname": "john_doe",
      "full_name": "John Doe",
      "user_type": "user",
      "is_certified": false,
      "avatar_thumbnail_url": "https://anecdotario-photos.s3.amazonaws.com/users/john_doe/profile/thumbnail_20241201_abc123.jpg",
      "posts_count": 15,
      "followers_count": 42,
      "following_count": 38,
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z",
      "match_type": "both",
      "match_position": 0
    }
  ],
  "pagination": {
    "current_page_size": 3,
    "requested_limit": 10,
    "has_more_pages": false,
    "items_scanned": 6
  },
  "search_metadata": {
    "search_type": "contains_match",
    "fields_searched": ["nickname", "full_name"],
    "entity_types": ["user", "organization"],
    "status_filter": "active_only",
    "sorting": "relevance_based"
  }
}
```

#### Search Features

- **Case-insensitive**: Matches regardless of capitalization
- **Partial matching**: Finds "john" in "johnny_test" and "John Doe"
- **Relevance sorting**: Nickname matches prioritized over full name matches
- **Cross-entity**: Searches both users and organizations
- **Active only**: Only returns entities with `status = 'active'`

#### Pagination

The API uses **token-based pagination** for efficient browsing:

1. **First page**: Make request without `page_token`
2. **Subsequent pages**: Use `next_page_token` from previous response
3. **End of results**: `has_more = false` and `next_page_token = null`

```javascript
// Example pagination workflow
let pageToken = null;
let allResults = [];

do {
  const url = `/search?q=john&limit=10${pageToken ? `&page_token=${pageToken}` : ''}`;
  const response = await fetch(url);
  const data = await response.json();
  
  allResults.push(...data.results);
  pageToken = data.next_page_token;
} while (pageToken);
```

#### Error Responses

| Status | Error | Description |
|--------|-------|-------------|
| **400** | Missing query | `q` parameter is required |
| **400** | Query too short | Query must be at least 2 characters |
| **400** | Invalid page token | Page token format is invalid |
| **500** | Search failure | Internal server error |

```json
// Example error response
{
  "success": false,
  "error": "Query parameter \"q\" is required",
  "details": {
    "usage": "GET /search?q=john&limit=10",
    "requirements": "Query must be at least 2 characters"
  }
}
```

## Internal Services

The Commons Service also provides internal Lambda functions for other Anecdotario services:

### 📸 Photo Management
- **Photo Upload**: `anecdotario-photo-upload-{env}`
- **Photo Delete**: `anecdotario-photo-delete-{env}`  
- **Photo Refresh**: `anecdotario-photo-refresh-{env}`

### ✅ Nickname Validation
- **Nickname Validate**: `anecdotario-nickname-validate-{env}`
- Global uniqueness checking across users and organizations
- Comprehensive validation rules and user-friendly error messages

### 👥 User-Organization Management
- **User-Org Create**: `anecdotario-user-org-create-{env}`
- **User-Org Get**: `anecdotario-user-org-get-{env}`
- **User-Org Update**: `anecdotario-user-org-update-{env}`
- **User-Org Delete**: `anecdotario-user-org-delete-{env}`

## Lambda Layer

The service exports a **Commons Service Layer** that other services can import:

```yaml
# In other service templates
Functions:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      Layers:
        - !ImportValue anecdotario-commons-service-layer-arn-dev
```

**Layer Includes**:
- Service contracts and interfaces
- Shared models (UserOrg, Photo)
- Common utilities and helpers
- Photo processing services

## Performance Notes

### Search API Performance

| Aspect | Details |
|--------|---------|
| **Operation Type** | DynamoDB scan (expensive for large datasets) |
| **Typical Response Time** | 1-3 seconds per page |
| **Recommended Page Size** | 20 results (default) |
| **Maximum Page Size** | 50 results |
| **Memory Allocation** | 256MB Lambda |
| **Timeout** | 15 seconds |

### Optimization Recommendations

1. **Use appropriate page sizes** (10-20 for UI, 50 for bulk operations)
2. **Cache results** when possible to reduce API calls
3. **Implement client-side debouncing** for search-as-you-type features
4. **Consider search term length** (longer terms = fewer results = faster response)

## Rate Limits

Currently no explicit rate limiting is configured, but AWS Lambda has natural concurrency limits:

- **Reserved concurrency**: 256 (search function)
- **Account-level limit**: 1000 concurrent executions (shared across all functions)

## CORS Configuration

CORS is handled at the API Gateway level with the following settings:

```yaml
Cors:
  AllowMethods: 'GET, POST, OPTIONS'
  AllowHeaders: 'Content-Type, Authorization'  
  AllowOrigin: '*'
  MaxAge: '600'
```

## Complete API Specification

For the complete OpenAPI 3.0.1 specification with all details, examples, and schemas, see: [`openapi.yaml`](./openapi.yaml)

## Support

For questions, issues, or feature requests related to the Commons Service API:

1. Check the [OpenAPI specification](./openapi.yaml) for detailed documentation
2. Review the [service contracts](./shared/contracts/) for internal function usage
3. Examine the [test files](./test_*.py) for usage examples