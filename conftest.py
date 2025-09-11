"""
Pytest configuration and fixtures for anecdotario-commons-service tests
Provides comprehensive AWS mocking and common test data following TDD best practices
"""
import json
import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import MagicMock, patch
from datetime import datetime
import base64
from PIL import Image
import io


# Set test environment variables
os.environ.update({
    'AWS_DEFAULT_REGION': 'us-east-1',
    'AWS_ACCESS_KEY_ID': 'testing',
    'AWS_SECRET_ACCESS_KEY': 'testing',
    'AWS_SECURITY_TOKEN': 'testing',
    'AWS_SESSION_TOKEN': 'testing',
    'ENVIRONMENT': 'test',
    'PHOTO_TABLE_NAME': 'Photos-test',
    'USER_ORG_TABLE_NAME': 'UserOrg-test',
    'COMMONS_SERVICE_PHOTO_BUCKET_NAME': 'anecdotario-photos-test',
    'COMMONS_SERVICE_MAX_IMAGE_SIZE': '5242880',  # 5MB
    'COMMONS_SERVICE_PRESIGNED_URL_EXPIRY': '604800'  # 7 days
})


@pytest.fixture(scope='session', autouse=True)
def disable_network():
    """Disable network calls during tests"""
    try:
        import pytest_socket
        pytest_socket.disable_socket()
    except ImportError:
        # pytest-socket not installed, skip network disable
        pass


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto"""
    os.environ.update({
        'AWS_ACCESS_KEY_ID': 'testing',
        'AWS_SECRET_ACCESS_KEY': 'testing',
        'AWS_SECURITY_TOKEN': 'testing',
        'AWS_SESSION_TOKEN': 'testing'
    })


@pytest.fixture
def mock_config():
    """Mock configuration for tests"""
    class MockConfig:
        def __init__(self):
            self.environment = 'test'
            self.parameter_store_prefix = '/anecdotario/test/commons-service'
            
        # Properties for direct access
        @property
        def enable_debug_logging(self):
            return False
            
        @property
        def photo_table_name(self):
            return 'Photos-test'
            
        @property
        def user_org_table_name(self):
            return 'UserOrg-test'
            
        @property
        def photo_bucket_name(self):
            return 'anecdotario-photos-test'
            
        def get_parameter(self, key, default=None):
            """Mock parameter getter with common test values"""
            config_map = {
                'photo-table-name': 'Photos-test',
                'user-org-table-name': 'UserOrg-test',
                'photo-bucket-name': 'anecdotario-photos-test',
                'max-image-size': '5242880',
                'presigned-url-expiry': '604800',
                'allowed-image-types': 'image/jpeg,image/png,image/webp',
                'enable-debug-logging': 'false',
                'allowed-origins': '*'
            }
            return config_map.get(key, default)
            
        def get_ssm_parameter(self, key, default=None):
            return self.get_parameter(key, default)
            
        def get_int_parameter(self, key, default=0):
            value = self.get_parameter(key, default)
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
                
        def get_bool_parameter(self, key, default=False):
            value = self.get_parameter(key, default)
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes')
            return default
            
        def get_list_parameter(self, key, default=None, separator=','):
            value = self.get_parameter(key)
            if value is None:
                return default or []
            if isinstance(value, str):
                return [item.strip() for item in value.split(separator)]
            return default or []
            
        # Property getters for commonly used config
        @property
        def photo_table_name(self):
            return self.get_parameter('photo-table-name', 'Photos-test')
            
        @property
        def user_org_table_name(self):
            return self.get_parameter('user-org-table-name', 'UserOrg-test')
            
        @property
        def photo_bucket_name(self):
            return self.get_parameter('photo-bucket-name', 'anecdotario-photos-test')
            
        @property
        def max_image_size(self):
            return self.get_int_parameter('max-image-size', 5242880)
            
        @property
        def allowed_image_types(self):
            return self.get_list_parameter('allowed-image-types', ['image/jpeg', 'image/png', 'image/webp'])
            
        @property
        def presigned_url_expiry(self):
            return self.get_int_parameter('presigned-url-expiry', 604800)
            
        @property
        def enable_debug_logging(self):
            return self.get_bool_parameter('enable-debug-logging', False)
    
    return MockConfig()


@pytest.fixture
def mock_aws_services(aws_credentials, mock_config):
    """Setup all AWS services with moto mocking"""
    with mock_aws():
        # Mock the config module before any imports
        with patch('shared.config.config', mock_config):
            # Create DynamoDB tables
            create_test_tables(mock_config)
            
            # Create S3 buckets
            create_test_s3_buckets(mock_config)
            
            # Create SSM parameters
            create_test_ssm_parameters(mock_config)
            
            yield {
                'dynamodb': boto3.resource('dynamodb', region_name='us-east-1'),
                's3': boto3.client('s3', region_name='us-east-1'),
                'ssm': boto3.client('ssm', region_name='us-east-1')
            }


def create_test_tables(config):
    """Create DynamoDB test tables"""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    
    # Photo table
    photo_table = dynamodb.create_table(
        TableName=config.photo_table_name,
        KeySchema=[
            {'AttributeName': 'photo_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'photo_id', 'AttributeType': 'S'},
            {'AttributeName': 'entity_type', 'AttributeType': 'S'},
            {'AttributeName': 'entity_key', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'entity-type-index',
                'KeySchema': [
                    {'AttributeName': 'entity_type', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            },
            {
                'IndexName': 'entity-photos-index',
                'KeySchema': [
                    {'AttributeName': 'entity_key', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # UserOrg table
    user_org_table = dynamodb.create_table(
        TableName=config.user_org_table_name,
        KeySchema=[
            {'AttributeName': 'nickname', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'nickname', 'AttributeType': 'S'},
            {'AttributeName': 'user_type', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'user-type-index',
                'KeySchema': [
                    {'AttributeName': 'user_type', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Wait for tables to be created
    photo_table.wait_until_exists()
    user_org_table.wait_until_exists()


def create_test_s3_buckets(config):
    """Create S3 test buckets"""
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket=config.photo_bucket_name)


def create_test_ssm_parameters(config):
    """Create SSM test parameters"""
    ssm = boto3.client('ssm', region_name='us-east-1')
    
    parameters = [
        {'Name': f'{config.parameter_store_prefix}/photo-table-name', 'Value': config.photo_table_name},
        {'Name': f'{config.parameter_store_prefix}/user-org-table-name', 'Value': config.user_org_table_name},
        {'Name': f'{config.parameter_store_prefix}/photo-bucket-name', 'Value': config.photo_bucket_name},
        {'Name': f'{config.parameter_store_prefix}/max-image-size', 'Value': str(config.max_image_size)},
        {'Name': f'{config.parameter_store_prefix}/presigned-url-expiry', 'Value': str(config.presigned_url_expiry)},
        {'Name': f'{config.parameter_store_prefix}/allowed-origins', 'Value': '*'}
    ]
    
    for param in parameters:
        ssm.put_parameter(**param, Type='String')


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = MagicMock()
    context.function_name = 'test-function'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = 'test-request-id'
    return context


@pytest.fixture
def api_gateway_event():
    """Mock API Gateway event"""
    return {
        'httpMethod': 'POST',
        'path': '/test',
        'resource': '/test',
        'requestContext': {
            'accountId': '123456789012',
            'apiId': 'test-api',
            'stage': 'test',
            'requestId': 'test-request-id',
            'identity': {
                'sourceIp': '127.0.0.1'
            },
            'authorizer': {
                'claims': {
                    'sub': 'test-user-123',
                    'email': 'test@example.com',
                    'cognito:username': 'test_user'
                }
            }
        },
        'headers': {
            'Content-Type': 'application/json'
        },
        'queryStringParameters': None,
        'body': json.dumps({}),
        'isBase64Encoded': False
    }


@pytest.fixture
def direct_lambda_event():
    """Mock direct Lambda invocation event"""
    return {
        'source': 'lambda.direct',
        'detail': {}
    }


# Test data fixtures
@pytest.fixture
def sample_test_image():
    """Generate a test image in base64 format"""
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=85)
    img_bytes.seek(0)
    
    # Convert to base64
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
    return f'data:image/jpeg;base64,{img_base64}'


@pytest.fixture
def sample_photo_data():
    """Sample photo data for testing"""
    return {
        'photo_id': 'test-photo-123',
        'entity_type': 'user',
        'entity_id': 'test_user',
        'photo_type': 'profile',
        'bucket_name': 'anecdotario-photos-test',
        'thumbnail_key': 'user/test_user/profile/thumbnail_20240101_abc123.jpg',
        'standard_key': 'user/test_user/profile/standard_20240101_abc123.jpg',
        'high_res_key': 'user/test_user/profile/high_res_20240101_abc123.jpg',
        'thumbnail_url': 'https://anecdotario-photos-test.s3.amazonaws.com/user/test_user/profile/thumbnail_20240101_abc123.jpg',
        'file_size': 1024,
        'processed_sizes': {'thumbnail': 512, 'standard': 768, 'high_res': 1024},
        'image_format': 'JPEG',
        'image_dimensions': {'width': 100, 'height': 100},
        'uploaded_by': 'test-user-123',
        'upload_source': 'user-service'
    }


@pytest.fixture
def sample_user_org_data():
    """Sample user/org data for testing"""
    return {
        'user': {
            'nickname': 'test_user',
            'full_name': 'Test User',
            'user_type': 'user',
            'email': 'test@example.com',
            'status': 'active',
            'is_certified': False
        },
        'org': {
            'nickname': 'test_org',
            'full_name': 'Test Organization',
            'user_type': 'organization',
            'website': 'https://test.org',
            'status': 'active',
            'is_certified': True
        }
    }


@pytest.fixture
def valid_photo_upload_event(api_gateway_event, sample_test_image):
    """Valid photo upload event"""
    api_gateway_event['body'] = json.dumps({
        'image': sample_test_image,
        'entity_type': 'user',
        'entity_id': 'test_user',
        'photo_type': 'profile',
        'uploaded_by': 'test-user-123',
        'upload_source': 'user-service'
    })
    return api_gateway_event


@pytest.fixture
def valid_nickname_event(api_gateway_event):
    """Valid nickname validation event"""
    api_gateway_event['body'] = json.dumps({
        'nickname': 'test_user',
        'entity_type': 'user'
    })
    return api_gateway_event


@pytest.fixture
def valid_user_org_create_event(api_gateway_event, sample_user_org_data):
    """Valid user-org creation event"""
    api_gateway_event['body'] = json.dumps(sample_user_org_data['user'])
    return api_gateway_event


@pytest.fixture
def mock_services():
    """Mock all shared services"""
    services = {}
    
    # Photo service mock
    photo_service = MagicMock()
    photo_service.upload_photo.return_value = {
        'photo_id': 'test-photo-123',
        'urls': {
            'thumbnail': 'https://example.com/thumbnail.jpg',
            'standard': 'https://example.com/standard.jpg',
            'high_res': 'https://example.com/high_res.jpg'
        },
        'metadata': {'file_size': 1024},
        'cleanup_result': {'deleted_count': 0}
    }
    photo_service.delete_photo.return_value = {'success': True}
    photo_service.refresh_photo_urls.return_value = {
        'photo_id': 'test-photo-123',
        'urls': {
            'standard': 'https://example.com/standard.jpg',
            'high_res': 'https://example.com/high_res.jpg'
        }
    }
    services['photo_service'] = photo_service
    
    # User-org service mock  
    user_org_service = MagicMock()
    user_org_service.create_entity.return_value = {
        'nickname': 'test_user',
        'full_name': 'Test User',
        'user_type': 'user',
        'status': 'active'
    }
    user_org_service.get_entity.return_value = {
        'nickname': 'test_user',
        'full_name': 'Test User',
        'user_type': 'user'
    }
    user_org_service.update_entity.return_value = {
        'nickname': 'test_user',
        'full_name': 'Updated User',
        'user_type': 'user'
    }
    user_org_service.delete_entity.return_value = {'success': True}
    user_org_service.search_entities.return_value = {
        'results': [],
        'total_count': 0,
        'has_more': False
    }
    services['user_org_service'] = user_org_service
    
    # Nickname validator mock
    nickname_validator = MagicMock()
    nickname_validator.validate.return_value = {
        'valid': True,
        'original': 'test_user',
        'normalized': 'test_user',
        'entity_type': 'user',
        'errors': [],
        'warnings': [],
        'hints': ['Great choice! This nickname follows all the rules.']
    }
    nickname_validator.get_validation_rules.return_value = {
        'length': {'min': 3, 'max': 30},
        'characters': {'allowed': 'a-z, 0-9, _'}
    }
    services['nickname_validator'] = nickname_validator
    
    return services


@pytest.fixture
def patch_shared_imports():
    """Patch shared module imports for testing"""
    shared_patches = [
        patch('shared.config.config'),
        patch('shared.utils.create_response'),
        patch('shared.utils.create_error_response'),
        patch('shared.services.service_container.get_service'),
        patch('shared.logger.photo_logger'),
        patch('shared.logger.user_org_logger')
    ]
    
    mock_objects = {}
    for p in shared_patches:
        mock_obj = p.start()
        # Extract the last part of the patch path for the key
        key = p.attribute or p.new
        if hasattr(p, 'attribute') and p.attribute:
            key = p.attribute.split('.')[-1]
        mock_objects[key] = mock_obj
    
    # Configure create_response mock
    if 'create_response' in mock_objects:
        mock_objects['create_response'].return_value = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': True})
        }
    
    # Configure create_error_response mock
    if 'create_error_response' in mock_objects:
        mock_objects['create_error_response'].return_value = {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Test error'})
        }
    
    yield mock_objects
    
    # Stop all patches
    for p in shared_patches:
        p.stop()


@pytest.fixture
def mock_boto3_clients():
    """Mock boto3 clients for direct service testing"""
    with patch('boto3.client') as mock_client, patch('boto3.resource') as mock_resource:
        # S3 client mock
        s3_client = MagicMock()
        s3_client.put_object.return_value = {'ETag': '"test-etag"'}
        s3_client.delete_objects.return_value = {'Deleted': []}
        s3_client.generate_presigned_url.return_value = 'https://example.com/presigned-url'
        
        # DynamoDB resource mock
        dynamodb_resource = MagicMock()
        
        # SSM client mock
        ssm_client = MagicMock()
        ssm_client.get_parameter.return_value = {'Parameter': {'Value': 'test-value'}}
        
        # Configure the mock to return appropriate clients
        def client_side_effect(service_name, **kwargs):
            if service_name == 's3':
                return s3_client
            elif service_name == 'ssm':
                return ssm_client
            return MagicMock()
            
        def resource_side_effect(service_name, **kwargs):
            if service_name == 'dynamodb':
                return dynamodb_resource
            return MagicMock()
        
        mock_client.side_effect = client_side_effect
        mock_resource.side_effect = resource_side_effect
        
        yield {
            's3': s3_client,
            'dynamodb': dynamodb_resource,
            'ssm': ssm_client
        }