# User-Organization Unified Storage Table

## 📊 DynamoDB Table Design

### Table Structure
```
Table Name: UserOrg-{environment}
Billing Mode: On-Demand (Pay per request)
```

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `nickname` | String | Hash Key (PK) | Unique identifier across users & orgs |
| `full_name` | String | | Full name or organization name |
| `user_type` | String | GSI Hash Key | 'user' or 'organization' |
| `avatar_thumbnail_url` | String | | URL to avatar/logo thumbnail |
| `is_certified` | Boolean | GSI Hash Key | Certification status |
| `status` | String | | 'active', 'inactive', 'suspended' |
| `email` | String | | Email address (optional) |
| `phone` | String | | Phone number (optional) |
| `website` | String | | Website URL (optional) |
| `created_at` | DateTime | GSI Range Key | Creation timestamp |
| `updated_at` | DateTime | | Last update timestamp |
| `created_by` | String | | Who created this entity |
| `followers_count` | Number | | Number of followers |
| `following_count` | Number | | Number of following |
| `posts_count` | Number | | Number of posts |

### Global Secondary Indexes

#### 1. User Type Index
- **Purpose**: Query by entity type (users vs organizations)
- **Hash Key**: `user_type`
- **Range Key**: `created_at`
- **Projection**: All attributes

#### 2. Certification Status Index  
- **Purpose**: Query certified entities
- **Hash Key**: `is_certified`
- **Range Key**: `created_at`
- **Projection**: All attributes

## 🔧 CRUD Operations

### Create Operations
| Function | Description | Input | Output |
|----------|-------------|-------|--------|
| `user-org-create` | Create new user/org | nickname, full_name, user_type, optional fields | Created entity data |

**Example Request:**
```json
{
  "nickname": "john_doe",
  "full_name": "John Doe",
  "user_type": "user",
  "avatar_thumbnail_url": "https://example.com/avatar.jpg",
  "is_certified": false,
  "email": "john@example.com"
}
```

### Read Operations  
| Function | Description | Modes | Output |
|----------|-------------|-------|--------|
| `user-org-get` | Flexible read operations | Single entity, List, Search, Certified | Entity/list data |

**Query Modes:**
1. **Get specific**: `{"nickname": "john_doe"}`
2. **List by type**: `{"user_type": "user", "limit": 20}`
3. **Search**: `{"search": "john", "limit": 10}`
4. **Get certified**: `{"certified": true}`

### Update Operations
| Function | Description | Updatable Fields | Output |
|----------|-------------|------------------|--------|
| `user-org-update` | Update entity data | All except nickname & user_type | Updated entity |

**Example Request:**
```json
{
  "nickname": "john_doe",
  "full_name": "John Doe Updated",
  "avatar_thumbnail_url": "https://new-avatar.jpg",
  "certification": {
    "is_certified": true,
    "certified_by": "admin"
  },
  "stats_update": {
    "followers_delta": 1,
    "posts_delta": 1
  }
}
```

### Delete Operations
| Function | Description | Options | Output |
|----------|-------------|---------|--------|
| `user-org-delete` | Delete entity | Soft/Hard delete | Deletion confirmation |

**Modes:**
- **Soft Delete** (default): Sets status to 'inactive'
- **Hard Delete**: Permanently removes from database

## 🔒 Unique Nickname Validation

### Validation Rules
1. **Global Uniqueness**: Nicknames unique across users AND organizations
2. **Case Insensitive**: Stored as lowercase for consistency
3. **Format Requirements**:
   - 3-30 characters
   - Lowercase letters, numbers, underscores only
   - Cannot start/end with underscore
   - No consecutive underscores

### Enhanced Validation Features
```python
# Example validation response
{
  "valid": false,
  "original": "John_User",
  "normalized": "john_user", 
  "entity_type": "user",
  "errors": [
    "Nickname contains uppercase letters"
  ],
  "warnings": [
    "Consider using only lowercase letters"
  ],
  "hints": [
    "Only lowercase letters (a-z), digits (0-9), and underscores (_) are allowed",
    "Invalid characters found: J, U"
  ]
}
```

### Reserved Words Protection
- **System Terms**: admin, api, support, help, system, root
- **Web Terms**: www, mail, ftp, http, https, ssl
- **Auth Terms**: login, signup, password, oauth, auth
- **Page Terms**: about, contact, terms, privacy, settings

## 📈 Performance & Scalability

### Query Patterns
| Pattern | Method | Performance | Use Case |
|---------|--------|-------------|----------|
| Get by nickname | `GetItem` | O(1) | Profile lookup, authentication |
| List by type | `GSI Query` | O(log n) | User/org directory |
| Search partial | `Scan` | O(n) | Search suggestions (use sparingly) |
| Get certified | `GSI Query` | O(log n) | Verified entity lists |

### Capacity Planning
- **Read**: Typical 10-100 RCU depending on traffic
- **Write**: Burst capacity for user registration
- **Storage**: ~1KB per entity, scales linearly

## 🏗️ Service Architecture

### Clean Architecture Layers
```
┌─────────────────────────────────────────┐
│           Lambda Handlers               │
│  (user-org-create, get, update, delete) │
├─────────────────────────────────────────┤
│         Service Layer                   │
│        (UserOrgService)                 │
├─────────────────────────────────────────┤
│         Model Layer                     │
│        (UserOrg PynamoDB)               │
├─────────────────────────────────────────┤
│         Data Layer                      │
│        (DynamoDB Table)                 │
└─────────────────────────────────────────┘
```

### Dependency Injection
```python
# Service registration
container.register_factory('user_org_service', UserOrgService)

# Usage in Lambda
user_org_service = get_service('user_org_service')
result = user_org_service.create_entity(...)
```

## 🧪 Testing Strategy

### Test Coverage
| Component | Test Types | Coverage |
|-----------|------------|----------|
| Model | Unit tests with moto | 90%+ |
| Service | Unit + Integration | 85%+ |
| Lambda | Handler tests | 80%+ |
| Validation | Comprehensive rules | 95%+ |

### Test Examples
```python
def test_nickname_uniqueness_across_types(self, user_org_service):
    # Create user
    user_org_service.create_entity(
        nickname='shared_name',
        user_type='user',
        full_name='User Name'
    )
    
    # Try to create org with same nickname
    with pytest.raises(DuplicateEntityError):
        user_org_service.create_entity(
            nickname='shared_name', 
            user_type='organization',
            full_name='Org Name'
        )
```

## 📊 Usage Examples

### Creating a User
```bash
# Lambda invocation
aws lambda invoke \
  --function-name anecdotario-user-org-create-dev \
  --payload '{
    "body": "{
      \"nickname\": \"john_doe\",
      \"full_name\": \"John Doe\", 
      \"user_type\": \"user\",
      \"email\": \"john@example.com\"
    }"
  }' response.json
```

### Getting Entity Data
```bash
# Get specific user
aws lambda invoke \
  --function-name anecdotario-user-org-get-dev \
  --payload '{
    "queryStringParameters": {
      "nickname": "john_doe"
    }
  }' response.json

# List all organizations
aws lambda invoke \
  --function-name anecdotario-user-org-get-dev \
  --payload '{
    "queryStringParameters": {
      "user_type": "organization",
      "limit": "20"
    }
  }' response.json
```

### Updating Entity
```bash
aws lambda invoke \
  --function-name anecdotario-user-org-update-dev \
  --payload '{
    "body": "{
      \"nickname\": \"john_doe\",
      \"full_name\": \"John Doe Updated\",
      \"certification\": {
        \"is_certified\": true,
        \"certified_by\": \"admin\"
      }
    }"
  }' response.json
```

### Service Integration
```python
# From user-service
lambda_client = boto3.client('lambda')

# Check if nickname exists
response = lambda_client.invoke(
    FunctionName='anecdotario-nickname-validate-dev',
    Payload=json.dumps({
        'nickname': user_nickname,
        'entity_type': 'user'
    })
)

# Create user if valid  
if validation_result['valid']:
    response = lambda_client.invoke(
        FunctionName='anecdotario-user-org-create-dev',
        Payload=json.dumps({
            'body': json.dumps({
                'nickname': user_nickname,
                'full_name': user_full_name,
                'user_type': 'user',
                'email': user_email,
                'created_by': 'user-service'
            })
        })
    )
```

## 🔐 Security Features

### Data Protection
- **Input Validation**: Comprehensive validation at all levels
- **SQL Injection**: N/A (NoSQL with parameterized queries)
- **XSS Prevention**: Output encoding in responses
- **Access Control**: Service-level authentication

### Privacy Controls
- **Public Data**: `to_public_dict()` excludes sensitive fields
- **Private Data**: Full access requires authorization
- **Audit Trail**: Created/updated timestamps and attribution

## 🚀 Deployment Integration

### SAM Template Addition
```yaml
UserOrgCreateFunction:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: user-org-create/
    Runtime: python3.12
    Environment:
      Variables:
        USER_ORG_TABLE_NAME: !Ref UserOrgTable

UserOrgTable:
  Type: AWS::DynamoDB::Table  
  Properties:
    TableName: !Sub 'UserOrg-${Environment}'
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: nickname
        AttributeType: S
      - AttributeName: user_type
        AttributeType: S
      - AttributeName: is_certified
        AttributeType: B
      - AttributeName: created_at
        AttributeType: S
    KeySchema:
      - AttributeName: nickname
        KeyType: HASH
    GlobalSecondaryIndexes:
      - IndexName: user-type-index
        KeySchema:
          - AttributeName: user_type
            KeyType: HASH
          - AttributeName: created_at
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
      - IndexName: certification-status-index
        KeySchema:
          - AttributeName: is_certified
            KeyType: HASH
          - AttributeName: created_at
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
```

---

## 📋 Summary

This unified user-organization table provides:

✅ **Global Nickname Uniqueness** across users and organizations  
✅ **Complete CRUD Operations** with clean Lambda handlers  
✅ **Enhanced Validation** with detailed error hints  
✅ **Flexible Query Patterns** for various use cases  
✅ **Production-Ready Architecture** with dependency injection  
✅ **Comprehensive Testing** with high coverage  
✅ **Performance Optimization** with appropriate indexes  
✅ **Security Best Practices** with input validation and privacy controls  

The system ensures that nicknames are truly unique across the entire platform while providing flexible, scalable access patterns for different application needs.