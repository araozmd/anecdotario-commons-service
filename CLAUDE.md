# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Service Overview

This is the **Commons Service** for the Anecdotario platform - a centralized serverless service providing shared functionality for all entity types (users, orgs, campaigns). Built with Python 3.12 LTS and deployed using AWS SAM.

## Key Architectural Decisions

### 1. Internal Service Communication Pattern
- **Pattern**: Direct Lambda invocation (not API Gateway)
- **Usage**: Other services invoke functions using `boto3.client('lambda').invoke()`
- **Security**: No HTTP endpoints, internal service communication only
- **Performance**: Lower latency, better security than REST APIs

### 2. Entity-Agnostic Design
- **Pattern**: All functions accept `entity_type` and `entity_id` parameters
- **Supported entities**: `user`, `org`, `campaign`
- **Extensibility**: Easy to add new entity types without code changes
- **Consistency**: Same processing logic across all entity types

### 3. Multi-Version Photo Storage Strategy
- **Versions**: 3 versions per photo (thumbnail 150x150, standard 320x320, high-res 800x800)
- **Access Control**: Thumbnails public, standard/high-res protected with presigned URLs
- **Processing**: Instagram-style square cropping with quality optimization
- **Cleanup**: Automatic removal of old photos when uploading new ones

## Common Development Tasks

### Build and Deploy
```bash
# Local build
sam build --parallel --cached

# Deploy to development
sam deploy --config-file samconfig-dev.toml

# Deploy to specific environment
sam deploy --config-file samconfig-staging.toml
sam deploy --config-file samconfig-prod.toml

# Deploy CI/CD pipeline
./deploy-pipeline.sh <github-token>
```

### Testing Commands
```bash
# Run tests for all functions
for function_dir in photo-upload photo-delete photo-refresh nickname-validate; do
  cd $function_dir && pytest tests/ -v && cd ..
done

# Run tests for specific function
cd photo-upload && pytest tests/ -v --cov=app

# Test with SAM local
sam local invoke PhotoUploadFunction --event events/photo-event.json
sam local invoke NicknameValidateFunction --event events/nickname-event.json

# Start local API for testing
sam local start-api --port 3000
```

### Development Workflow
```bash
# Set up development environment
pyenv local 3.12.8
pip install aws-sam-cli boto3 pytest Pillow pynamodb

# Install function dependencies
cd photo-upload && pip install -r requirements.txt

# Validate SAM template
sam validate --lint

# Package for deployment
sam package --s3-bucket anecdotario-sam-artifacts-dev --s3-prefix commons-service
```

### Monitoring and Debugging
```bash
# View function logs
sam logs -n PhotoUploadFunction --stack-name commons-service-dev --tail
sam logs -n NicknameValidateFunction --stack-name commons-service-dev --tail

# View specific log streams
aws logs filter-log-events --log-group-name /aws/lambda/anecdotario-photo-upload-dev

# Enable debug logging
export ENABLE_DEBUG_LOGGING=true
```

## Code Architecture

### Lambda Layer Pattern
- **Shared Layer**: `CommonsServiceLayer` contains shared modules (`config.py`, `utils.py`, models, processors, validators)
- **Function-Specific Code**: Each function directory contains only `app.py`, `requirements.txt`, and tests
- **Dependency Management**: Shared dependencies in layer, function-specific in individual `requirements.txt`

### Configuration Architecture (Hybrid Pattern)
1. **Environment Variables** (highest priority) - Runtime overrides
2. **AWS Parameter Store** - Environment-specific secrets and configuration
3. **Local .env files** - Development defaults and static settings

**Parameter Store Structure**:
```
/anecdotario/{env}/commons-service/
├── photo-bucket-name      # Required S3 bucket name
├── photo-table-name       # Optional DynamoDB table override
└── allowed-origins        # Optional CORS origins
```

**Configuration Usage Pattern**:
```python
from config import config

# Get with fallbacks
bucket_name = config.get_ssm_parameter('photo-bucket-name')
max_size = config.get_int_parameter('max-image-size', 5242880)  # 5MB default
debug_enabled = config.get_bool_parameter('enable-debug-logging', False)
```

### Service Function Patterns

#### Photo Operations Pattern
- **Input**: Always includes `entity_type`, `entity_id`, `photo_type`
- **Processing**: Entity-agnostic with type-specific handling
- **S3 Structure**: `{entity_type}/{entity_id}/{photo_type}/{version}_{timestamp}_{hash}.jpg`
- **Cleanup**: Old photos automatically removed before new upload

#### Error Handling Pattern
```python
from utils import create_response, create_error_response

def lambda_handler(event, context):
    try:
        # Validation
        if not event.get('entity_type'):
            return create_error_response(400, 'entity_type is required', event)
        
        # Processing logic
        result = process_request(event)
        return create_response(200, json.dumps(result), event)
        
    except ValueError as e:
        return create_error_response(400, str(e), event)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_error_response(500, 'Internal server error', event)
```

### DynamoDB Model Architecture

#### Photo Model (`shared/models/photo.py`)
```python
class Photo(Model):
    class Meta:
        table_name = os.environ.get('PHOTO_TABLE_NAME', 'Photos-dev')
        region = 'us-east-1'
        
    # Primary key
    photo_id = UnicodeAttribute(hash_key=True)
    
    # Entity identification
    entity_type = UnicodeAttribute()  # user, org, campaign
    entity_id = UnicodeAttribute()    # nickname, org_id, etc.
    entity_key = UnicodeAttribute()   # Composite: {entity_type}#{entity_id}
    
    # Photo metadata
    photo_type = UnicodeAttribute()   # profile, logo, banner, gallery
    bucket_name = UnicodeAttribute()
    
    # S3 keys for different versions
    thumbnail_key = UnicodeAttribute()
    standard_key = UnicodeAttribute() 
    high_res_key = UnicodeAttribute()
    
    # URLs (thumbnail public, others presigned)
    thumbnail_url = UnicodeAttribute()
    
    # Global Secondary Indexes
    class EntityTypeIndex(GlobalSecondaryIndex):
        class Meta:
            index_name = 'entity-type-index'
            projection = AllProjection()
        entity_type = UnicodeAttribute(hash_key=True)
        created_at = UnicodeAttribute(range_key=True)
    
    class EntityPhotosIndex(GlobalSecondaryIndex):
        class Meta:
            index_name = 'entity-photos-index' 
            projection = AllProjection()
        entity_key = UnicodeAttribute(hash_key=True)
        created_at = UnicodeAttribute(range_key=True)
```

### Service Integration Patterns

#### From User Service
```python
import boto3
import json

lambda_client = boto3.client('lambda')

# Photo upload
response = lambda_client.invoke(
    FunctionName='anecdotario-photo-upload-dev',
    Payload=json.dumps({
        'image': 'data:image/jpeg;base64,...',
        'entity_type': 'user',
        'entity_id': user_nickname,
        'photo_type': 'profile',
        'uploaded_by': user_id,
        'upload_source': 'user-service'
    })
)

result = json.loads(response['Payload'].read())
if response['StatusCode'] == 200:
    photo_data = json.loads(result['body'])
    thumbnail_url = photo_data['thumbnail_url']
    standard_url = photo_data['standard_url']
```

#### From Org Service
```python
# Nickname validation with org-specific rules
response = lambda_client.invoke(
    FunctionName='anecdotario-nickname-validate-dev',
    Payload=json.dumps({
        'nickname': org_name,
        'entity_type': 'org'  # Uses org-specific reserved words
    })
)

validation_result = json.loads(response['Payload'].read())
if not validation_result.get('valid'):
    error_hints = validation_result['hints']  # User-friendly error messages
```

## CI/CD Pipeline Architecture

### Three-Stage Pipeline
1. **Build Stage**: Run tests, build SAM application, package artifacts
2. **Dev Deployment**: Auto-deploy to development on commit
3. **Staging Deployment**: Auto-deploy after dev success
4. **Prod Deployment**: Manual approval required

### Test Integration
- **Unit Tests**: Pytest for all functions with coverage reporting
- **Test Execution**: Automatic during build phase
- **Test Structure**: Each function has `tests/unit/` directory
- **Failed Tests**: Build continues but reports test failures

### Buildspec Structure (`pipeline/buildspec.yml`)
- **Dependencies**: Python 3.12, SAM CLI, pytest, boto3, Pillow, pynamodb
- **S3 Artifacts**: Creates SAM artifacts buckets if they don't exist
- **Parallel Building**: SAM build with `--parallel --cached` flags
- **Test Execution**: Tests all function directories automatically

## Environment-Specific Configuration

### Development (`samconfig-dev.toml`)
- **Stack**: `commons-service-dev`
- **Table**: `Photos-dev`
- **Bucket**: `anecdotario-photos-dev`
- **Region**: `us-east-1`

### Staging/Production
- Similar structure with environment-specific naming
- Production requires manual approval in pipeline
- Separate Parameter Store configurations per environment

## Function Specifications

### Photo Upload Function
- **Memory**: 512MB (image processing intensive)
- **Timeout**: 60 seconds
- **Concurrency**: 10 reserved
- **Dependencies**: Pillow for image processing

### Photo Delete Function
- **Memory**: 256MB
- **Timeout**: 30 seconds
- **Concurrency**: 5 reserved
- **Operations**: S3 batch delete, DynamoDB cleanup

### Photo Refresh Function
- **Memory**: 128MB (minimal processing)
- **Timeout**: 10 seconds
- **Concurrency**: 20 reserved
- **Purpose**: Generate new presigned URLs

### Nickname Validate Function
- **Memory**: 128MB
- **Timeout**: 5 seconds
- **Concurrency**: 50 reserved
- **Features**: Comprehensive validation with detailed error hints

## S3 Bucket Architecture

### Access Control Strategy
```yaml
# Bucket Policy Pattern
AllowPublicThumbnailAccess:
  Resource: "${Bucket}/*/*/*/thumbnail_*.jpg"  # Public read
  
DenyDirectPublicAccess:
  Resource:
    - "${Bucket}/*/*/*/standard_*.jpg"    # Protected
    - "${Bucket}/*/*/*/high_res_*.jpg"    # Protected
```

### File Naming Convention
- **Pattern**: `{version}_{timestamp}_{hash}.jpg`
- **Timestamp**: ISO format for sorting
- **Hash**: Short hash for uniqueness
- **Cleanup**: Old files automatically removed

## Development Best Practices

### Function Development
1. **Use shared utilities**: Import from `utils` module in layer
2. **Entity-agnostic design**: Always support `entity_type` parameter
3. **Comprehensive error handling**: Use `create_error_response` utility
4. **Input validation**: Validate all required parameters upfront
5. **Resource cleanup**: Clean up old resources when replacing

### Testing Strategy
1. **Unit tests**: Mock AWS services, test business logic
2. **Integration tests**: Use `sam local` with real AWS services
3. **Coverage**: Aim for >80% test coverage
4. **Test data**: Use realistic test events in `events/` directory

### Configuration Management
1. **Environment variables**: Use for overrides only
2. **Parameter Store**: Store environment-specific and sensitive config
3. **Local defaults**: Use `.env.defaults` for development settings
4. **Caching**: Configuration is cached in Lambda execution context

---

**Note**: This service is designed for internal microservice communication. Direct frontend access is not supported - all invocation should be through other Anecdotario services.

- Pipeline arn is arn:aws:codepipeline:us-east-1:871046834194:anecdotario-commons-pipeline
