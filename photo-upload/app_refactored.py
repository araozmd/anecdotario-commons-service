"""
Photo Upload Lambda Function - REFACTORED VERSION
Entity-agnostic photo upload service demonstrating clean code practices

This is an example of how the Lambda handler should be refactored using:
- Decorators for request validation
- Constants instead of magic numbers  
- Proper error handling with custom exceptions
- Dependency injection for testability
- Separation of concerns
"""
import json
import os
import sys

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from decorators import standard_lambda_handler
from constants import ImageConstants, HTTPConstants, ErrorMessages
from exceptions import ValidationError, ImageProcessingError, StorageError
from services.photo_service import PhotoService
from utils import create_response


# Initialize photo service (dependency injection in practice would pass these)
photo_service = PhotoService()


@standard_lambda_handler(
    required_fields=['image', 'entity_type', 'entity_id', 'photo_type'],
    entity_validation=True,
    photo_type_validation=True,
    support_query_params=False,
    log_requests=True
)
def lambda_handler(event, context):
    """
    Clean, focused Lambda handler using decorators
    All validation is handled by decorators, business logic is separated
    """
    # Extract validated parameters (decorators guarantee these exist and are valid)
    params = event['parsed_body']
    
    image_data = params['image']
    entity_type = params['entity_type']
    entity_id = params['entity_id']
    photo_type = params['photo_type']
    uploaded_by = params.get('uploaded_by')
    
    # Business logic - delegate to service layer
    result = photo_service.upload_photo(
        image_data=image_data,
        entity_type=entity_type,
        entity_id=entity_id,
        photo_type=photo_type,
        uploaded_by=uploaded_by
    )
    
    # Return success response
    return create_response(
        HTTPConstants.OK,
        json.dumps({
            'success': True,
            'message': 'Photo uploaded successfully',
            'photo_id': result['photo_id'],
            'urls': result['urls'],
            'metadata': result['metadata'],
            'cleanup_result': result.get('cleanup_result', {})
        }),
        event
    )


# Example of how individual functions would be refactored
class PhotoUploadHandler:
    """
    Alternative class-based approach for better organization
    """
    
    def __init__(self, photo_service: PhotoService = None):
        self.photo_service = photo_service or PhotoService()
    
    @standard_lambda_handler(
        required_fields=['image', 'entity_type', 'entity_id', 'photo_type'],
        entity_validation=True,
        photo_type_validation=True
    )
    def handle_upload(self, event, context):
        """Class-based handler example"""
        params = event['parsed_body']
        
        result = self.photo_service.upload_photo(
            image_data=params['image'],
            entity_type=params['entity_type'],
            entity_id=params['entity_id'],
            photo_type=params['photo_type'],
            uploaded_by=params.get('uploaded_by')
        )
        
        return create_response(
            HTTPConstants.OK,
            json.dumps({
                'success': True,
                'photo_id': result['photo_id'],
                'urls': result['urls']
            }),
            event
        )


# For backwards compatibility, you can still use the function-based approach
handler_instance = PhotoUploadHandler()
lambda_handler_class_based = handler_instance.handle_upload


if __name__ == '__main__':
    # Example event for testing
    test_event = {
        'body': json.dumps({
            'image': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...',
            'entity_type': 'user',
            'entity_id': 'test_user',
            'photo_type': 'profile',
            'uploaded_by': 'user-123'
        }),
        'headers': {'Content-Type': 'application/json'},
        'httpMethod': 'POST'
    }
    
    class MockContext:
        function_name = 'photo-upload-test'
        aws_request_id = 'test-123'
    
    # Test the refactored handler
    response = lambda_handler(test_event, MockContext())
    print(json.dumps(response, indent=2))