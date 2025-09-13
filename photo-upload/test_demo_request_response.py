"""
Photo Upload Lambda Function - Request/Response Format Demonstration
===================================================================

This test file demonstrates the exact request and response formats for the photo-upload
Lambda function, using dummy data and proper AWS mocking to show the contract structure.

Key Features Demonstrated:
- PhotoUploadRequest contract structure
- PhotoUploadResponse contract structure
- Base64 image handling (minimal 1x1 pixel test images)
- S3 operations mocking
- Success and error scenarios
- All supported entity types and photo types
"""
import json
import pytest
import os
import sys
import base64
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws
import boto3
from PIL import Image
import io

# Add the parent directory to sys.path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up environment
os.environ['PHOTO_BUCKET_NAME'] = 'anecdotario-photos-test'

from app import lambda_handler, validate_input, process_image, upload_to_s3
from anecdotario_commons.contracts import PhotoUploadResponse, PhotoUploadRequest


class TestPhotoUploadRequestResponseDemo:
    """
    Demonstration of photo-upload Lambda function request/response formats
    """

    def create_minimal_test_image(self, format='JPEG', color='red') -> str:
        """
        Create a minimal 1x1 pixel test image in base64 format

        Args:
            format: 'JPEG' or 'PNG'
            color: Color for the pixel

        Returns:
            Base64 encoded image with data URL prefix
        """
        # Create minimal 1x1 pixel image
        img = Image.new('RGB', (1, 1), color=color)
        img_buffer = io.BytesIO()
        img.save(img_buffer, format=format, quality=85)
        img_buffer.seek(0)

        # Convert to base64 with data URL prefix
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        mime_type = f'image/{format.lower()}'
        return f'data:{mime_type};base64,{img_base64}'

    def test_photo_upload_request_contract_structure(self):
        """
        Demonstrate PhotoUploadRequest contract structure with all fields
        """
        print("\n" + "="*60)
        print("PHOTO UPLOAD REQUEST CONTRACT STRUCTURE")
        print("="*60)

        # Create dummy base64 image
        test_image = self.create_minimal_test_image()

        # Complete request with all fields
        complete_request = PhotoUploadRequest(
            image=test_image,
            entity_type="user",
            entity_id="john_doe_123",
            photo_type="profile",
            uploaded_by="user-456789",
            upload_source="user-service"
        )

        print("Complete PhotoUploadRequest structure:")
        print(json.dumps({
            "image": f"{test_image[:50]}...",  # Truncated for display
            "entity_type": complete_request.entity_type,
            "entity_id": complete_request.entity_id,
            "photo_type": complete_request.photo_type,
            "uploaded_by": complete_request.uploaded_by,
            "upload_source": complete_request.upload_source
        }, indent=2))

        # Minimal required request
        minimal_request = PhotoUploadRequest(
            image=test_image,
            entity_type="org",
            entity_id="acme_corp",
            photo_type="logo"
        )

        print("\nMinimal PhotoUploadRequest structure:")
        print(json.dumps({
            "image": f"{test_image[:50]}...",  # Truncated for display
            "entity_type": minimal_request.entity_type,
            "entity_id": minimal_request.entity_id,
            "photo_type": minimal_request.photo_type,
            "uploaded_by": minimal_request.uploaded_by,  # Will be None
            "upload_source": minimal_request.upload_source  # Will be None
        }, indent=2))

        # Valid enum values
        print("\nValid enum values:")
        print("entity_type: ['user', 'org', 'campaign']")
        print("photo_type: ['profile', 'logo', 'banner', 'gallery', 'thumbnail']")
        print("upload_source: ['user-service', 'org-service', 'campaign-service', 'api', 'admin']")

        # Assertions
        assert complete_request.entity_type == "user"
        assert complete_request.photo_type == "profile"
        assert minimal_request.uploaded_by is None
        assert minimal_request.upload_source is None

    @mock_aws
    def test_photo_upload_success_response_structure(self):
        """
        Demonstrate PhotoUploadResponse structure for successful upload
        """
        print("\n" + "="*60)
        print("PHOTO UPLOAD SUCCESS RESPONSE STRUCTURE")
        print("="*60)

        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='anecdotario-photos-test')

        # Create test image
        test_image = self.create_minimal_test_image('JPEG', 'blue')

        # Create request event
        request_event = {
            'image': test_image,
            'entity_type': 'user',
            'entity_id': 'alice_smith',
            'photo_type': 'profile',
            'uploaded_by': 'user-789123',
            'upload_source': 'user-service'
        }

        print("Request event:")
        display_event = request_event.copy()
        display_event['image'] = f"{test_image[:50]}..."  # Truncated for display
        print(json.dumps(display_event, indent=2))

        # Execute lambda handler
        response = lambda_handler(request_event, Mock())

        print("\nSuccess response structure:")
        print(json.dumps(response, indent=2))

        # Verify response follows PhotoUploadResponse contract
        assert response['success'] is True
        assert 'photo_id' in response
        assert response['entity_type'] == 'user'
        assert response['entity_id'] == 'alice_smith'
        assert response['photo_type'] == 'profile'
        assert 'thumbnail_url' in response
        assert 'standard_url' in response
        assert 'high_res_url' in response
        assert 'versions' in response
        assert 'processing_time' in response
        assert 'size_reduction' in response
        assert 'message' in response

        # Verify URL formats
        assert response['thumbnail_url'].startswith('https://')
        assert response['standard_url'].startswith('https://')
        assert response['high_res_url'].startswith('https://')

        # Verify versions structure
        versions = response['versions']
        assert 'thumbnail' in versions
        assert 'standard' in versions
        assert 'high_res' in versions

        for version, info in versions.items():
            assert 'size' in info
            assert 'dimensions' in info

    def test_photo_upload_validation_error_response(self):
        """
        Demonstrate PhotoUploadResponse structure for validation errors
        """
        print("\n" + "="*60)
        print("PHOTO UPLOAD VALIDATION ERROR RESPONSE")
        print("="*60)

        # Test missing required fields
        invalid_events = [
            {
                'entity_type': 'user',
                'entity_id': 'test_user',
                'photo_type': 'profile'
                # Missing 'image'
            },
            {
                'image': self.create_minimal_test_image(),
                'entity_id': 'test_user',
                'photo_type': 'profile'
                # Missing 'entity_type'
            },
            {
                'image': self.create_minimal_test_image(),
                'entity_type': 'invalid_type',  # Invalid enum value
                'entity_id': 'test_user',
                'photo_type': 'profile'
            }
        ]

        error_scenarios = [
            "Missing required field: image",
            "Missing required field: entity_type",
            "Invalid entity_type"
        ]

        for i, (event, scenario) in enumerate(zip(invalid_events, error_scenarios)):
            print(f"\n--- Error Scenario {i+1}: {scenario} ---")

            print("Request event:")
            display_event = event.copy()
            if 'image' in display_event:
                display_event['image'] = f"{event['image'][:50]}..."
            print(json.dumps(display_event, indent=2))

            response = lambda_handler(event, Mock())

            print("Error response:")
            print(json.dumps(response, indent=2))

            # Verify error response follows contract
            assert response['success'] is False
            assert response['photo_id'] == ""
            assert 'entity_type' in response
            assert 'entity_id' in response
            assert 'photo_type' in response
            assert 'message' in response
            assert 'Validation error' in response['message']

            # Optional fields should be None for errors
            assert response.get('thumbnail_url') is None
            assert response.get('standard_url') is None
            assert response.get('high_res_url') is None

    @mock_aws
    def test_all_entity_and_photo_types_combinations(self):
        """
        Demonstrate all valid entity_type and photo_type combinations
        """
        print("\n" + "="*60)
        print("ALL VALID ENTITY AND PHOTO TYPE COMBINATIONS")
        print("="*60)

        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='anecdotario-photos-test')

        # Valid combinations
        combinations = [
            ('user', 'profile', 'john_doe'),
            ('user', 'gallery', 'jane_smith'),
            ('org', 'logo', 'acme_corp'),
            ('org', 'banner', 'tech_startup'),
            ('campaign', 'banner', 'summer_2024'),
            ('campaign', 'gallery', 'product_launch')
        ]

        for entity_type, photo_type, entity_id in combinations:
            test_image = self.create_minimal_test_image()

            event = {
                'image': test_image,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'photo_type': photo_type,
                'uploaded_by': f'{entity_type}-admin-123',
                'upload_source': f'{entity_type}-service'
            }

            response = lambda_handler(event, Mock())

            print(f"\n{entity_type.upper()} + {photo_type.upper()}:")
            print(f"  Entity ID: {entity_id}")
            print(f"  Success: {response['success']}")
            print(f"  Photo ID: {response.get('photo_id', 'N/A')}")
            print(f"  Processing Time: {response.get('processing_time', 'N/A')}s")

            assert response['success'] is True
            assert response['entity_type'] == entity_type
            assert response['entity_id'] == entity_id
            assert response['photo_type'] == photo_type

    def test_process_image_functionality_demo(self):
        """
        Demonstrate image processing functionality
        """
        print("\n" + "="*60)
        print("IMAGE PROCESSING FUNCTIONALITY DEMONSTRATION")
        print("="*60)

        # Create test images of different sizes
        test_cases = [
            ('Small 10x10 JPEG', 'JPEG', 10, 10, 'red'),
            ('Medium 100x100 PNG', 'PNG', 100, 100, 'green'),
            ('Large 500x500 JPEG', 'JPEG', 500, 500, 'blue')
        ]

        for name, format, width, height, color in test_cases:
            print(f"\n--- {name} ---")

            # Create test image
            img = Image.new('RGB', (width, height), color=color)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format=format, quality=90)
            img_buffer.seek(0)

            # Convert to base64
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            test_image = f'data:image/{format.lower()};base64,{img_base64}'

            # Process image
            versions, sizes = process_image(test_image)

            print(f"Original size: {sizes['original']} bytes")
            print("Processed versions:")
            for version, size in sizes.items():
                if version != 'original':
                    print(f"  {version}: {size} bytes")

            # Calculate reduction
            largest_processed = max(sizes['thumbnail'], sizes['standard'], sizes['high_res'])
            reduction = round((1 - largest_processed / sizes['original']) * 100, 1)
            print(f"Size reduction: {reduction}%")

            # Verify all versions created
            assert 'thumbnail' in versions
            assert 'standard' in versions
            assert 'high_res' in versions
            assert len(versions['thumbnail']) > 0
            assert len(versions['standard']) > 0
            assert len(versions['high_res']) > 0

    @mock_aws
    def test_s3_upload_structure_demo(self):
        """
        Demonstrate S3 upload structure and URL generation
        """
        print("\n" + "="*60)
        print("S3 UPLOAD STRUCTURE DEMONSTRATION")
        print("="*60)

        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='anecdotario-photos-test')

        # Create test image
        test_image = self.create_minimal_test_image()
        versions, sizes = process_image(test_image)

        # Upload to S3
        bucket_name = 'anecdotario-photos-test'
        entity_type = 'user'
        entity_id = 'demo_user'
        photo_type = 'profile'

        with patch('boto3.client') as mock_boto3:
            mock_s3 = MagicMock()
            mock_s3.put_object.return_value = {'ETag': '"test-etag"'}
            mock_s3.generate_presigned_url.return_value = 'https://bucket.s3.amazonaws.com/presigned-url'
            mock_boto3.return_value = mock_s3

            upload_result = upload_to_s3(bucket_name, entity_type, entity_id, photo_type, versions)

            print("S3 Key Structure:")
            for version, s3_key in upload_result['s3_keys'].items():
                print(f"  {version}: {s3_key}")

            print("\nURL Structure:")
            for version, url in upload_result['urls'].items():
                print(f"  {version}: {url}")

            print("\nKey Pattern: {entity_type}/{entity_id}/{photo_type}/{version}_{timestamp}_{unique_id}.jpg")
            print("- Thumbnail: Public URL (direct S3 access)")
            print("- Standard/High-res: Presigned URLs (7-day expiry)")

            # Verify structure
            assert 'thumbnail' in upload_result['s3_keys']
            assert 'standard' in upload_result['s3_keys']
            assert 'high_res' in upload_result['s3_keys']

            for s3_key in upload_result['s3_keys'].values():
                assert s3_key.startswith(f"{entity_type}/{entity_id}/{photo_type}/")
                assert s3_key.endswith('.jpg')

    def test_api_gateway_vs_direct_invocation_formats(self):
        """
        Demonstrate request format differences between API Gateway and direct Lambda invocation
        """
        print("\n" + "="*60)
        print("API GATEWAY vs DIRECT INVOCATION FORMATS")
        print("="*60)

        test_image = self.create_minimal_test_image()

        # API Gateway format (with body wrapper)
        api_gateway_event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'image': test_image,
                'entity_type': 'user',
                'entity_id': 'api_user',
                'photo_type': 'profile'
            }),
            'headers': {'Content-Type': 'application/json'}
        }

        # Direct Lambda invocation format
        direct_event = {
            'image': test_image,
            'entity_type': 'user',
            'entity_id': 'direct_user',
            'photo_type': 'profile'
        }

        print("API Gateway Event Format:")
        display_api_event = api_gateway_event.copy()
        body_data = json.loads(display_api_event['body'])
        body_data['image'] = f"{test_image[:50]}..."
        display_api_event['body'] = json.dumps(body_data)
        print(json.dumps(display_api_event, indent=2))

        print("\nDirect Lambda Event Format:")
        display_direct_event = direct_event.copy()
        display_direct_event['image'] = f"{test_image[:50]}..."
        print(json.dumps(display_direct_event, indent=2))

        # Test both formats work
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='anecdotario-photos-test')

            # API Gateway format should work
            request_obj_api = validate_input(api_gateway_event)
            assert request_obj_api.entity_id == 'api_user'

            # Direct format should work
            request_obj_direct = validate_input(direct_event)
            assert request_obj_direct.entity_id == 'direct_user'

        print("\nBoth formats successfully validated!")

    def test_error_handling_comprehensive_demo(self):
        """
        Comprehensive demonstration of error handling scenarios
        """
        print("\n" + "="*60)
        print("COMPREHENSIVE ERROR HANDLING DEMONSTRATION")
        print("="*60)

        error_scenarios = [
            {
                'name': 'Missing Image',
                'event': {
                    'entity_type': 'user',
                    'entity_id': 'test_user',
                    'photo_type': 'profile'
                },
                'expected_error': 'Missing required field: image'
            },
            {
                'name': 'Invalid Entity Type',
                'event': {
                    'image': self.create_minimal_test_image(),
                    'entity_type': 'invalid_entity',
                    'entity_id': 'test_user',
                    'photo_type': 'profile'
                },
                'expected_error': 'Invalid entity_type'
            },
            {
                'name': 'Invalid Photo Type',
                'event': {
                    'image': self.create_minimal_test_image(),
                    'entity_type': 'user',
                    'entity_id': 'test_user',
                    'photo_type': 'invalid_photo_type'
                },
                'expected_error': 'Invalid photo_type'
            },
            {
                'name': 'Invalid Upload Source',
                'event': {
                    'image': self.create_minimal_test_image(),
                    'entity_type': 'user',
                    'entity_id': 'test_user',
                    'photo_type': 'profile',
                    'upload_source': 'invalid_source'
                },
                'expected_error': 'Invalid upload_source'
            },
            {
                'name': 'Invalid Image Data',
                'event': {
                    'image': 'data:text/plain;base64,aGVsbG8gd29ybGQ=',  # Text data, not image
                    'entity_type': 'user',
                    'entity_id': 'test_user',
                    'photo_type': 'profile'
                },
                'expected_error': 'Error processing image'
            }
        ]

        for scenario in error_scenarios:
            print(f"\n--- {scenario['name']} ---")

            print("Request:")
            display_event = scenario['event'].copy()
            if 'image' in display_event:
                display_event['image'] = f"{scenario['event']['image'][:50]}..."
            print(json.dumps(display_event, indent=2))

            response = lambda_handler(scenario['event'], Mock())

            print("Error Response:")
            print(json.dumps(response, indent=2))

            # Verify error response structure
            assert response['success'] is False
            assert scenario['expected_error'] in response['message']
            assert response['photo_id'] == ""

            print(f"✓ Correctly handled: {scenario['expected_error']}")


if __name__ == '__main__':
    # Run the demonstration
    demo = TestPhotoUploadRequestResponseDemo()

    print("PHOTO UPLOAD LAMBDA FUNCTION REQUEST/RESPONSE DEMONSTRATION")
    print("=" * 80)

    # Run each demonstration
    demo.test_photo_upload_request_contract_structure()
    demo.test_photo_upload_success_response_structure()
    demo.test_photo_upload_validation_error_response()
    demo.test_all_entity_and_photo_types_combinations()
    demo.test_process_image_functionality_demo()
    demo.test_s3_upload_structure_demo()
    demo.test_api_gateway_vs_direct_invocation_formats()
    demo.test_error_handling_comprehensive_demo()

    print("\n" + "="*80)
    print("DEMONSTRATION COMPLETE")
    print("="*80)