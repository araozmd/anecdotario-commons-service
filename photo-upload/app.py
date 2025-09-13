"""
Photo Upload Lambda Function
Self-contained photo upload service for users, orgs, campaigns, etc.
"""
import json
import os
import base64
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from PIL import Image
import io


def create_success_response(data: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create protocol-agnostic success response for internal Lambda communication"""
    response = {
        "success": True,
        "data": data
    }
    
    # Build metadata
    response_metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "function_name": "photo-upload"
    }
    
    if metadata:
        response_metadata.update(metadata)
    
    response["metadata"] = response_metadata
    
    return response


def create_failure_response(error_code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create protocol-agnostic failure response for internal Lambda communication"""
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message
        }
    }
    
    if details:
        response["error"]["details"] = details
    
    # Build metadata
    response["metadata"] = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "function_name": "photo-upload"
    }
    
    return response


def validate_input(event: dict) -> Dict[str, Any]:
    """Validate input parameters"""
    required_fields = ['image', 'entity_type', 'entity_id', 'photo_type']
    
    # Handle both direct Lambda invocation and API Gateway formats
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")
    else:
        body = event
    
    # Check required fields
    for field in required_fields:
        if field not in body or not body[field]:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate entity_type
    valid_entity_types = ['user', 'org', 'campaign']
    if body['entity_type'] not in valid_entity_types:
        raise ValueError(f"Invalid entity_type. Must be one of: {', '.join(valid_entity_types)}")
    
    # Validate photo_type
    valid_photo_types = ['profile', 'logo', 'banner', 'gallery']
    if body['photo_type'] not in valid_photo_types:
        raise ValueError(f"Invalid photo_type. Must be one of: {', '.join(valid_photo_types)}")
    
    return body


def process_image(image_data: str) -> Dict[str, bytes]:
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
        
        # Process different versions
        versions = {}
        
        # Thumbnail: 150x150 square
        thumb = img.copy()
        thumb.thumbnail((150, 150), Image.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        thumb.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
        versions['thumbnail'] = thumb_buffer.getvalue()
        
        # Standard: 320x320 square
        standard = img.copy()
        standard.thumbnail((320, 320), Image.Resampling.LANCZOS)
        standard_buffer = io.BytesIO()
        standard.save(standard_buffer, format='JPEG', quality=90, optimize=True)
        versions['standard'] = standard_buffer.getvalue()
        
        # High resolution: 800x800 square
        high_res = img.copy()
        high_res.thumbnail((800, 800), Image.Resampling.LANCZOS)
        high_res_buffer = io.BytesIO()
        high_res.save(high_res_buffer, format='JPEG', quality=95, optimize=True)
        versions['high_res'] = high_res_buffer.getvalue()
        
        return versions
        
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
    
    Expected request format:
    {
        "image": "data:image/jpeg;base64,...",
        "entity_type": "user|org|campaign",
        "entity_id": "nickname_or_id",
        "photo_type": "profile|logo|banner|gallery",
        "uploaded_by": "user_id",
        "upload_source": "user-service|org-service"
    }
    """
    
    try:
        # Validate input
        params = validate_input(event)
        
        image_data = params['image']
        entity_type = params['entity_type']
        entity_id = params['entity_id']
        photo_type = params['photo_type']
        uploaded_by = params.get('uploaded_by')
        upload_source = params.get('upload_source', 'unknown')
        
        print(f"Processing photo upload: {entity_type}/{entity_id}/{photo_type}")
        
        # Get bucket name from environment or parameter store
        bucket_name = os.environ.get('PHOTO_BUCKET_NAME')
        if not bucket_name:
            return create_failure_response(
                "CONFIGURATION_ERROR",
                "S3 bucket not configured",
                {"missing_config": "PHOTO_BUCKET_NAME"}
            )
        
        # Process image into multiple versions
        versions = process_image(image_data)
        
        # Upload to S3
        upload_result = upload_to_s3(bucket_name, entity_type, entity_id, photo_type, versions)
        
        # Generate photo ID
        photo_id = f"{entity_type}_{entity_id}_{photo_type}_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Create success response
        response_data = {
            'photo_id': photo_id,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'photo_type': photo_type,
            'urls': upload_result['urls']
        }
        
        # Execution metadata
        execution_metadata = {
            's3_keys': upload_result['s3_keys'],
            'bucket_name': bucket_name,
            'uploaded_by': uploaded_by,
            'upload_source': upload_source
        }
        
        print(f"Photo upload completed successfully: {photo_id}")
        
        return create_success_response(response_data, execution_metadata)
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "field": "input_validation",
                "required_fields": ["image", "entity_type", "entity_id", "photo_type"]
            }
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Photo upload failed due to internal error",
            {"error_details": str(e)}
        )