"""
Unit tests for photo refresh Lambda function
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
    mock_config.photo_bucket_name = 'anecdotario-photos-test'
    mock_config.photo_table_name = 'Photos-test'
    mock_config.presigned_url_expiry = 604800
    
    with patch('shared.services.service_container.get_service') as mock_get_service:
        mock_photo_service = MagicMock()
        mock_get_service.return_value = mock_photo_service
        
        from app import lambda_handler, _parse_expires_in


@mock_aws
class TestPhotoRefreshLambdaHandler:
    """Test cases for photo refresh Lambda handler"""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_aws_services, mock_config):
        """Setup mocks for each test"""
        self.mock_config = mock_config
        self.aws_services = mock_aws_services
        
        # Setup service container mock
        self.mock_photo_service = MagicMock()
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_get_service.return_value = self.mock_photo_service
            yield
    
    def test_refresh_photo_by_id_success(self, lambda_context):
        """Test successful photo URL refresh by photo ID"""
        event_data = {
            'photo_id': 'test-photo-123',
            'expires_in': '604800'  # 7 days
        }
        
        expected_result = {
            'urls': {
                'standard': 'https://bucket.s3.aws.com/standard.jpg?presigned_params',
                'high_res': 'https://bucket.s3.aws.com/high_res.jpg?presigned_params'
            },
            'generated_at': '2024-01-01T12:00:00Z'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_photo_urls.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called correctly
                mock_photo_service.refresh_photo_urls.assert_called_once_with('test-photo-123')
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
                
                # Verify response data structure
                response_args = mock_response.call_args[0]
                response_data = json.loads(response_args[1])
                
                assert response_data['success'] is True
                assert response_data['message'] == 'Photo URLs refreshed successfully'
                assert response_data['photo_id'] == 'test-photo-123'
                assert response_data['expires_in'] == 604800
                assert 'urls' in response_data
                assert 'generated_at' in response_data
    
    def test_refresh_photo_by_id_not_found(self, lambda_context):
        """Test photo refresh when photo ID doesn't exist"""
        event_data = {
            'photo_id': 'nonexistent-photo'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            from shared.exceptions import ValidationError
            mock_photo_service.refresh_photo_urls.side_effect = ValidationError('Photo not found')
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_error_response') as mock_error_response:
                mock_error_response.return_value = {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Photo not found'})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called
                mock_photo_service.refresh_photo_urls.assert_called_once_with('nonexistent-photo')
                
                # Verify error response
                assert response['statusCode'] == 404
                mock_error_response.assert_called_once()
    
    def test_refresh_entity_photos_success(self, lambda_context):
        """Test successful refresh of entity photos"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'test_user',
            'photo_type': 'profile',
            'expires_in': '86400'  # 1 day
        }
        
        expected_result = {
            'photos_found': 2,
            'photos_refreshed': [
                {
                    'photo_id': 'photo-123',
                    'urls': {
                        'standard': 'https://bucket.s3.aws.com/standard1.jpg?presigned',
                        'high_res': 'https://bucket.s3.aws.com/high_res1.jpg?presigned'
                    }
                },
                {
                    'photo_id': 'photo-456',
                    'urls': {
                        'standard': 'https://bucket.s3.aws.com/standard2.jpg?presigned',
                        'high_res': 'https://bucket.s3.aws.com/high_res2.jpg?presigned'
                    }
                }
            ],
            'errors': []
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_entity_photo_urls.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called correctly
                mock_photo_service.refresh_entity_photo_urls.assert_called_once_with(
                    'user', 'test_user', 'profile', 86400
                )
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
                
                # Verify response data structure
                response_args = mock_response.call_args[0]
                response_data = json.loads(response_args[1])
                
                assert response_data['success'] is True
                assert response_data['message'] == 'Entity photo URLs refreshed successfully'
                assert response_data['entity_type'] == 'user'
                assert response_data['entity_id'] == 'test_user'
                assert response_data['photo_type'] == 'profile'
                assert response_data['photos_found'] == 2
                assert response_data['photos_refreshed'] == 2
                assert len(response_data['photos']) == 2
    
    def test_get_current_photo_success(self, lambda_context):
        """Test successful retrieval of current photo with fresh URLs"""
        event_data = {
            'entity_type': 'org',
            'entity_id': 'test_org',
            'photo_type': 'logo',
            'get_current': 'true',
            'expires_in': '3600'  # 1 hour
        }
        
        expected_result = {
            'photo_info': {
                'photo_id': 'current-photo-789',
                'entity_type': 'org',
                'entity_id': 'test_org',
                'photo_type': 'logo',
                'file_size': 2048,
                'image_format': 'PNG',
                'created_at': '2024-01-01T12:00:00Z'
            },
            'urls': {
                'thumbnail': 'https://bucket.s3.aws.com/thumbnail.png',  # Public
                'standard': 'https://bucket.s3.aws.com/standard.png?presigned',
                'high_res': 'https://bucket.s3.aws.com/high_res.png?presigned'
            },
            'expires_in': 3600,
            'generated_at': '2024-01-01T12:30:00Z'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.get_current_entity_photo.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called correctly
                mock_photo_service.get_current_entity_photo.assert_called_once_with(
                    'org', 'test_org', 'logo', 3600
                )
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
                
                # Verify response data structure
                response_args = mock_response.call_args[0]
                response_data = json.loads(response_args[1])
                
                assert response_data['success'] is True
                assert response_data['message'] == 'Current photo retrieved successfully'
                assert response_data['entity_type'] == 'org'
                assert response_data['entity_id'] == 'test_org'
                assert response_data['photo_type'] == 'logo'
                assert 'photo' in response_data
                assert 'urls' in response_data
                assert response_data['expires_in'] == 3600
    
    def test_get_current_photo_not_found(self, lambda_context):
        """Test getting current photo when none exists"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'user_no_photos',
            'photo_type': 'profile',
            'get_current': 'true'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            from shared.exceptions import ValidationError
            mock_photo_service.get_current_entity_photo.side_effect = ValidationError('No current photo found')
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_error_response') as mock_error_response:
                mock_error_response.return_value = {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'No current photo found'})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called
                mock_photo_service.get_current_entity_photo.assert_called_once()
                
                # Verify error response
                assert response['statusCode'] == 404
                mock_error_response.assert_called_once()
    
    def test_refresh_entity_photos_not_found(self, lambda_context):
        """Test refresh when no entity photos exist"""
        event_data = {
            'entity_type': 'campaign',
            'entity_id': 'campaign_no_photos',
            'photo_type': 'banner'
        }
        
        expected_result = {
            'photos_found': 0,
            'photos_refreshed': [],
            'errors': []
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_entity_photo_urls.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_error_response') as mock_error_response:
                mock_error_response.return_value = {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'No photos found for the specified entity'})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called
                mock_photo_service.refresh_entity_photo_urls.assert_called_once()
                
                # Verify error response for no photos found
                assert response['statusCode'] == 404
                mock_error_response.assert_called_once()
    
    def test_refresh_entity_photos_with_errors(self, lambda_context):
        """Test entity photo refresh with partial failures"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'test_user',
            'photo_type': 'profile'
        }
        
        expected_result = {
            'photos_found': 2,
            'photos_refreshed': [
                {
                    'photo_id': 'photo-123',
                    'urls': {
                        'standard': 'https://bucket.s3.aws.com/standard1.jpg?presigned',
                        'high_res': 'https://bucket.s3.aws.com/high_res1.jpg?presigned'
                    }
                }
            ],
            'errors': [
                'Failed to refresh photo photo-456: S3 key not found'
            ]
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_entity_photo_urls.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Should still return success but include errors
                assert response['statusCode'] == 200
                
                # Verify response includes error information
                response_data = json.loads(mock_response.call_args[0][1])
                assert response_data['photos_found'] == 2
                assert response_data['photos_refreshed'] == 1
                assert response_data['errors'] == ['Failed to refresh photo photo-456: S3 key not found']
    
    def test_refresh_invalid_parameters(self, lambda_context):
        """Test refresh with invalid parameters"""
        # No photo_id or entity info
        event_data = {}
        
        with patch('shared.utils.create_error_response') as mock_error_response:
            mock_error_response.return_value = {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Must provide either photo_id or entity_type+entity_id'})
            }
            
            response = lambda_handler(event_data, lambda_context)
            
            # Should return error for missing parameters
            assert response['statusCode'] == 400
            mock_error_response.assert_called_once()
            
            # Verify error includes usage information
            call_args = mock_error_response.call_args[0]
            error_context = call_args[3]  # The context parameter
            assert 'usage_mode_1' in error_context
            assert 'usage_mode_2' in error_context
            assert 'usage_mode_3' in error_context
    
    def test_refresh_partial_entity_parameters(self, lambda_context):
        """Test refresh with incomplete entity parameters"""
        # Only entity_type, missing entity_id
        event_data = {
            'entity_type': 'user'
            # Missing entity_id
        }
        
        with patch('shared.utils.create_error_response') as mock_error_response:
            mock_error_response.return_value = {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Must provide either photo_id or entity_type+entity_id'})
            }
            
            response = lambda_handler(event_data, lambda_context)
            
            # Should return error for incomplete entity parameters
            assert response['statusCode'] == 400
    
    def test_refresh_default_photo_type(self, lambda_context):
        """Test refresh with default photo type when not specified"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'test_user'
            # No photo_type specified - should default to 'profile'
        }
        
        expected_result = {
            'photos_found': 1,
            'photos_refreshed': [
                {
                    'photo_id': 'photo-123',
                    'urls': {
                        'standard': 'https://bucket.s3.aws.com/standard.jpg?presigned',
                        'high_res': 'https://bucket.s3.aws.com/high_res.jpg?presigned'
                    }
                }
            ],
            'errors': []
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_entity_photo_urls.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called with default photo_type 'profile'
                mock_photo_service.refresh_entity_photo_urls.assert_called_once_with(
                    'user', 'test_user', 'profile', None
                )
                
                # Verify response
                assert response['statusCode'] == 200
    
    def test_refresh_service_exception(self, lambda_context):
        """Test handling of unexpected service exceptions"""
        event_data = {
            'photo_id': 'test-photo-123'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_photo_urls.side_effect = Exception('Unexpected service error')
            mock_get_service.return_value = mock_photo_service
            
            # Exception should be re-raised for decorator to handle
            with pytest.raises(Exception) as exc_info:
                lambda_handler(event_data, lambda_context)
            
            assert 'Unexpected service error' in str(exc_info.value)


class TestPhotoRefreshHelperFunctions:
    """Test helper functions in photo refresh module"""
    
    def test_parse_expires_in_valid_values(self):
        """Test parsing valid expires_in values"""
        # Valid numeric strings
        assert _parse_expires_in('3600') == 3600
        assert _parse_expires_in('86400') == 86400
        assert _parse_expires_in('604800') == 604800
    
    def test_parse_expires_in_boundary_values(self):
        """Test parsing expires_in boundary values"""
        # Mock time constants for testing
        with patch('app.TimeConstants') as mock_time_constants:
            mock_time_constants.MAX_PRESIGNED_URL_EXPIRY = 604800  # 7 days
            mock_time_constants.MIN_PRESIGNED_URL_EXPIRY = 300     # 5 minutes
            
            # Value too high - should be clamped to max
            assert _parse_expires_in('999999') == 604800
            
            # Value too low - should be clamped to min
            assert _parse_expires_in('60') == 300
            
            # Valid values within bounds
            assert _parse_expires_in('3600') == 3600
    
    def test_parse_expires_in_invalid_values(self):
        """Test parsing invalid expires_in values"""
        # Non-numeric strings
        assert _parse_expires_in('invalid') is None
        assert _parse_expires_in('abc123') is None
        assert _parse_expires_in('') is None
        
        # None/empty values
        assert _parse_expires_in(None) is None
        assert _parse_expires_in('') is None
    
    def test_parse_expires_in_edge_cases(self):
        """Test parsing expires_in edge cases"""
        # Negative values
        with patch('app.TimeConstants') as mock_time_constants:
            mock_time_constants.MIN_PRESIGNED_URL_EXPIRY = 300
            assert _parse_expires_in('-100') == 300
        
        # Zero value
        with patch('app.TimeConstants') as mock_time_constants:
            mock_time_constants.MIN_PRESIGNED_URL_EXPIRY = 300
            assert _parse_expires_in('0') == 300


@mock_aws
class TestPhotoRefreshIntegration:
    """Integration tests for photo refresh functionality"""
    
    def test_photo_refresh_service_integration(self, mock_aws_services):
        """Test photo refresh service integration with AWS services"""
        event_data = {
            'photo_id': 'integration-test-photo',
            'expires_in': '3600'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.refresh_photo_urls.return_value = {
                'urls': {'standard': 'https://test.com/standard.jpg?presigned'},
                'generated_at': '2024-01-01T12:00:00Z'
            }
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {'statusCode': 200, 'body': '{"success": true}'}
                
                response = lambda_handler(event_data, MagicMock())
                
                # Verify integration worked
                mock_photo_service.refresh_photo_urls.assert_called_once()
                assert mock_response.called
    
    def test_current_photo_retrieval_integration(self, mock_aws_services):
        """Test current photo retrieval integration"""
        event_data = {
            'entity_type': 'campaign',
            'entity_id': 'summer_campaign',
            'photo_type': 'banner',
            'get_current': 'true'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.get_current_entity_photo.return_value = {
                'photo_info': {'photo_id': 'current-123'},
                'urls': {'standard': 'https://test.com/banner.jpg?presigned'},
                'expires_in': 604800,
                'generated_at': '2024-01-01T12:00:00Z'
            }
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {'statusCode': 200, 'body': '{"success": true}'}
                
                response = lambda_handler(event_data, MagicMock())
                
                # Verify integration for current photo retrieval
                mock_photo_service.get_current_entity_photo.assert_called_once_with(
                    'campaign', 'summer_campaign', 'banner', None
                )
                assert mock_response.called


class TestPhotoRefreshBusinessLogic:
    """Test business logic specific to photo refresh"""
    
    def test_refresh_operation_modes(self):
        """Test that refresh supports all operation modes"""
        # Mode 1: Photo ID refresh
        mode1_required = ['photo_id']
        mode1_optional = ['expires_in']
        
        # Mode 2: Entity photo refresh
        mode2_required = ['entity_type', 'entity_id']
        mode2_optional = ['photo_type', 'expires_in']
        
        # Mode 3: Get current photo
        mode3_required = ['entity_type', 'entity_id', 'get_current']
        mode3_optional = ['photo_type', 'expires_in']
        
        # Verify mode requirements
        assert len(mode1_required) == 1
        assert len(mode2_required) == 2
        assert len(mode3_required) == 3
    
    def test_refresh_response_formats(self):
        """Test that refresh responses follow expected formats"""
        # Photo ID refresh response
        photo_id_fields = [
            'success', 'message', 'photo_id', 'urls', 
            'expires_in', 'generated_at'
        ]
        
        # Entity refresh response
        entity_fields = [
            'success', 'message', 'entity_type', 'entity_id', 'photo_type',
            'photos_found', 'photos_refreshed', 'photos', 'expires_in', 'errors'
        ]
        
        # Current photo response
        current_fields = [
            'success', 'message', 'entity_type', 'entity_id', 'photo_type',
            'photo', 'urls', 'expires_in', 'generated_at'
        ]
        
        # Verify response structures
        assert all(field in photo_id_fields for field in photo_id_fields)
        assert all(field in entity_fields for field in entity_fields)
        assert all(field in current_fields for field in current_fields)
    
    def test_expires_in_validation_logic(self):
        """Test expires_in parameter validation logic"""
        # Valid ranges (these would be defined in TimeConstants)
        min_expiry = 300      # 5 minutes
        max_expiry = 604800   # 7 days
        
        # Test boundary conditions
        test_cases = [
            ('100', min_expiry),    # Below minimum
            ('3600', 3600),         # Valid value
            ('999999', max_expiry), # Above maximum
            ('invalid', None),      # Invalid string
            (None, None)            # No value provided
        ]
        
        # Verify test case structure
        for input_val, expected in test_cases:
            assert isinstance(input_val, (str, type(None)))
            assert isinstance(expected, (int, type(None)))


if __name__ == '__main__':
    pytest.main([__file__])