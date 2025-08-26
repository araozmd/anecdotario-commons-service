# Anecdotario Commons Service

**Shared functionality service for all Anecdotario entities (users, orgs, campaigns)**

This service provides common functionality used across multiple Anecdotario microservices, including photo upload/processing and nickname validation with consistent rules.

## 🎯 Purpose

The Commons Service centralizes shared functionality to ensure consistency across all entity types:
- **Photo Operations**: Upload, delete, and refresh presigned URLs for photos
- **Nickname Validation**: Comprehensive validation with detailed error hints
- **Future Expansions**: Ready for additional common utilities

## 🏗️ Architecture

### Technology Stack
- **Runtime**: Python 3.12 LTS on AWS Lambda
- **Storage**: S3 for photos, DynamoDB for metadata
- **Framework**: AWS SAM (Serverless Application Model)
- **Configuration**: Hybrid (local .env + AWS Parameter Store)

### Service Structure
```
anecdotario-commons-service/
├── photo-upload/           # Photo upload with multi-version processing
├── photo-delete/          # Photo deletion with S3 cleanup
├── photo-refresh/         # Presigned URL regeneration
├── nickname-validate/     # Nickname validation with hints
├── shared/                # Shared modules and configuration
│   ├── config.py         # Configuration manager
│   ├── models/           # DynamoDB models
│   ├── processors/       # Image processing
│   ├── validators/       # Validation utilities
│   └── utils.py          # Common utilities
├── pipeline/             # CI/CD configuration
└── events/               # Test events
```

## 📋 Functions

### 1. Photo Upload
- **Function**: `photo-upload`
- **Purpose**: Upload and process photos for any entity type
- **Features**:
  - Multi-version creation (thumbnail, standard, high-res)
  - Instagram-style square cropping
  - Automatic cleanup of old photos
  - Entity-agnostic design

### 2. Photo Delete
- **Function**: `photo-delete`
- **Purpose**: Delete photos and cleanup S3 objects
- **Features**:
  - Delete by photo ID or entity
  - Batch S3 cleanup
  - Database record removal

### 3. Photo Refresh
- **Function**: `photo-refresh`
- **Purpose**: Regenerate presigned URLs for protected photos
- **Features**:
  - Individual photo refresh
  - Entity photo refresh
  - Current photo retrieval

### 4. Nickname Validation
- **Function**: `nickname-validate`
- **Purpose**: Validate nicknames with detailed error hints
- **Features**:
  - Comprehensive validation rules
  - Entity-specific reserved words
  - Detailed error hints for frontend
  - Validation rules API

## 🚀 Deployment

### Prerequisites
- Python 3.12
- AWS SAM CLI
- AWS CLI configured
- GitHub repository access

### Environment Setup
```bash
# Set Python version
pyenv local 3.12.8

# Install dependencies
pip install aws-sam-cli boto3 pytest

# Configure AWS credentials
aws configure
```

### Deploy Pipeline (Recommended)
```bash
# Deploy CI/CD pipeline
./deploy-pipeline.sh <your-github-token>

# Subscribe to approval notifications
aws sns subscribe \
  --topic-arn <approval-topic-arn> \
  --protocol email \
  --notification-endpoint your-email@example.com
```

### Manual Deployment
```bash
# Build and deploy to development
sam build
sam deploy --config-file samconfig-dev.toml

# Deploy to staging
sam deploy --config-file samconfig-staging.toml

# Deploy to production (requires approval in pipeline)
sam deploy --config-file samconfig-prod.toml
```

## ⚙️ Configuration

### Parameter Store
Required parameters (per environment):
```
/anecdotario/{env}/commons-service/
├── photo-bucket-name          # S3 bucket for photos
├── photo-table-name           # DynamoDB table (optional override)
└── allowed-origins            # CORS origins (optional)
```

### Local Configuration
Static settings in `shared/.env.defaults`:
- Image processing settings
- Validation rules
- Performance tuning
- Feature flags

## 📖 API Usage

### Photo Upload
```json
POST (invoke directly)
{
  "image": "data:image/jpeg;base64,...",
  "entity_type": "user|org|campaign",
  "entity_id": "nickname_or_id",
  "photo_type": "profile|logo|banner",
  "uploaded_by": "user_id",
  "upload_source": "user-service"
}
```

### Photo Delete
```json
POST (invoke directly)
{
  "photo_id": "photo_123"
}
// OR
{
  "entity_type": "user",
  "entity_id": "john_doe",
  "photo_type": "profile"
}
```

### Photo Refresh
```json
POST (invoke directly)
{
  "entity_type": "user",
  "entity_id": "john_doe",
  "photo_type": "profile",
  "get_current": true
}
```

### Nickname Validation
```json
POST (invoke directly)
{
  "nickname": "test_user",
  "entity_type": "user"
}

Response:
{
  "valid": false,
  "error": "Nickname contains invalid characters",
  "hints": [
    "Only lowercase letters (a-z), digits (0-9), and underscores (_) are allowed",
    "Invalid characters found: A"
  ]
}
```

## 🎨 S3 Bucket Structure

```
anecdotario-photos-{env}/
├── users/
│   └── {nickname}/
│       └── profile/
│           ├── thumbnail_20241225_abc123.jpg   # 150x150, public
│           ├── standard_20241225_abc123.jpg    # 320x320, protected
│           └── high_res_20241225_abc123.jpg    # 800x800, protected
├── orgs/
│   └── {org_nickname}/
│       ├── logo/
│       └── banner/
└── campaigns/
    └── {campaign_id}/
        └── gallery/
```

## 🧪 Testing

### Unit Tests
```bash
# Test specific function
cd photo-upload && pytest tests/ -v

# Test nickname validation
cd nickname-validate && pytest tests/ -v
```

### Integration Tests
```bash
# Test with SAM local
sam local invoke PhotoUploadFunction --event events/photo-event.json
sam local invoke NicknameValidateFunction --event events/nickname-event.json
```

### Load Testing
```bash
# Example with Apache Bench
ab -n 100 -c 10 -T application/json \
   -p test-nickname.json \
   "https://lambda-url/nickname-validate"
```

## 🔍 Monitoring

### CloudWatch Logs
```bash
# View logs for specific function
sam logs -n PhotoUploadFunction --stack-name commons-service-dev --tail
sam logs -n NicknameValidateFunction --stack-name commons-service-dev --tail
```

### Metrics
- **Photo Upload**: Duration, memory usage, error rate
- **Nickname Validation**: Request volume, validation failures
- **S3 Operations**: Upload/delete success rates

## 🔧 Development

### Adding New Shared Functions
1. Create function directory: `new-function/`
2. Add function to `template.yaml`
3. Update CI/CD buildspec if needed
4. Add tests and documentation

### Local Development
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run formatters and linters
black shared/ */app.py
pylint shared/ */app.py

# Start local API (if needed for testing)
sam local start-api --port 3000
```

## 🚨 Troubleshooting

### Common Issues

1. **Permission Errors**
   - Verify IAM roles have required permissions
   - Check Parameter Store access

2. **Image Processing Failures**
   - Validate image format and size
   - Check Pillow installation

3. **S3 Access Denied**
   - Verify bucket policies
   - Check CORS configuration

4. **Validation Errors**
   - Review nickname rules
   - Check reserved words list

### Debug Mode
Set `ENABLE_DEBUG_LOGGING=true` in environment for detailed logs.

## 📈 Performance

### Optimization Settings
- **Memory**: Right-sized per function (128-512MB)
- **Timeout**: Optimized for function complexity (5-60s)
- **Concurrency**: Reserved concurrency to prevent throttling

### Cost Optimization
- **Pay-per-request**: DynamoDB and Lambda billing
- **S3 Lifecycle**: Automatic cleanup of incomplete uploads
- **Image Caching**: Long-lived S3 cache headers

## 🔐 Security

### Best Practices Implemented
- ✅ Least privilege IAM roles
- ✅ Encrypted Parameter Store values
- ✅ S3 bucket policies for public/private access
- ✅ Input validation and sanitization
- ✅ Reserved word filtering
- ✅ CORS configuration

## 🎯 Usage by Other Services

### User Service Integration
```python
import boto3

# Invoke photo upload
lambda_client = boto3.client('lambda')
response = lambda_client.invoke(
    FunctionName='anecdotario-photo-upload-dev',
    Payload=json.dumps({
        'image': image_data,
        'entity_type': 'user',
        'entity_id': user_nickname,
        'photo_type': 'profile'
    })
)

# Invoke nickname validation
response = lambda_client.invoke(
    FunctionName='anecdotario-nickname-validate-dev',
    Payload=json.dumps({
        'nickname': nickname,
        'entity_type': 'user'
    })
)
```

### Org Service Integration
```python
# Same pattern for organizations
response = lambda_client.invoke(
    FunctionName='anecdotario-nickname-validate-dev',
    Payload=json.dumps({
        'nickname': org_name,
        'entity_type': 'org'
    })
)
```

## 🎖️ Best Practices

1. **Always validate input** before processing
2. **Use entity-specific validation** when needed
3. **Handle errors gracefully** with detailed messages
4. **Clean up resources** (photos) when replacing
5. **Monitor performance** and optimize as needed
6. **Test thoroughly** before deployment
7. **Document changes** and API updates

---

**Note**: This service is designed to be invoked by other microservices, not directly by frontend applications. All authentication and authorization should be handled by the calling service.