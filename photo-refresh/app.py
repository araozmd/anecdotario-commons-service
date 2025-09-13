"""
Photo Refresh Lambda Function
Self-contained photo URL refresh service for users, orgs, campaigns, etc.
"""
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError


def create_success_response(data: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create protocol-agnostic success response for internal Lambda communication"""
    response = {
        "success": True,
        "data": data
    }
    
    # Build metadata
    response_metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "function_name": "photo-refresh"
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
        "function_name": "photo-refresh"
    }
    
    return response


def validate_input(event: dict) -> Dict[str, Any]:
    """Validate input parameters"""
    # Handle both direct Lambda invocation and API Gateway formats
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")
    else:
        body = event
    
    # Check required fields
    required_fields = ['entity_type', 'entity_id']
    for field in required_fields:
        if field not in body or not body[field]:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate entity_type
    valid_entity_types = ['user', 'org', 'campaign']
    if body['entity_type'] not in valid_entity_types:
        raise ValueError(f"Invalid entity_type. Must be one of: {', '.join(valid_entity_types)}")
    
    return body


def generate_presigned_urls(bucket_name: str, s3_keys: list, expiry: int = 604800) -> Dict[str, str]:
    """Generate presigned URLs for S3 objects"""
    s3_client = boto3.client('s3')
    urls = {}
    
    for s3_key in s3_keys:
        try:
            # Check if it's a thumbnail (public) or protected image
            if '/thumbnail_' in s3_key:
                # Public URL for thumbnails
                urls[s3_key] = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
            else:
                # Presigned URL for protected images
                urls[s3_key] = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=expiry
                )
        except ClientError as e:
            print(f"Error generating URL for {s3_key}: {str(e)}")
    
    return urls


def lambda_handler(event, context):
    """
    Photo URL refresh handler for all entity types
    
    Expected request format:
    {
        "entity_type": "user|org|campaign",
        "entity_id": "nickname_or_id",
        "photo_type": "profile|logo|banner|gallery" // optional
    }
    """
    
    try:
        # Validate input
        params = validate_input(event)
        
        entity_type = params['entity_type']
        entity_id = params['entity_id']
        photo_type = params.get('photo_type')
        
        print(f"Refreshing photo URLs: {entity_type}/{entity_id}/{photo_type or 'all'}")
        
        # Get bucket name from environment
        bucket_name = os.environ.get('PHOTO_BUCKET_NAME')
        if not bucket_name:
            return create_failure_response(
                "CONFIGURATION_ERROR",
                "S3 bucket not configured",
                {"missing_config": "PHOTO_BUCKET_NAME"}
            )
        
        s3_client = boto3.client('s3')
        
        # Build S3 prefix for the entity
        if photo_type:
            prefix = f"{entity_type}/{entity_id}/{photo_type}/"
        else:
            prefix = f"{entity_type}/{entity_id}/"
        
        # List objects with the prefix
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix
            )
            
            s3_keys = []
            if 'Contents' in response:
                s3_keys = [obj['Key'] for obj in response['Contents']]
            
            if not s3_keys:
                return create_failure_response(
                    'NOT_FOUND',
                    'No photos found for the specified entity',
                    {
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'photo_type': photo_type,
                        'prefix_searched': prefix
                    }
                )
            
            # Generate fresh URLs
            urls = generate_presigned_urls(bucket_name, s3_keys)
            
            # Organize URLs by photo type and version
            organized_urls = {}
            for s3_key, url in urls.items():
                # Parse S3 key: entity_type/entity_id/photo_type/version_timestamp_id.jpg
                key_parts = s3_key.split('/')
                if len(key_parts) >= 4:
                    current_photo_type = key_parts[2]
                    filename = key_parts[3]
                    
                    # Extract version from filename
                    if filename.startswith('thumbnail_'):
                        version = 'thumbnail'
                    elif filename.startswith('standard_'):
                        version = 'standard'
                    elif filename.startswith('high_res_'):
                        version = 'high_res'
                    else:
                        version = 'unknown'
                    
                    if current_photo_type not in organized_urls:
                        organized_urls[current_photo_type] = {}
                    
                    organized_urls[current_photo_type][version] = url
            
            response_data = {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'photo_type': photo_type,
                'photos_found': len(s3_keys),
                'urls': organized_urls,
                'url_expiry': {
                    'expires_in_seconds': 604800,  # 7 days
                    'refreshed_at': datetime.now(timezone.utc).isoformat() + "Z"
                }
            }
            
            execution_metadata = {
                'total_urls_generated': len(urls),
                'prefix_searched': prefix,
                'bucket_name': bucket_name
            }
            
        except ClientError as e:
            return create_failure_response(
                "S3_ERROR",
                "Error listing S3 objects",
                {"s3_error": str(e), "prefix": prefix}
            )
        
        print(f"Photo URL refresh completed successfully")
        
        return create_success_response(response_data, execution_metadata)
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "required_fields": ["entity_type", "entity_id"],
                "optional_fields": ["photo_type"]
            }
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Photo URL refresh failed due to internal error",
            {"error_details": str(e)}
        )