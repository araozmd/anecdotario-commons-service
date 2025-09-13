"""
AWS-specific utilities for commons-service
"""
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from .constants import HTTPConstants
from .validation_utils import generate_storage_key
from .config import config
from .logger import logger


def create_response(status_code: int, body: str, event: Optional[dict] = None, headers: Optional[dict] = None) -> Dict[str, Any]:
    """
    Create standardized Lambda proxy response
    
    Args:
        status_code: HTTP status code
        body: Response body (JSON string)
        event: Original Lambda event for context
        headers: Additional headers
        
    Returns:
        Lambda proxy integration response
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': body
    }


def create_error_response(status_code: int, message: str, event: Optional[dict] = None, details: Optional[dict] = None) -> Dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        status_code: HTTP status code
        message: Error message
        event: Original Lambda event for context
        details: Additional error details
        
    Returns:
        Lambda proxy integration error response
    """
    error_body = {
        'success': False,
        'error': message,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if details:
        error_body.update(details)
    
    return create_response(status_code, json.dumps(error_body), event)


def generate_s3_key(entity_type: str, entity_id: str, photo_type: str, version: str, file_extension: str = 'jpg') -> str:
    """
    Generate S3 key for photo files
    
    Args:
        entity_type: Type of entity ('user', 'org', etc.)
        entity_id: Entity identifier (nickname, org_id, etc.)
        photo_type: Photo type ('profile', 'logo', etc.)
        version: Image version ('thumbnail', 'standard', 'high_res')
        file_extension: File extension (default: 'jpg')
        
    Returns:
        S3 object key
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{version}_{timestamp}_{unique_id}.{file_extension}"
    
    return f"{entity_type}/{entity_id}/{photo_type}/{filename}"


def generate_photo_id() -> str:
    """
    Generate unique photo ID
    
    Returns:
        Unique photo identifier
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"photo_{timestamp}_{unique_id}"


def generate_presigned_url(bucket_name: str, s3_key: str, expiry_seconds: Optional[int] = None) -> Optional[str]:
    """
    Generate presigned URL for S3 object
    
    Args:
        bucket_name: S3 bucket name
        s3_key: S3 object key
        expiry_seconds: URL expiry in seconds (default from config)
        
    Returns:
        Presigned URL or None if error
    """
    if expiry_seconds is None:
        expiry_seconds = config.presigned_url_expiry
    
    try:
        s3_client = boto3.client('s3')
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expiry_seconds
        )
        return presigned_url
    
    except ClientError as e:
        logger.error("Failed to generate presigned URL", error=e, bucket=bucket_name, key=s3_key)
        return None
    except Exception as e:
        logger.error("Unexpected error generating presigned URL", error=e, bucket=bucket_name, key=s3_key)
        return None


def generate_public_url(bucket_name: str, s3_key: str) -> str:
    """
    Generate public URL for S3 object (for thumbnails)
    
    Args:
        bucket_name: S3 bucket name
        s3_key: S3 object key
        
    Returns:
        Public S3 URL
    """
    return f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"


def create_success_response(data: Any, metadata: Optional[Dict[str, Any]] = None, function_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create protocol-agnostic success response for internal Lambda communication
    
    Args:
        data: The actual response data
        metadata: Optional metadata dict
        function_name: Name of the function generating the response
        
    Returns:
        Protocol-agnostic success response
    """
    response = {
        "success": True,
        "data": data
    }
    
    # Build metadata
    response_metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }
    
    if function_name:
        response_metadata["function_name"] = function_name
    
    if metadata:
        response_metadata.update(metadata)
    
    response["metadata"] = response_metadata
    
    return response


def create_failure_response(error_code: str, message: str, details: Optional[Dict[str, Any]] = None, function_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create protocol-agnostic failure response for internal Lambda communication
    
    Args:
        error_code: Error code (e.g., 'VALIDATION_ERROR', 'NOT_FOUND', 'INTERNAL_ERROR')
        message: Human-readable error message
        details: Optional error details dict
        function_name: Name of the function generating the response
        
    Returns:
        Protocol-agnostic failure response
    """
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
    response_metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }
    
    if function_name:
        response_metadata["function_name"] = function_name
    
    response["metadata"] = response_metadata
    
    return response


def calculate_file_hash(data: bytes, algorithm: str = 'md5') -> str:
    """
    Calculate hash of file data
    
    Args:
        data: File bytes
        algorithm: Hash algorithm ('md5', 'sha256')
        
    Returns:
        Hex digest of hash
    """
    if algorithm == 'md5':
        return hashlib.md5(data).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(data).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def delete_s3_objects(bucket_name: str, s3_keys: list) -> Dict[str, Any]:
    """
    Delete multiple S3 objects in batch
    
    Args:
        bucket_name: S3 bucket name
        s3_keys: List of S3 keys to delete
        
    Returns:
        Deletion result summary
    """
    if not s3_keys:
        return {'deleted_count': 0, 'failed_count': 0, 'errors': []}
    
    try:
        s3_client = boto3.client('s3')
        
        # Prepare objects for batch deletion
        delete_objects = [{'Key': key} for key in s3_keys]
        
        response = s3_client.delete_objects(
            Bucket=bucket_name,
            Delete={
                'Objects': delete_objects,
                'Quiet': False  # Return info about deleted objects
            }
        )
        
        deleted_count = len(response.get('Deleted', []))
        errors = response.get('Errors', [])
        failed_count = len(errors)
        
        logger.info("S3 batch deletion completed", 
                   bucket=bucket_name, 
                   deleted_count=deleted_count, 
                   failed_count=failed_count)
        
        return {
            'deleted_count': deleted_count,
            'failed_count': failed_count,
            'errors': errors,
            'success': failed_count == 0
        }
    
    except ClientError as e:
        logger.error("S3 batch deletion failed", error=e, bucket=bucket_name, keys_count=len(s3_keys))
        return {
            'deleted_count': 0,
            'failed_count': len(s3_keys),
            'errors': [str(e)],
            'success': False
        }
    except Exception as e:
        logger.error("Unexpected error in S3 batch deletion", error=e, bucket=bucket_name)
        return {
            'deleted_count': 0,
            'failed_count': len(s3_keys),
            'errors': [str(e)],
            'success': False
        }


def upload_to_s3(bucket_name: str, s3_key: str, data: bytes, content_type: str = 'image/jpeg') -> bool:
    """
    Upload data to S3
    
    Args:
        bucket_name: S3 bucket name
        s3_key: S3 object key
        data: File data to upload
        content_type: MIME content type
        
    Returns:
        True if successful, False otherwise
    """
    try:
        s3_client = boto3.client('s3')
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=data,
            ContentType=content_type
        )
        
        logger.info("S3 upload successful", bucket=bucket_name, key=s3_key, size=len(data))
        return True
    
    except ClientError as e:
        logger.error("S3 upload failed", error=e, bucket=bucket_name, key=s3_key)
        return False
    except Exception as e:
        logger.error("Unexpected error in S3 upload", error=e, bucket=bucket_name, key=s3_key)
        return False


def parse_base64_image(image_data: str) -> bytes:
    """
    Parse base64 encoded image data
    
    Args:
        image_data: Base64 encoded image string (with or without data URL prefix)
        
    Returns:
        Image bytes
        
    Raises:
        ValueError: If image data is invalid
    """
    import base64
    
    if not image_data:
        raise ValueError("No image data provided")
    
    # Remove data URL prefix if present (data:image/jpeg;base64,...)
    if ',' in image_data and image_data.startswith('data:'):
        image_data = image_data.split(',')[1]
    
    try:
        return base64.b64decode(image_data)
    except Exception as e:
        raise ValueError(f"Invalid base64 image data: {str(e)}")


def validate_entity_type(entity_type: str, valid_types: Optional[list] = None) -> bool:
    """
    Validate entity type
    
    Args:
        entity_type: Entity type to validate
        valid_types: List of valid types (default from constants)
        
    Returns:
        True if valid, False otherwise
    """
    if valid_types is None:
        from .constants import EntityConstants
        valid_types = EntityConstants.ALL_ENTITY_TYPES
    
    return entity_type.lower() in [t.lower() for t in valid_types]


def validate_photo_type(photo_type: str, entity_type: Optional[str] = None) -> bool:
    """
    Validate photo type for entity
    
    Args:
        photo_type: Photo type to validate
        entity_type: Entity type for context-specific validation
        
    Returns:
        True if valid, False otherwise
    """
    from .constants import EntityConstants
    
    if entity_type:
        entity_type = entity_type.lower()
        if entity_type == 'user':
            valid_types = EntityConstants.USER_PHOTO_TYPES
        elif entity_type == 'org':
            valid_types = EntityConstants.ORG_PHOTO_TYPES
        elif entity_type == 'campaign':
            valid_types = EntityConstants.CAMPAIGN_PHOTO_TYPES
        else:
            valid_types = EntityConstants.ALL_PHOTO_TYPES
    else:
        valid_types = EntityConstants.ALL_PHOTO_TYPES
    
    return photo_type.lower() in [t.lower() for t in valid_types]


