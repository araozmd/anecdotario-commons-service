"""
Utility functions for photo service
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional


def create_response(status_code: int, body: str, event: Dict[str, Any], allowed_methods: list = None) -> Dict[str, Any]:
    """
    Create standardized Lambda response
    
    Args:
        status_code: HTTP status code
        body: Response body (JSON string)
        event: Lambda event (for CORS origin)
        allowed_methods: Allowed HTTP methods for CORS
        
    Returns:
        Lambda response dict
    """
    if allowed_methods is None:
        allowed_methods = ['POST', 'GET', 'DELETE', 'OPTIONS']
    
    # Get origin for CORS (fallback to wildcard)
    origin = event.get('headers', {}).get('origin', '*')
    
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': ', '.join(allowed_methods),
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
            'Access-Control-Allow-Credentials': 'true'
        },
        'body': body
    }
    
    return response


def create_error_response(status_code: int, message: str, event: Dict[str, Any], details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        status_code: HTTP status code
        message: Error message
        event: Lambda event (for CORS)
        details: Optional additional error details
        
    Returns:
        Lambda error response dict
    """
    error_body = {
        'error': message,
        'statusCode': status_code,
        'timestamp': datetime.utcnow().isoformat(),
        'requestId': event.get('requestContext', {}).get('requestId', 'unknown')
    }
    
    if details:
        error_body.update(details)
    
    return create_response(status_code, json.dumps(error_body), event)


def generate_photo_id() -> str:
    """
    Generate unique photo ID
    
    Returns:
        Unique photo identifier
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"photo_{timestamp}_{unique_id}"


def generate_s3_key(entity_type: str, entity_id: str, photo_type: str, version: str, photo_id: str) -> str:
    """
    Generate S3 key for photo storage
    
    Args:
        entity_type: Type of entity ('user', 'org', etc.)
        entity_id: Entity identifier (nickname, org_id, etc.)
        photo_type: Photo type ('profile', 'logo', etc.)
        version: Image version ('thumbnail', 'standard', 'high_res')
        photo_id: Unique photo identifier
        
    Returns:
        S3 object key
    """
    return f"{entity_type}s/{entity_id}/{photo_type}/{version}_{photo_id}.jpg"


def generate_public_url(bucket_name: str, s3_key: str) -> str:
    """
    Generate public S3 URL
    
    Args:
        bucket_name: S3 bucket name
        s3_key: S3 object key
        
    Returns:
        Public S3 URL
    """
    return f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"


def parse_image_data(body: str, is_base64_encoded: bool = False) -> tuple[bytes, Optional[Dict[str, Any]]]:
    """
    Parse image data from request body
    
    Args:
        body: Request body
        is_base64_encoded: Whether body is base64 encoded
        
    Returns:
        Tuple of (image_bytes, metadata_dict)
        
    Raises:
        ValueError: If image data is invalid
    """
    import base64
    
    if is_base64_encoded:
        # Body is already base64 encoded binary data
        return base64.b64decode(body), None
    
    # Parse JSON body
    try:
        body_json = json.loads(body)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in request body")
    
    image_data = body_json.get('image')
    if not image_data:
        raise ValueError("No image data in request body")
    
    # Remove data URL prefix if present (data:image/jpeg;base64,...)
    if ',' in image_data:
        image_data = image_data.split(',')[1]
    
    try:
        image_bytes = base64.b64decode(image_data)
    except Exception:
        raise ValueError("Invalid base64 image data")
    
    # Extract metadata
    metadata = {
        'entity_type': body_json.get('entity_type'),
        'entity_id': body_json.get('entity_id'),
        'photo_type': body_json.get('photo_type', 'profile'),
        'uploaded_by': body_json.get('uploaded_by'),
        'upload_source': body_json.get('upload_source')
    }
    
    return image_bytes, metadata


def validate_entity_request(metadata: Dict[str, Any]) -> Optional[str]:
    """
    Validate entity request metadata
    
    Args:
        metadata: Entity metadata from request
        
    Returns:
        Error message if invalid, None if valid
    """
    required_fields = ['entity_type', 'entity_id']
    
    for field in required_fields:
        if not metadata.get(field):
            return f"Missing required field: {field}"
    
    # Validate entity_type
    valid_entity_types = ['user', 'org', 'campaign']
    if metadata['entity_type'] not in valid_entity_types:
        return f"Invalid entity_type. Must be one of: {', '.join(valid_entity_types)}"
    
    # Validate photo_type
    valid_photo_types = ['profile', 'logo', 'banner', 'gallery']
    if metadata.get('photo_type') and metadata['photo_type'] not in valid_photo_types:
        return f"Invalid photo_type. Must be one of: {', '.join(valid_photo_types)}"
    
    return None


def calculate_size_reduction(original_size: int, optimized_size: int) -> str:
    """
    Calculate size reduction percentage
    
    Args:
        original_size: Original file size in bytes
        optimized_size: Optimized file size in bytes
        
    Returns:
        Size reduction percentage as string
    """
    if original_size == 0:
        return "0.0%"
    
    reduction = (1 - optimized_size / original_size) * 100
    return f"{reduction:.1f}%"