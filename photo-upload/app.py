"""
Photo Upload Lambda Function
Self-contained photo upload service for users, orgs, campaigns, etc.
"""
import json
import os
import base64
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from PIL import Image
import io
from anecdotario_commons.contracts import PhotoUploadResponse, PhotoUploadRequest


def create_failure_response(message: str, entity_type: str = "user", entity_id: str = "", photo_type: str = "profile") -> Dict[str, Any]:
    """Create failure response using PhotoUploadResponse contract"""
    response = PhotoUploadResponse(
        success=False,
        photo_id="",
        entity_type=entity_type,
        entity_id=entity_id,
        photo_type=photo_type,
        message=message
    )
    return response.to_dict()


def validate_input(event: dict) -> PhotoUploadRequest:
    """
    Validate input parameters and return PhotoUploadRequest contract object.

    Performs runtime validation of Literal types since dataclass type hints
    don't enforce validation at runtime.
    """
    # Handle both direct Lambda invocation and API Gateway formats
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")
    else:
        body = event

    # Validate required fields before creating the request
    required_fields = {
        'image': 'Missing required field: image',
        'entity_type': 'Missing required field: entity_type',
        'entity_id': 'Missing required field: entity_id',
        'photo_type': 'Missing required field: photo_type'
    }

    for field, error_msg in required_fields.items():
        if field not in body or not body[field]:
            raise ValueError(error_msg)

    # Validate enum values manually (since Literal types don't enforce runtime validation)
    valid_entity_types = ['user', 'org', 'campaign']
    if body['entity_type'] not in valid_entity_types:
        raise ValueError(f"Invalid entity_type '{body['entity_type']}'. Must be one of: {valid_entity_types}")

    valid_photo_types = ['profile', 'logo', 'banner', 'gallery', 'thumbnail']
    if body['photo_type'] not in valid_photo_types:
        raise ValueError(f"Invalid photo_type '{body['photo_type']}'. Must be one of: {valid_photo_types}")

    # Validate upload_source if provided
    if 'upload_source' in body and body['upload_source']:
        valid_upload_sources = ['user-service', 'org-service', 'campaign-service', 'api', 'admin']
        if body['upload_source'] not in valid_upload_sources:
            raise ValueError(f"Invalid upload_source '{body['upload_source']}'. Must be one of: {valid_upload_sources}")

    # Create PhotoUploadRequest using the contract structure
    try:
        request = PhotoUploadRequest(
            image=body['image'],
            entity_type=body['entity_type'],
            entity_id=body['entity_id'],
            photo_type=body['photo_type'],
            uploaded_by=body.get('uploaded_by'),
            upload_source=body.get('upload_source', 'api')  # Default to 'api' as per contract
        )
        return request

    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid request parameters: {str(e)}")


def process_image(image_data: str) -> tuple[Dict[str, bytes], Dict[str, int]]:
    """Process image into multiple versions"""
    try:
        # Remove data URL prefix if present
        if image_data.startswith('data:image/'):
            image_data = image_data.split(',', 1)[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        
        # Open image with PIL
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Get original size for metrics
        original_size = len(image_bytes)

        # Process different versions
        versions = {}
        sizes = {}

        # Thumbnail: 150x150 square
        thumb = img.copy()
        thumb.thumbnail((150, 150), Image.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        thumb.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
        versions['thumbnail'] = thumb_buffer.getvalue()
        sizes['thumbnail'] = len(versions['thumbnail'])

        # Standard: 320x320 square
        standard = img.copy()
        standard.thumbnail((320, 320), Image.Resampling.LANCZOS)
        standard_buffer = io.BytesIO()
        standard.save(standard_buffer, format='JPEG', quality=90, optimize=True)
        versions['standard'] = standard_buffer.getvalue()
        sizes['standard'] = len(versions['standard'])

        # High resolution: 800x800 square
        high_res = img.copy()
        high_res.thumbnail((800, 800), Image.Resampling.LANCZOS)
        high_res_buffer = io.BytesIO()
        high_res.save(high_res_buffer, format='JPEG', quality=95, optimize=True)
        versions['high_res'] = high_res_buffer.getvalue()
        sizes['high_res'] = len(versions['high_res'])

        # Add original size for comparison
        sizes['original'] = original_size

        return versions, sizes
        
    except Exception as e:
        raise ValueError(f"Error processing image: {str(e)}")


def upload_to_s3(bucket_name: str, entity_type: str, entity_id: str, photo_type: str, versions: Dict[str, bytes]) -> Dict[str, str]:
    """Upload image versions to S3"""
    s3_client = boto3.client('s3')
    
    # Generate unique identifiers
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    
    # Upload each version
    s3_keys = {}
    urls = {}
    
    for version_name, image_bytes in versions.items():
        # Create S3 key
        s3_key = f"{entity_type}/{entity_id}/{photo_type}/{version_name}_{timestamp}_{unique_id}.jpg"
        
        try:
            # Upload to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=image_bytes,
                ContentType='image/jpeg',
                ServerSideEncryption='AES256'
            )
            
            s3_keys[version_name] = s3_key
            
            # Generate URLs
            if version_name == 'thumbnail':
                # Public URL for thumbnails
                urls[version_name] = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
            else:
                # Presigned URLs for protected images (7 days expiry)
                urls[version_name] = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=604800  # 7 days
                )
            
        except ClientError as e:
            raise Exception(f"Error uploading {version_name} to S3: {str(e)}")
    
    return {'s3_keys': s3_keys, 'urls': urls}


def lambda_handler(event, context):
    """
    Photo upload handler for all entity types

    Uses PhotoUploadRequest contract for input validation.

    Expected request format follows PhotoUploadRequest schema:
    - image: base64 encoded image data
    - entity_type: 'user', 'org', or 'campaign'
    - entity_id: identifier for the entity
    - photo_type: 'profile', 'logo', 'banner', 'gallery', or 'thumbnail'
    - uploaded_by: optional user ID
    - upload_source: optional source service
    """

    start_time = time.time()

    try:
        # Validate input using contract
        request = validate_input(event)

        image_data = request.image
        entity_type = request.entity_type
        entity_id = request.entity_id
        photo_type = request.photo_type
        uploaded_by = request.uploaded_by
        upload_source = request.upload_source or 'unknown'

        print(f"Processing photo upload: {entity_type}/{entity_id}/{photo_type}")

        # Get bucket name from environment or parameter store
        bucket_name = os.environ.get('PHOTO_BUCKET_NAME')
        if not bucket_name:
            return create_failure_response(
                "S3 bucket not configured",
                entity_type, entity_id, photo_type
            )

        # Process image into multiple versions
        versions, sizes = process_image(image_data)

        # Upload to S3
        upload_result = upload_to_s3(bucket_name, entity_type, entity_id, photo_type, versions)

        # Generate photo ID
        photo_id = f"{entity_type}_{entity_id}_{photo_type}_{int(datetime.now(timezone.utc).timestamp())}"

        # Calculate processing metrics
        processing_time = round(time.time() - start_time, 3)

        # Calculate size reduction
        original_size = sizes['original']
        largest_processed = max(sizes['thumbnail'], sizes['standard'], sizes['high_res'])
        reduction_percent = round((1 - largest_processed / original_size) * 100, 1)
        size_reduction = f"{reduction_percent}% (from {original_size} to {largest_processed} bytes)"

        # Create version info
        version_info = {
            'thumbnail': {'size': sizes['thumbnail'], 'dimensions': '150x150'},
            'standard': {'size': sizes['standard'], 'dimensions': '320x320'},
            'high_res': {'size': sizes['high_res'], 'dimensions': '800x800'}
        }

        print(f"Photo upload completed successfully: {photo_id}")

        # Create PhotoUploadResponse using the contract
        response = PhotoUploadResponse(
            success=True,
            photo_id=photo_id,
            entity_type=entity_type,
            entity_id=entity_id,
            photo_type=photo_type,
            thumbnail_url=upload_result['urls'].get('thumbnail'),
            standard_url=upload_result['urls'].get('standard'),
            high_res_url=upload_result['urls'].get('high_res'),
            versions=version_info,
            processing_time=processing_time,
            size_reduction=size_reduction,
            message=f"Photo uploaded successfully in {processing_time}s"
        )

        return response.to_dict()

    except ValueError as e:
        print(f"Validation error: {str(e)}")
        entity_type = event.get('entity_type', 'user')
        entity_id = event.get('entity_id', '')
        photo_type = event.get('photo_type', 'profile')
        return create_failure_response(
            f"Validation error: {str(e)}",
            entity_type, entity_id, photo_type
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        entity_type = event.get('entity_type', 'user')
        entity_id = event.get('entity_id', '')
        photo_type = event.get('photo_type', 'profile')
        return create_failure_response(
            f"Photo upload failed: {str(e)}",
            entity_type, entity_id, photo_type
        )