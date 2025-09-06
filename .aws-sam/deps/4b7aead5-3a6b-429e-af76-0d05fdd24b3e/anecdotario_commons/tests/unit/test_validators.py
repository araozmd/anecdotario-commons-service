"""
Unit tests for shared validators
"""
import pytest
from unittest.mock import Mock
import sys
import os

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class TestNicknameValidator:
    """Test cases for NicknameValidator class"""
    
    @pytest.fixture
    def nickname_validator(self, mock_config):
        """Create a NicknameValidator instance with mocked config"""
        # Mock the config module
        import shared.validators.nickname as nickname_module
        nickname_module.config = mock_config
        
        from shared.validators.nickname import NicknameValidator
        return NicknameValidator()
    
    def test_normalize_nickname(self, nickname_validator):
        """Test nickname normalization"""
        assert nickname_validator.normalize_nickname('JohnDoe') == 'johndoe'
        assert nickname_validator.normalize_nickname(' TestUser ') == 'testuser'
        assert nickname_validator.normalize_nickname('USER_123') == 'user_123'
    
    def test_validate_empty_nickname(self, nickname_validator):
        """Test validation with empty nickname"""
        result = nickname_validator.validate('', 'user')
        
        assert result['valid'] is False
        assert 'Nickname cannot be empty' in result['errors']
        assert 'Please provide a nickname' in result['hints']
    
    def test_validate_too_short_nickname(self, nickname_validator):
        """Test validation with too short nickname"""
        result = nickname_validator.validate('ab', 'user')
        
        assert result['valid'] is False
        assert 'at least 3 characters long' in result['errors'][0]
    
    def test_validate_too_long_nickname(self, nickname_validator):
        """Test validation with too long nickname"""
        long_nickname = 'a' * 31
        result = nickname_validator.validate(long_nickname, 'user')
        
        assert result['valid'] is False
        assert '30 characters or less' in result['errors'][0]
    
    def test_validate_invalid_characters(self, nickname_validator):
        """Test validation with invalid characters"""
        result = nickname_validator.validate('user@name', 'user')
        
        assert result['valid'] is False
        assert 'Invalid characters' in result['errors'][0]
        assert '@' in result['errors'][0]
    
    def test_validate_leading_underscore(self, nickname_validator):
        """Test validation with leading underscore"""
        result = nickname_validator.validate('_user', 'user')
        
        assert result['valid'] is False
        assert 'cannot start with underscore' in result['errors'][0]
    
    def test_validate_trailing_underscore(self, nickname_validator):
        """Test validation with trailing underscore"""
        result = nickname_validator.validate('user_', 'user')
        
        assert result['valid'] is False
        assert 'cannot end with underscore' in result['errors'][0]
    
    def test_validate_consecutive_underscores(self, nickname_validator):
        """Test validation with consecutive underscores"""
        result = nickname_validator.validate('user__name', 'user')
        
        assert result['valid'] is False
        assert 'consecutive underscores' in result['errors'][0]
    
    def test_validate_case_normalization_warning(self, nickname_validator):
        """Test validation with case that needs normalization"""
        result = nickname_validator.validate('JohnDoe', 'user')
        
        assert result['valid'] is True
        assert result['original'] == 'JohnDoe'
        assert result['normalized'] == 'johndoe'
        assert 'stored as lowercase' in result['warnings'][0]
    
    def test_validate_leading_digit(self, nickname_validator):
        """Test validation with leading digit"""
        result = nickname_validator.validate('123user', 'user')
        
        # Should be error by default (allow_leading_digits = False)
        assert result['valid'] is False
        assert 'cannot start with a number' in result['errors'][0]
    
    def test_validate_confusing_characters(self, nickname_validator):
        """Test validation with confusing characters"""
        result = nickname_validator.validate('user0', 'user')
        
        assert result['valid'] is True  # Warning, not error
        assert any('confusing characters' in warning for warning in result['warnings'])
        assert "'0' (could be confused with 'o')" in result['warnings'][0]
    
    def test_validate_reserved_word(self, nickname_validator):
        """Test validation with reserved word"""
        result = nickname_validator.validate('admin', 'user')
        
        assert result['valid'] is False
        assert 'reserved word' in result['errors'][0]
        assert 'admin' in result['errors'][0]
    
    def test_validate_partial_reserved_word(self, nickname_validator):
        """Test validation with partial reserved word"""
        result = nickname_validator.validate('admin_john', 'user')
        
        # Should be valid but with warning
        assert result['valid'] is True
        assert any('reserved word' in warning for warning in result['warnings'])
    
    def test_validate_low_complexity(self, nickname_validator):
        """Test validation with low complexity nickname"""
        result = nickname_validator.validate('aaa', 'user')
        
        assert result['valid'] is True
        assert any('low complexity' in warning for warning in result['warnings'])
    
    def test_validate_all_digits(self, nickname_validator):
        """Test validation with all-digit nickname"""
        result = nickname_validator.validate('123456', 'user')
        
        assert result['valid'] is False  # Leading digit should make it invalid
        assert 'cannot start with a number' in result['errors'][0]
    
    def test_validate_entity_specific_reserved_words(self, nickname_validator):
        """Test validation with entity-specific reserved words"""
        # Test org-specific reserved word
        result = nickname_validator.validate('company', 'org')
        assert result['valid'] is False
        assert 'reserved word' in result['errors'][0]
        
        # Test same word should be valid for user
        result = nickname_validator.validate('company', 'user')
        assert result['valid'] is True
    
    def test_validate_perfect_nickname(self, nickname_validator):
        """Test validation with perfect nickname"""
        result = nickname_validator.validate('john_doe', 'user')
        
        assert result['valid'] is True
        assert result['errors'] == []
        assert result['warnings'] == []
        assert 'Great choice!' in result['hints'][0]
    
    def test_get_validation_rules_user(self, nickname_validator):
        """Test getting validation rules for user entity"""
        rules = nickname_validator.get_validation_rules('user')
        
        assert 'length' in rules
        assert 'characters' in rules
        assert 'reserved' in rules
        assert rules['length']['min'] == 3
        assert rules['length']['max'] == 30
        assert 'a-z, 0-9, _' in rules['characters']['allowed']
    
    def test_get_validation_rules_org(self, nickname_validator):
        """Test getting validation rules for org entity"""
        rules = nickname_validator.get_validation_rules('org')
        
        assert rules['reserved']['entity_type'] == 'org'
        # Should have more reserved words than user
        assert 'company' in str(rules['reserved'])
    
    def test_get_valid_examples(self, nickname_validator):
        """Test getting valid examples for different entity types"""
        user_examples = nickname_validator._get_valid_examples('user')
        org_examples = nickname_validator._get_valid_examples('org')
        campaign_examples = nickname_validator._get_valid_examples('campaign')
        
        assert 'john_doe' in user_examples
        assert 'acme_corp' in org_examples
        assert 'summer_2024' in campaign_examples


if __name__ == '__main__':
    pytest.main([__file__])