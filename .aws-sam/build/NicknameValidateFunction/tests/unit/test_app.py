"""
Unit tests for nickname validation Lambda function
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the parent directory to sys.path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Mock the shared imports before importing app
with patch.dict('sys.modules', {
    'shared.utils': MagicMock(),
    'shared.validators.nickname': MagicMock()
}):
    from app import lambda_handler


class TestNicknameValidationLambdaHandler:
    """Test cases for nickname validation Lambda handler"""
    
    def test_lambda_handler_missing_nickname(self, lambda_context, api_gateway_event):
        """Test handler with missing nickname"""
        api_gateway_event['body'] = json.dumps({
            'entity_type': 'user'
            # Missing nickname
        })
        
        response = lambda_handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Nickname is required' in body['error']
    
    def test_lambda_handler_invalid_entity_type(self, lambda_context, api_gateway_event):
        """Test handler with invalid entity type"""
        api_gateway_event['body'] = json.dumps({
            'nickname': 'test_user',
            'entity_type': 'invalid'
        })
        
        response = lambda_handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid entity_type' in body['error']
    
    def test_lambda_handler_get_rules_request(self, lambda_context, api_gateway_event):
        """Test handler for getting validation rules"""
        api_gateway_event['body'] = json.dumps({
            'get_rules': True,
            'entity_type': 'user'
        })
        
        with patch('app.nickname_validator.get_validation_rules') as mock_rules:
            mock_rules.return_value = {
                'length': {'min': 3, 'max': 30},
                'characters': {'allowed': 'a-z, 0-9, _'}
            }
            
            response = lambda_handler(api_gateway_event, lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'rules' in body
            mock_rules.assert_called_once_with('user')
    
    def test_lambda_handler_valid_nickname(self, lambda_context, valid_nickname_event):
        """Test handler with valid nickname"""
        mock_validation_result = {
            'valid': True,
            'original': 'test_user',
            'normalized': 'test_user',
            'entity_type': 'user',
            'errors': [],
            'warnings': [],
            'hints': ['Great choice! This nickname follows all the rules.']
        }
        
        with patch('app.nickname_validator.validate') as mock_validate:
            mock_validate.return_value = mock_validation_result
            
            response = lambda_handler(valid_nickname_event, lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['valid'] is True
            assert body['normalized'] == 'test_user'
            assert body['validation_passed'] is True
            mock_validate.assert_called_once_with('test_user', 'user')
    
    def test_lambda_handler_invalid_nickname(self, lambda_context, api_gateway_event):
        """Test handler with invalid nickname"""
        api_gateway_event['body'] = json.dumps({
            'nickname': 'admin',
            'entity_type': 'user'
        })
        
        mock_validation_result = {
            'valid': False,
            'original': 'admin',
            'normalized': 'admin',
            'entity_type': 'user',
            'errors': ['admin is a reserved word and cannot be used'],
            'warnings': [],
            'hints': ['Try adding numbers or personalizing it, like john_admin or admin123']
        }
        
        with patch('app.nickname_validator.validate') as mock_validate:
            mock_validate.return_value = mock_validation_result
            
            response = lambda_handler(api_gateway_event, lambda_context)
            
            assert response['statusCode'] == 200  # Still 200, but valid=False
            body = json.loads(response['body'])
            assert body['valid'] is False
            assert body['errors'] == ['admin is a reserved word and cannot be used']
            assert body['validation_failed'] is True
            assert 'Try adding numbers' in body['hints'][0]
    
    def test_lambda_handler_nickname_with_warnings(self, lambda_context, api_gateway_event):
        """Test handler with nickname that has warnings"""
        api_gateway_event['body'] = json.dumps({
            'nickname': 'User123',
            'entity_type': 'user'
        })
        
        mock_validation_result = {
            'valid': True,
            'original': 'User123',
            'normalized': 'user123',
            'entity_type': 'user',
            'errors': [],
            'warnings': ['Nickname will be stored as lowercase for uniqueness'],
            'hints': ['Your nickname will appear as User123 but be unique as user123']
        }
        
        with patch('app.nickname_validator.validate') as mock_validate:
            mock_validate.return_value = mock_validation_result
            
            response = lambda_handler(api_gateway_event, lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['valid'] is True
            assert body['warnings'] == ['Nickname will be stored as lowercase for uniqueness']
            assert body['normalized'] == 'user123'
            assert body['original'] == 'User123'
    
    def test_lambda_handler_query_parameters(self, lambda_context, api_gateway_event):
        """Test handler with query parameters instead of body"""
        api_gateway_event['body'] = None
        api_gateway_event['queryStringParameters'] = {
            'nickname': 'test_user',
            'entity_type': 'org'
        }
        
        mock_validation_result = {
            'valid': True,
            'original': 'test_user',
            'normalized': 'test_user',
            'entity_type': 'org',
            'errors': [],
            'warnings': [],
            'hints': ['Great choice! This nickname follows all the rules.']
        }
        
        with patch('app.nickname_validator.validate') as mock_validate:
            mock_validate.return_value = mock_validation_result
            
            response = lambda_handler(api_gateway_event, lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['valid'] is True
            assert body['entity_type'] == 'org'
            mock_validate.assert_called_once_with('test_user', 'org')
    
    def test_lambda_handler_exception_handling(self, lambda_context, valid_nickname_event):
        """Test exception handling in Lambda handler"""
        with patch('app.nickname_validator.validate', side_effect=Exception('Test error')):
            response = lambda_handler(valid_nickname_event, lambda_context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['error'] == 'Internal server error'


if __name__ == '__main__':
    pytest.main([__file__])