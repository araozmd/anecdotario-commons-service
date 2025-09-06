"""
Shared test configuration and fixtures
"""
import json
import pytest
import boto3
from moto import mock_dynamodb, mock_s3
from unittest.mock import Mock, patch


@pytest.fixture
def mock_aws_credentials():
    """Mock AWS credentials for testing"""
    import os
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    config_mock = Mock()
    config_mock.get_parameter.return_value = None
    config_mock.get_int_parameter.side_effect = lambda name, default: default
    config_mock.get_bool_parameter.side_effect = lambda name, default: default
    config_mock.get_ssm_parameter.return_value = None
    return config_mock


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = Mock()
    context.function_name = 'test-function'
    context.function_version = '1'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    context.memory_limit_in_mb = '128'
    context.remaining_time_in_millis.return_value = 30000
    context.aws_request_id = 'test-request-id'
    return context


@pytest.fixture
def api_gateway_event():
    """Standard API Gateway event for testing"""
    return {
        'httpMethod': 'POST',
        'path': '/test',
        'queryStringParameters': {},
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': None,
        'requestContext': {
            'requestId': 'test-request-id',
            'authorizer': {
                'claims': {
                    'sub': 'test-user-123',
                    'email': 'test@example.com'
                }
            }
        }
    }


@pytest.fixture
def valid_photo_upload_event(api_gateway_event):
    """Valid photo upload event"""
    api_gateway_event['body'] = json.dumps({
        'image': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/gA==',
        'entity_type': 'user',
        'entity_id': 'test_user',
        'photo_type': 'profile',
        'uploaded_by': 'test-user-123'
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
def mock_dynamodb():
    """Mock DynamoDB for testing"""
    with mock_dynamodb():
        # Create mock table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='Photos-dev',
            KeySchema=[
                {
                    'AttributeName': 'photo_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'photo_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        yield table


@pytest.fixture
def mock_s3():
    """Mock S3 for testing"""
    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='anecdotario-photos-dev')
        yield s3


@pytest.fixture
def sample_photo_record():
    """Sample photo record for testing"""
    return {
        'photo_id': 'test-photo-123',
        'entity_type': 'user',
        'entity_id': 'test_user',
        'entity_key': 'user#test_user',
        'photo_type': 'profile',
        'bucket_name': 'anecdotario-photos-dev',
        'thumbnail_key': 'users/test_user/profile/thumbnail_test-photo-123.jpg',
        'standard_key': 'users/test_user/profile/standard_test-photo-123.jpg',
        'high_res_key': 'users/test_user/profile/high_res_test-photo-123.jpg',
        'thumbnail_url': 'https://anecdotario-photos-dev.s3.amazonaws.com/users/test_user/profile/thumbnail_test-photo-123.jpg',
        'created_at': '2023-12-01T10:00:00Z',
        'updated_at': '2023-12-01T10:00:00Z',
        'uploaded_by': 'test-user-123',
        'file_size': 1024,
        'content_type': 'image/jpeg'
    }