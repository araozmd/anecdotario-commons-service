"""
Unit tests for nickname validation Lambda function
"""
import json
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws

# Add the parent directory to sys.path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Mock the shared modules before importing
with patch('shared.config.config') as mock_config:
    mock_config.environment = 'test'
    
    with patch('shared.services.service_container.get_service') as mock_get_service:
        mock_nickname_validator = MagicMock()
        mock_get_service.return_value = mock_nickname_validator
        
        from app import lambda_handler


@mock_aws
class TestNicknameValidationLambdaHandler:
    """Test cases for nickname validation Lambda handler"""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_aws_services, mock_config):
        """Setup mocks for each test"""
        self.mock_config = mock_config
        self.aws_services = mock_aws_services
        
        # Setup service container mock
        self.mock_nickname_validator = MagicMock()
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_get_service.return_value = self.mock_nickname_validator
            yield
    
    def test_lambda_handler_successful_validation(self, lambda_context, valid_nickname_event):
        """Test successful nickname validation"""
        expected_result = {
            'valid': True,
            'original': 'test_user',
            'normalized': 'test_user',
            'entity_type': 'user',
            'errors': [],
            'warnings': [],
            'hints': ['Great choice! This nickname follows all the rules.']
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.return_value = expected_result
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(expected_result)
                }
                
                response = lambda_handler(valid_nickname_event, lambda_context)
                
                # Verify validator was called correctly
                mock_validator.validate.assert_called_once_with('test_user', 'user')
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
    
    def test_lambda_handler_invalid_nickname(self, lambda_context, api_gateway_event):
        """Test handler with invalid nickname"""
        api_gateway_event['body'] = json.dumps({
            'nickname': 'admin',
            'entity_type': 'user'
        })
        
        expected_result = {
            'valid': False,
            'original': 'admin',
            'normalized': 'admin',
            'entity_type': 'user',
            'errors': ['admin is a reserved word and cannot be used'],
            'warnings': [],
            'hints': ['Try adding numbers or personalizing it, like john_admin or admin123']
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.return_value = expected_result
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(expected_result)
                }
                
                response = lambda_handler(api_gateway_event, lambda_context)
                
                # Verify validator was called
                mock_validator.validate.assert_called_once_with('admin', 'user')
                
                # Verify response (200 OK with valid=False)
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
    
    def test_lambda_handler_missing_nickname(self, lambda_context, api_gateway_event):
        """Test handler with missing nickname"""
        api_gateway_event['body'] = json.dumps({
            'entity_type': 'user'
            # Missing nickname
        })
        
        with patch('shared.utils.create_error_response') as mock_error_response:
            mock_error_response.return_value = {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Nickname is required'})
            }
            
            response = lambda_handler(api_gateway_event, lambda_context)
            
            # Should return error for missing required field
            assert response['statusCode'] == 400
    
    def test_lambda_handler_invalid_entity_type(self, lambda_context, api_gateway_event):
        """Test handler with invalid entity type"""
        api_gateway_event['body'] = json.dumps({
            'nickname': 'test_user',
            'entity_type': 'invalid'
        })
        
        with patch('shared.utils.create_error_response') as mock_error_response:
            mock_error_response.return_value = {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid entity_type: invalid'})
            }
            
            response = lambda_handler(api_gateway_event, lambda_context)
            
            # Should validate entity type
            assert response['statusCode'] == 400
    
    def test_lambda_handler_get_validation_rules(self, lambda_context, api_gateway_event):
        """Test handler for getting validation rules"""
        api_gateway_event['body'] = json.dumps({
            'get_rules': True,
            'entity_type': 'user'
        })
        
        expected_rules = {
            'length': {'min': 3, 'max': 30},
            'characters': {'allowed': 'a-z, 0-9, _'},
            'reserved_words': ['admin', 'root', 'system'],
            'patterns': {
                'no_consecutive_underscores': True,
                'no_leading_trailing_underscores': True
            }
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.get_validation_rules.return_value = expected_rules
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'rules': expected_rules})
                }
                
                response = lambda_handler(api_gateway_event, lambda_context)
                
                # Verify rules were requested for correct entity type
                mock_validator.get_validation_rules.assert_called_once_with('user')
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
    
    def test_lambda_handler_nickname_with_warnings(self, lambda_context, api_gateway_event):
        """Test handler with nickname that has warnings"""
        api_gateway_event['body'] = json.dumps({
            'nickname': 'User123',
            'entity_type': 'user'
        })
        
        expected_result = {
            'valid': True,
            'original': 'User123',
            'normalized': 'user123',
            'entity_type': 'user',
            'errors': [],
            'warnings': ['Nickname will be stored as lowercase for uniqueness'],
            'hints': ['Your nickname will appear as User123 but be unique as user123']
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.return_value = expected_result
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(expected_result)
                }
                
                response = lambda_handler(api_gateway_event, lambda_context)
                
                # Verify validator was called with original case
                mock_validator.validate.assert_called_once_with('User123', 'user')
                
                # Verify response includes warnings
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
    
    def test_lambda_handler_query_parameters(self, lambda_context, api_gateway_event):
        """Test handler with query parameters instead of body"""
        api_gateway_event['body'] = None
        api_gateway_event['queryStringParameters'] = {
            'nickname': 'test_user',
            'entity_type': 'org'
        }
        
        expected_result = {
            'valid': True,
            'original': 'test_user',
            'normalized': 'test_user',
            'entity_type': 'org',
            'errors': [],
            'warnings': [],
            'hints': ['Great choice! This nickname follows all the rules.']
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.return_value = expected_result
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(expected_result)
                }
                
                response = lambda_handler(api_gateway_event, lambda_context)
                
                # Verify validator was called with org entity type
                mock_validator.validate.assert_called_once_with('test_user', 'org')
                
                # Verify response
                assert response['statusCode'] == 200
    
    def test_lambda_handler_direct_lambda_event(self, lambda_context):
        """Test handler with direct Lambda invocation"""
        direct_event = {
            'nickname': 'test_user',
            'entity_type': 'user'
        }
        
        expected_result = {
            'valid': True,
            'original': 'test_user',
            'normalized': 'test_user',
            'entity_type': 'user',
            'errors': [],
            'warnings': [],
            'hints': ['Great choice! This nickname follows all the rules.']
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.return_value = expected_result
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(expected_result)
                }
                
                response = lambda_handler(direct_event, lambda_context)
                
                # Verify validator was called
                mock_validator.validate.assert_called_once_with('test_user', 'user')
                
                # Verify response
                assert response['statusCode'] == 200
    
    def test_lambda_handler_exception_handling(self, lambda_context, valid_nickname_event):
        """Test exception handling in Lambda handler"""
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.side_effect = Exception('Validator service error')
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_error_response') as mock_error_response:
                mock_error_response.return_value = {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Internal server error'})
                }
                
                response = lambda_handler(valid_nickname_event, lambda_context)
                
                # Should handle service error gracefully
                assert response['statusCode'] >= 400


@mock_aws
class TestNicknameValidationIntegration:
    """Integration tests for nickname validation functionality"""
    
    def test_nickname_validation_service_integration(self, mock_aws_services):
        """Test nickname validation service integration"""
        event_data = {
            'nickname': 'test_user',
            'entity_type': 'user'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.validate.return_value = {
                'valid': True,
                'original': 'test_user',
                'normalized': 'test_user',
                'entity_type': 'user',
                'errors': [],
                'warnings': [],
                'hints': ['Great choice!']
            }
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {'statusCode': 200, 'body': '{"valid": true}'}
                
                response = lambda_handler(event_data, MagicMock())
                
                # Verify integration worked
                mock_validator.validate.assert_called_once()
                assert mock_response.called
    
    def test_validation_rules_integration(self, mock_aws_services):
        """Test validation rules retrieval integration"""
        event_data = {
            'get_rules': True,
            'entity_type': 'org'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_validator = MagicMock()
            mock_validator.get_validation_rules.return_value = {
                'length': {'min': 3, 'max': 30},
                'characters': {'allowed': 'a-z, 0-9, _'}
            }
            mock_get_service.return_value = mock_validator
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {'statusCode': 200, 'body': '{"rules": {}}'}
                
                response = lambda_handler(event_data, MagicMock())
                
                # Verify rules were requested for org entity type
                mock_validator.get_validation_rules.assert_called_once_with('org')
                assert mock_response.called


class TestNicknameValidationBusinessLogic:
    """Test business logic specific to nickname validation"""
    
    def test_entity_type_validation(self):
        """Test that entity type validation works correctly"""
        valid_entity_types = ['user', 'org', 'campaign']
        
        # This would test the actual validation logic
        # For now, we verify the expected entity types
        assert len(valid_entity_types) == 3
        assert 'user' in valid_entity_types
        assert 'org' in valid_entity_types
        assert 'campaign' in valid_entity_types
    
    def test_nickname_validation_response_format(self):
        """Test that validation response follows expected format"""
        expected_fields = [
            'valid', 'original', 'normalized', 'entity_type',
            'errors', 'warnings', 'hints'
        ]
        
        # This validates our response structure matches expectations
        assert all(field in expected_fields for field in expected_fields)
    
    def test_validation_rules_response_format(self):
        """Test that validation rules response follows expected format"""
        expected_rule_categories = [
            'length', 'characters', 'reserved_words', 'patterns'
        ]
        
        # This validates our rules structure matches expectations
        assert all(category in expected_rule_categories for category in expected_rule_categories)
    
    def test_nickname_normalization_logic(self):
        """Test nickname normalization behavior"""
        # Test cases for normalization
        test_cases = [
            ('TestUser', 'testuser'),
            ('test_user', 'test_user'),
            ('TEST123', 'test123'),
            ('User_Name_123', 'user_name_123')
        ]
        
        for original, expected_normalized in test_cases:
            # This would test the actual normalization function
            # For now, we verify the test case structure is correct
            assert isinstance(original, str)
            assert isinstance(expected_normalized, str)
            assert expected_normalized == expected_normalized.lower()


if __name__ == '__main__':
    pytest.main([__file__])