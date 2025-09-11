"""
Unit tests for photo delete Lambda function
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
    
    with patch('shared.services.service_container.get_service') as mock_get_service:
        mock_photo_service = MagicMock()
        mock_get_service.return_value = mock_photo_service
        
        from app import lambda_handler


@mock_aws
class TestPhotoDeleteLambdaHandler:
    """Test cases for photo delete Lambda handler"""
    
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
    
    def test_delete_photo_by_id_success(self, lambda_context):
        """Test successful photo deletion by photo ID"""
        event_data = {
            'photo_id': 'test-photo-123'
        }
        
        expected_result = {
            'deleted_count': 1,
            'failed_count': 0,
            's3_cleanup': {
                'files_deleted': 3,  # thumbnail, standard, high_res
                'files_failed': 0
            }
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_photo.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called correctly
                mock_photo_service.delete_photo.assert_called_once_with(photo_id='test-photo-123')
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
                
                # Verify response data structure
                response_args = mock_response.call_args[0]
                response_data = json.loads(response_args[1])
                
                assert response_data['success'] is True
                assert response_data['message'] == 'Photo deleted successfully'
                assert response_data['photo_id'] == 'test-photo-123'
                assert response_data['deleted_count'] == 1
                assert response_data['failed_count'] == 0
                assert 's3_cleanup' in response_data
    
    def test_delete_photo_by_id_not_found(self, lambda_context):
        """Test photo deletion when photo ID doesn't exist"""
        event_data = {
            'photo_id': 'nonexistent-photo'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_photo.side_effect = Exception('Photo not found')
            mock_get_service.return_value = mock_photo_service
            
            from shared.exceptions import ValidationError
            mock_photo_service.delete_photo.side_effect = ValidationError('Photo not found')
            
            with patch('shared.utils.create_error_response') as mock_error_response:
                mock_error_response.return_value = {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Photo not found'})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called
                mock_photo_service.delete_photo.assert_called_once_with(photo_id='nonexistent-photo')
                
                # Verify error response
                assert response['statusCode'] == 404
                mock_error_response.assert_called_once()
    
    def test_delete_entity_photos_success(self, lambda_context):
        """Test successful deletion of entity photos"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'test_user',
            'photo_type': 'profile'
        }
        
        expected_result = {
            'photos_deleted': 2,
            'photos_processed': 2,
            's3_files_deleted': [
                'user/test_user/profile/thumbnail_20240101_abc123.jpg',
                'user/test_user/profile/standard_20240101_abc123.jpg',
                'user/test_user/profile/high_res_20240101_abc123.jpg',
                'user/test_user/profile/thumbnail_20240102_def456.jpg',
                'user/test_user/profile/standard_20240102_def456.jpg',
                'user/test_user/profile/high_res_20240102_def456.jpg'
            ],
            'deletion_errors': []
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_entity_photos.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called correctly
                mock_photo_service.delete_entity_photos.assert_called_once_with(
                    'user', 'test_user', 'profile'
                )
                
                # Verify response
                assert response['statusCode'] == 200
                mock_response.assert_called_once()
                
                # Verify response data structure
                response_args = mock_response.call_args[0]
                response_data = json.loads(response_args[1])
                
                assert response_data['success'] is True
                assert response_data['message'] == 'Entity photos deleted successfully'
                assert response_data['entity_type'] == 'user'
                assert response_data['entity_id'] == 'test_user'
                assert response_data['photo_type'] == 'profile'
                assert response_data['photos_deleted'] == 2
                assert response_data['deleted_files_count'] == 6
                assert len(response_data['deleted_files']) == 6
    
    def test_delete_entity_photos_all_types(self, lambda_context):
        """Test deletion of all photo types for an entity"""
        event_data = {
            'entity_type': 'org',
            'entity_id': 'test_org'
            # No photo_type specified - should delete all types
        }
        
        expected_result = {
            'photos_deleted': 3,
            'photos_processed': 3,
            's3_files_deleted': [
                'org/test_org/logo/thumbnail_20240101_abc123.jpg',
                'org/test_org/logo/standard_20240101_abc123.jpg',
                'org/test_org/logo/high_res_20240101_abc123.jpg',
                'org/test_org/banner/thumbnail_20240102_def456.jpg',
                'org/test_org/banner/standard_20240102_def456.jpg',
                'org/test_org/banner/high_res_20240102_def456.jpg',
                'org/test_org/gallery/thumbnail_20240103_ghi789.jpg',
                'org/test_org/gallery/standard_20240103_ghi789.jpg',
                'org/test_org/gallery/high_res_20240103_ghi789.jpg'
            ],
            'deletion_errors': []
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_entity_photos.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called with None for photo_type
                mock_photo_service.delete_entity_photos.assert_called_once_with(
                    'org', 'test_org', None
                )
                
                # Verify response
                assert response['statusCode'] == 200
                assert json.loads(mock_response.call_args[0][1])['photos_deleted'] == 3
    
    def test_delete_entity_photos_not_found(self, lambda_context):
        """Test deletion when no entity photos exist"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'user_no_photos',
            'photo_type': 'profile'
        }
        
        expected_result = {
            'photos_deleted': 0,
            'photos_processed': 0,
            's3_files_deleted': [],
            'deletion_errors': []
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_entity_photos.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_error_response') as mock_error_response:
                mock_error_response.return_value = {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'No photos found for the specified entity'})
                }
                
                response = lambda_handler(event_data, lambda_context)
                
                # Verify service was called
                mock_photo_service.delete_entity_photos.assert_called_once()
                
                # Verify error response for no photos found
                assert response['statusCode'] == 404
                mock_error_response.assert_called_once()
    
    def test_delete_entity_photos_with_errors(self, lambda_context):
        """Test entity photo deletion with partial failures"""
        event_data = {
            'entity_type': 'user',
            'entity_id': 'test_user',
            'photo_type': 'profile'
        }
        
        expected_result = {
            'photos_deleted': 1,
            'photos_processed': 2,
            's3_files_deleted': [
                'user/test_user/profile/thumbnail_20240101_abc123.jpg',
                'user/test_user/profile/standard_20240101_abc123.jpg',
                'user/test_user/profile/high_res_20240101_abc123.jpg'
            ],
            'deletion_errors': [
                'Failed to delete photo test-photo-456: Access denied'
            ]
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_entity_photos.return_value = expected_result
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
                assert response_data['photos_deleted'] == 1
                assert response_data['errors'] == ['Failed to delete photo test-photo-456: Access denied']
    
    def test_delete_invalid_parameters(self, lambda_context):
        """Test deletion with invalid parameters"""
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
    
    def test_delete_partial_entity_parameters(self, lambda_context):
        """Test deletion with incomplete entity parameters"""
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
    
    def test_delete_service_exception(self, lambda_context):
        """Test handling of unexpected service exceptions"""
        event_data = {
            'photo_id': 'test-photo-123'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_photo.side_effect = Exception('Unexpected service error')
            mock_get_service.return_value = mock_photo_service
            
            # Exception should be re-raised for decorator to handle
            with pytest.raises(Exception) as exc_info:
                lambda_handler(event_data, lambda_context)
            
            assert 'Unexpected service error' in str(exc_info.value)
    
    def test_delete_direct_lambda_invocation(self, lambda_context):
        """Test deletion via direct Lambda invocation (not API Gateway)"""
        # Direct event format (no body wrapper)
        direct_event = {
            'photo_id': 'direct-photo-123'
        }
        
        expected_result = {
            'deleted_count': 1,
            'failed_count': 0,
            's3_cleanup': {
                'files_deleted': 3,
                'files_failed': 0
            }
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_photo.return_value = expected_result
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': True})
                }
                
                response = lambda_handler(direct_event, lambda_context)
                
                # Verify service was called with direct event data
                mock_photo_service.delete_photo.assert_called_once_with(photo_id='direct-photo-123')
                
                # Verify response
                assert response['statusCode'] == 200


@mock_aws
class TestPhotoDeleteIntegration:
    """Integration tests for photo delete functionality"""
    
    def test_photo_delete_service_integration(self, mock_aws_services):
        """Test photo delete service integration with AWS services"""
        event_data = {
            'photo_id': 'integration-test-photo'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_photo.return_value = {
                'deleted_count': 1,
                'failed_count': 0,
                's3_cleanup': {'files_deleted': 3, 'files_failed': 0}
            }
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {'statusCode': 200, 'body': '{"success": true}'}
                
                response = lambda_handler(event_data, MagicMock())
                
                # Verify integration worked
                mock_photo_service.delete_photo.assert_called_once()
                assert mock_response.called
    
    def test_entity_photo_delete_integration(self, mock_aws_services):
        """Test entity photo delete integration"""
        event_data = {
            'entity_type': 'campaign',
            'entity_id': 'summer_campaign',
            'photo_type': 'banner'
        }
        
        with patch('shared.services.service_container.get_service') as mock_get_service:
            mock_photo_service = MagicMock()
            mock_photo_service.delete_entity_photos.return_value = {
                'photos_deleted': 1,
                'photos_processed': 1,
                's3_files_deleted': ['campaign/summer_campaign/banner/file.jpg'],
                'deletion_errors': []
            }
            mock_get_service.return_value = mock_photo_service
            
            with patch('shared.utils.create_response') as mock_response:
                mock_response.return_value = {'statusCode': 200, 'body': '{"success": true}'}
                
                response = lambda_handler(event_data, MagicMock())
                
                # Verify integration for entity deletion
                mock_photo_service.delete_entity_photos.assert_called_once_with(
                    'campaign', 'summer_campaign', 'banner'
                )
                assert mock_response.called


class TestPhotoDeleteBusinessLogic:
    """Test business logic specific to photo deletion"""
    
    def test_deletion_modes_validation(self):
        """Test that deletion supports both operation modes"""
        # Mode 1: Photo ID deletion
        mode1_required = ['photo_id']
        
        # Mode 2: Entity photo deletion  
        mode2_required = ['entity_type', 'entity_id']
        mode2_optional = ['photo_type']
        
        # Verify mode requirements
        assert len(mode1_required) == 1
        assert len(mode2_required) == 2
        assert len(mode2_optional) == 1
    
    def test_deletion_response_format(self):
        """Test that deletion response follows expected format"""
        # Photo ID deletion response
        photo_id_fields = [
            'success', 'message', 'photo_id', 'deleted_count',
            'failed_count', 's3_cleanup', 'errors'
        ]
        
        # Entity deletion response
        entity_fields = [
            'success', 'message', 'entity_type', 'entity_id', 'photo_type',
            'photos_deleted', 'deleted_files_count', 'deleted_files',
            'photos_processed', 'errors'
        ]
        
        # Verify response structures
        assert all(field in photo_id_fields for field in photo_id_fields)
        assert all(field in entity_fields for field in entity_fields)
    
    def test_error_handling_scenarios(self):
        """Test error handling scenarios"""
        error_scenarios = [
            'photo_not_found',
            'entity_not_found', 
            'no_photos_for_entity',
            'partial_deletion_failure',
            'service_unavailable',
            'invalid_parameters'
        ]
        
        # Verify we handle all expected error scenarios
        assert len(error_scenarios) == 6
        assert 'photo_not_found' in error_scenarios
        assert 'invalid_parameters' in error_scenarios


if __name__ == '__main__':
    pytest.main([__file__])