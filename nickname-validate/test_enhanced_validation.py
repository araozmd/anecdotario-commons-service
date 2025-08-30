#!/usr/bin/env python3
"""
Enhanced nickname validation test
Tests the integration between nickname validator and unified user-org table
"""
import json
import pytest
import os
import sys
from moto import mock_dynamodb
import boto3

# Add shared directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

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

# Patch config before importing modules
import shared.config
shared.config.config = MockConfig()

from shared.validators.nickname import nickname_validator
from shared.models.user_org import UserOrg
from shared.services.user_org_service import UserOrgService


class TestEnhancedNicknameValidation:
    """Test suite for enhanced nickname validation with user-org integration"""
    
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
    def sample_entities(self, user_org_service):
        """Create sample entities for testing uniqueness"""
        # Create a user
        user_org_service.create_entity(
            nickname='existing_user',
            full_name='Existing User',
            user_type='user'
        )
        
        # Create an organization
        user_org_service.create_entity(
            nickname='existing_org',
            full_name='Existing Organization',
            user_type='organization'
        )
        
        return {
            'user_nickname': 'existing_user',
            'org_nickname': 'existing_org'
        }
    
    def test_unique_nickname_validation_passes(self, sample_entities):
        """Test that unique nicknames pass validation"""
        result = nickname_validator.validate('new_unique_user', 'user')
        
        assert result['valid'] is True
        assert not result['errors']
        assert result['normalized'] == 'new_unique_user'
    
    def test_duplicate_user_nickname_fails(self, sample_entities):
        """Test that duplicate user nickname fails validation"""
        result = nickname_validator.validate('existing_user', 'user')
        
        assert result['valid'] is False
        assert any('already taken' in error for error in result['errors'])
        assert result['normalized'] == 'existing_user'
        assert 'Suggestions:' in ' '.join(result['hints'])
    
    def test_duplicate_org_nickname_fails(self, sample_entities):
        """Test that duplicate org nickname fails validation"""
        result = nickname_validator.validate('existing_org', 'organization')
        
        assert result['valid'] is False
        assert any('already taken' in error for error in result['errors'])
        assert result['normalized'] == 'existing_org'
    
    def test_cross_entity_uniqueness(self, sample_entities):
        """Test that user cannot use org nickname and vice versa"""
        # Try to create user with existing org nickname
        result = nickname_validator.validate('existing_org', 'user')
        assert result['valid'] is False
        assert any('already taken' in error for error in result['errors'])
        
        # Try to create org with existing user nickname
        result = nickname_validator.validate('existing_user', 'organization')
        assert result['valid'] is False
        assert any('already taken' in error for error in result['errors'])
    
    def test_case_insensitive_uniqueness(self, sample_entities):
        """Test that nicknames are unique regardless of case"""
        # Test variations of existing user nickname
        test_cases = [
            'EXISTING_USER',
            'Existing_User',
            'existing_USER',
            'ExIsTiNg_UsEr'
        ]
        
        for test_nickname in test_cases:
            result = nickname_validator.validate(test_nickname, 'user')
            assert result['valid'] is False
            assert any('already taken' in error for error in result['errors'])
            assert result['normalized'] == 'existing_user'
    
    def test_validation_with_other_rules(self, sample_entities):
        """Test that uniqueness check works alongside other validation rules"""
        # Test nickname that's both duplicate and has other issues
        result = nickname_validator.validate('existing_user!', 'user')
        
        assert result['valid'] is False
        # Should have both uniqueness error and character validation error
        errors = ' '.join(result['errors'])
        assert 'already taken' in errors
        assert 'Invalid characters' in errors
    
    def test_suggestions_provided(self, sample_entities):
        """Test that helpful suggestions are provided for duplicate nicknames"""
        result = nickname_validator.validate('existing_user', 'user')
        
        assert result['valid'] is False
        hints = ' '.join(result['hints'])
        
        # Should suggest alternatives
        assert 'existing_user1' in hints or 'existing_user_user' in hints
        assert 'Try adding' in hints
    
    def test_normalization_with_uniqueness(self, sample_entities):
        """Test that normalization works correctly with uniqueness checking"""
        # Create an entity with specific case
        result = nickname_validator.validate('New_User_123', 'user')
        assert result['valid'] is True  # Should be unique
        assert result['normalized'] == 'new_user_123'
        assert result['original'] == 'New_User_123'
    
    def test_validation_without_database(self):
        """Test that validation gracefully handles database unavailability"""
        # Temporarily break the database connection by changing table name
        original_table = os.environ.get('USER_ORG_TABLE_NAME')
        os.environ['USER_ORG_TABLE_NAME'] = 'NonExistentTable'
        
        try:
            result = nickname_validator.validate('test_user', 'user')
            
            # Should still validate other rules, but uniqueness check should be skipped
            # Look for warning about uniqueness check
            warnings = ' '.join(result['warnings'])
            assert 'Could not verify nickname uniqueness' in warnings
            
        finally:
            # Restore original table name
            if original_table:
                os.environ['USER_ORG_TABLE_NAME'] = original_table
    
    def test_reserved_words_still_work(self, sample_entities):
        """Test that reserved word validation still works alongside uniqueness"""
        result = nickname_validator.validate('admin', 'user')
        
        assert result['valid'] is False
        errors = ' '.join(result['errors'])
        assert 'reserved word' in errors
    
    def test_complete_validation_flow(self, sample_entities):
        """Test the complete validation flow with all rules"""
        # Test a good nickname
        result = nickname_validator.validate('good_user_123', 'user')
        assert result['valid'] is True
        assert result['normalized'] == 'good_user_123'
        assert 'Great choice!' in ' '.join(result['hints'])
        
        # Test a bad nickname with multiple issues
        result = nickname_validator.validate('_EXISTING_USER_!', 'user')
        assert result['valid'] is False
        
        errors = ' '.join(result['errors'])
        assert 'cannot start with underscore' in errors
        assert 'cannot end with underscore' in errors
        assert 'Invalid characters' in errors
        assert 'already taken' in errors


def main():
    """Run enhanced validation tests"""
    print("Running enhanced nickname validation tests...")
    
    # Run with pytest
    exit_code = pytest.main([
        __file__, 
        '-v',
        '--tb=short',
        '-x'  # Stop on first failure
    ])
    
    if exit_code == 0:
        print("\n✅ All enhanced validation tests passed!")
        print("🔗 Nickname validation successfully integrated with user-org table")
        print("🛡️  Cross-entity uniqueness validation working correctly")
    else:
        print("\n❌ Some tests failed")
        print("🔧 Please check the integration between validator and user-org table")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())