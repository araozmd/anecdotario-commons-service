"""
Tests for User-Organization Create Lambda Function
"""
import json
import pytest
import os
import sys
from moto import mock_dynamodb
import boto3

# Add shared directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

# Mock configuration for testing
class MockConfig:
    def get_ssm_parameter(self, name, default=None):
        return default
    
    def get_int_parameter(self, name, default=0):
        return default
    
    def get_bool_parameter(self, name, default=False):
        return default
    
    def get_parameter(self, name, default=None):
        return default
    
    def get_env(self, name, default=None):
        return os.environ.get(name, default)

# Patch config before importing app
import shared.config
shared.config.config = MockConfig()

from shared.models.user_org import UserOrg
from shared.services.user_org_service import UserOrgService
from shared.exceptions import ValidationError, DuplicateEntityError


class TestUserOrgCreate:
    """Test suite for user-org create functionality"""
    
    @pytest.fixture
    def dynamodb_setup(self):
        """Set up mock DynamoDB for testing"""
        with mock_dynamodb():
            # Set environment variable for table name
            os.environ['USER_ORG_TABLE_NAME'] = 'UserOrg-test'
            
            # Create the table
            UserOrg.create_table(read_capacity_units=5, write_capacity_units=5, wait=True)
            yield
    
    @pytest.fixture
    def user_org_service(self, dynamodb_setup):
        """Create UserOrgService instance for testing"""
        return UserOrgService()
    
    @pytest.fixture
    def valid_user_data(self):
        """Valid user creation data"""
        return {
            'nickname': 'john_doe',
            'full_name': 'John Doe',
            'user_type': 'user',
            'email': 'john@example.com',
            'avatar_thumbnail_url': 'https://example.com/avatar.jpg'
        }
    
    @pytest.fixture
    def valid_org_data(self):
        """Valid organization creation data"""
        return {
            'nickname': 'acme_corp',
            'full_name': 'ACME Corporation',
            'user_type': 'organization',
            'website': 'https://acme.com',
            'is_certified': True
        }
    
    def test_create_user_success(self, user_org_service, valid_user_data):
        """Test successful user creation"""
        result = user_org_service.create_entity(**valid_user_data)
        
        assert result['nickname'] == 'john_doe'
        assert result['full_name'] == 'John Doe'
        assert result['user_type'] == 'user'
        assert result['email'] == 'john@example.com'
        assert result['avatar_thumbnail_url'] == 'https://example.com/avatar.jpg'
        assert result['status'] == 'active'
        assert result['is_certified'] is False
        assert 'created_at' in result
        
        # Verify entity exists in database
        assert UserOrg.nickname_exists('john_doe')
    
    def test_create_organization_success(self, user_org_service, valid_org_data):
        """Test successful organization creation"""
        result = user_org_service.create_entity(**valid_org_data)
        
        assert result['nickname'] == 'acme_corp'
        assert result['full_name'] == 'ACME Corporation'
        assert result['user_type'] == 'organization'
        assert result['website'] == 'https://acme.com'
        assert result['is_certified'] is True
        assert result['status'] == 'active'
        
        # Verify entity exists in database
        assert UserOrg.nickname_exists('acme_corp')
    
    def test_create_duplicate_nickname_fails(self, user_org_service, valid_user_data):
        """Test that duplicate nickname creation fails"""
        # Create first entity
        user_org_service.create_entity(**valid_user_data)
        
        # Try to create another with same nickname
        org_data = {
            'nickname': 'john_doe',  # Same nickname
            'full_name': 'John Doe Organization',
            'user_type': 'organization'
        }
        
        with pytest.raises(DuplicateEntityError) as exc_info:
            user_org_service.create_entity(**org_data)
        
        assert 'already exists' in str(exc_info.value)
    
    def test_create_invalid_nickname_fails(self, user_org_service):
        """Test that invalid nicknames fail validation"""
        invalid_data = {
            'nickname': 'Invalid Name!',  # Spaces and special chars not allowed
            'full_name': 'Invalid User',
            'user_type': 'user'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**invalid_data)
        
        assert 'lowercase letters' in str(exc_info.value)
    
    def test_create_invalid_user_type_fails(self, user_org_service):
        """Test that invalid user_type fails validation"""
        invalid_data = {
            'nickname': 'test_user',
            'full_name': 'Test User',
            'user_type': 'invalid_type'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**invalid_data)
        
        assert 'Invalid user_type' in str(exc_info.value)
    
    def test_create_missing_required_fields_fails(self, user_org_service):
        """Test that missing required fields fail validation"""
        # Missing full_name
        with pytest.raises(ValidationError):
            user_org_service.create_entity(
                nickname='test_user',
                user_type='user'
                # full_name missing
            )
        
        # Missing user_type
        with pytest.raises(ValidationError):
            user_org_service.create_entity(
                nickname='test_user',
                full_name='Test User'
                # user_type missing
            )
    
    def test_create_nickname_normalization(self, user_org_service):
        """Test that nicknames are properly normalized"""
        data = {
            'nickname': 'JoHn_DoE',  # Mixed case
            'full_name': 'John Doe',
            'user_type': 'user'
        }
        
        result = user_org_service.create_entity(**data)
        
        # Should be normalized to lowercase
        assert result['nickname'] == 'john_doe'
        assert UserOrg.nickname_exists('john_doe')
        assert not UserOrg.nickname_exists('JoHn_DoE')  # Original case should not exist
    
    def test_create_reserved_nickname_fails(self, user_org_service):
        """Test that reserved nicknames fail validation"""
        reserved_data = {
            'nickname': 'admin',  # Reserved word
            'full_name': 'Admin User',
            'user_type': 'user'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**reserved_data)
        
        assert 'reserved word' in str(exc_info.value)
    
    def test_create_with_invalid_email_fails(self, user_org_service):
        """Test that invalid email format fails validation"""
        data = {
            'nickname': 'test_user',
            'full_name': 'Test User',
            'user_type': 'user',
            'email': 'invalid-email-format'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**data)
        
        assert 'email' in str(exc_info.value).lower()
    
    def test_create_with_invalid_website_fails(self, user_org_service):
        """Test that invalid website URL fails validation"""
        data = {
            'nickname': 'test_org',
            'full_name': 'Test Organization',
            'user_type': 'organization',
            'website': 'not-a-valid-url'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**data)
        
        assert 'website' in str(exc_info.value).lower()
    
    def test_create_nickname_uniqueness_across_types(self, user_org_service):
        """Test that nicknames must be unique across users AND organizations"""
        # Create a user
        user_data = {
            'nickname': 'shared_name',
            'full_name': 'User Name',
            'user_type': 'user'
        }
        user_org_service.create_entity(**user_data)
        
        # Try to create organization with same nickname
        org_data = {
            'nickname': 'shared_name',
            'full_name': 'Organization Name',
            'user_type': 'organization'
        }
        
        with pytest.raises(DuplicateEntityError):
            user_org_service.create_entity(**org_data)
    
    def test_create_minimum_nickname_length(self, user_org_service):
        """Test minimum nickname length validation"""
        data = {
            'nickname': 'ab',  # Too short (less than 3 chars)
            'full_name': 'Short Name',
            'user_type': 'user'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**data)
        
        assert 'at least' in str(exc_info.value)
    
    def test_create_maximum_nickname_length(self, user_org_service):
        """Test maximum nickname length validation"""
        data = {
            'nickname': 'a' * 50,  # Too long (more than 30 chars)
            'full_name': 'Long Name',
            'user_type': 'user'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            user_org_service.create_entity(**data)
        
        assert 'cannot exceed' in str(exc_info.value)


class TestUserOrgModel:
    """Test suite for UserOrg model methods"""
    
    @pytest.fixture
    def dynamodb_setup(self):
        """Set up mock DynamoDB for testing"""
        with mock_dynamodb():
            os.environ['USER_ORG_TABLE_NAME'] = 'UserOrg-test'
            UserOrg.create_table(read_capacity_units=5, write_capacity_units=5, wait=True)
            yield
    
    @pytest.fixture
    def sample_entities(self, dynamodb_setup):
        """Create sample entities for testing"""
        # Create a user
        user = UserOrg(
            nickname='test_user',
            full_name='Test User',
            user_type='user',
            email='user@test.com'
        )
        user.save()
        
        # Create an organization
        org = UserOrg(
            nickname='test_org',
            full_name='Test Organization',
            user_type='organization',
            is_certified=True,
            website='https://test.org'
        )
        org.save()
        
        return {'user': user, 'org': org}
    
    def test_nickname_exists(self, sample_entities):
        """Test nickname_exists method"""
        assert UserOrg.nickname_exists('test_user')
        assert UserOrg.nickname_exists('test_org')
        assert not UserOrg.nickname_exists('nonexistent_user')
    
    def test_get_by_nickname(self, sample_entities):
        """Test get_by_nickname method"""
        user = UserOrg.get_by_nickname('test_user')
        assert user is not None
        assert user.nickname == 'test_user'
        assert user.user_type == 'user'
        
        org = UserOrg.get_by_nickname('test_org')
        assert org is not None
        assert org.nickname == 'test_org'
        assert org.user_type == 'organization'
        
        nonexistent = UserOrg.get_by_nickname('nonexistent')
        assert nonexistent is None
    
    def test_to_dict(self, sample_entities):
        """Test to_dict method"""
        user = UserOrg.get_by_nickname('test_user')
        user_dict = user.to_dict()
        
        assert user_dict['nickname'] == 'test_user'
        assert user_dict['full_name'] == 'Test User'
        assert user_dict['user_type'] == 'user'
        assert user_dict['email'] == 'user@test.com'
        assert 'created_at' in user_dict
        assert 'updated_at' in user_dict
    
    def test_to_public_dict(self, sample_entities):
        """Test to_public_dict method excludes sensitive info"""
        user = UserOrg.get_by_nickname('test_user')
        public_dict = user.to_public_dict()
        
        assert public_dict['nickname'] == 'test_user'
        assert public_dict['full_name'] == 'Test User'
        assert public_dict['user_type'] == 'user'
        
        # Should not include email or phone in public dict
        assert 'email' not in public_dict
        assert 'phone' not in public_dict
    
    def test_update_stats(self, sample_entities):
        """Test update_stats method"""
        user = UserOrg.get_by_nickname('test_user')
        original_followers = user.followers_count
        
        user.update_stats(followers_delta=5, posts_delta=2)
        
        # Refresh from database
        updated_user = UserOrg.get_by_nickname('test_user')
        assert updated_user.followers_count == original_followers + 5
        assert updated_user.posts_count == 2
    
    def test_certification_status(self, sample_entities):
        """Test set_certification_status method"""
        user = UserOrg.get_by_nickname('test_user')
        assert not user.is_certified
        
        user.set_certification_status(True, 'admin')
        
        # Refresh from database
        updated_user = UserOrg.get_by_nickname('test_user')
        assert updated_user.is_certified