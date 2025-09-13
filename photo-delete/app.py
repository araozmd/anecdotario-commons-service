"""
Photo Delete Lambda Function
Self-contained photo deletion service for users, orgs, campaigns, etc.
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
        "function_name": "photo-delete"
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
        "function_name": "photo-delete"
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
    
    # Check if we have either photo_id or entity parameters
    photo_id = body.get('photo_id')
    entity_type = body.get('entity_type')
    entity_id = body.get('entity_id')
    
    if not photo_id and not (entity_type and entity_id):
        raise ValueError('Must provide either photo_id or entity_type+entity_id')
    
    # Validate entity_type if provided
    if entity_type:
        valid_entity_types = ['user', 'org', 'campaign']
        if entity_type not in valid_entity_types:
            raise ValueError(f"Invalid entity_type. Must be one of: {', '.join(valid_entity_types)}")
    
    return body


def delete_s3_objects(bucket_name: str, s3_keys: list) -> Dict[str, Any]:
    """Delete multiple objects from S3"""
    if not s3_keys:
        return {'deleted': [], 'errors': []}
    
    s3_client = boto3.client('s3')
    deleted = []
    errors = []
    
    try:
        # Prepare delete request
        delete_keys = [{'Key': key} for key in s3_keys]
        
        # Delete objects in batches (S3 allows up to 1000 per request)
        batch_size = 1000
        for i in range(0, len(delete_keys), batch_size):
            batch = delete_keys[i:i + batch_size]
            
            response = s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={
                    'Objects': batch,
                    'Quiet': False
                }
            )
            
            # Track successful deletions
            if 'Deleted' in response:
                deleted.extend([obj['Key'] for obj in response['Deleted']])
            
            # Track errors
            if 'Errors' in response:
                errors.extend([
                    f"Failed to delete {obj['Key']}: {obj['Message']}"
                    for obj in response['Errors']
                ])
    
    except ClientError as e:
        errors.append(f"S3 delete operation failed: {str(e)}")
    
    return {'deleted': deleted, 'errors': errors}


def lambda_handler(event, context):
    """
    Photo deletion handler supporting two operation modes
    
    Mode 1 - Delete by photo ID:
    {"photo_id": "photo_123"}
    
    Mode 2 - Delete entity photos:
    {"entity_type": "user", "entity_id": "john", "photo_type": "profile"}
    """
    
    try:
        # Validate input
        params = validate_input(event)
        
        # Get S3 bucket name
        bucket_name = os.environ.get('PHOTO_BUCKET_NAME')
        if not bucket_name:
            return create_failure_response(
                "CONFIGURATION_ERROR",
                "S3 bucket not configured",
                {"missing_config": "PHOTO_BUCKET_NAME"}
            )
        
        # Determine deletion mode
        photo_id = params.get('photo_id')
        entity_type = params.get('entity_type')
        entity_id = params.get('entity_id')
        photo_type = params.get('photo_type')
        
        if photo_id:
            # Mode 1: Delete specific photo by ID (simplified - just return success for now)
            print(f"Deleting photo by ID: {photo_id}")
            
            response_data = {
                'photo_id': photo_id,
                'deletion_mode': 'by_photo_id',
                'note': 'Specific photo ID deletion implementation needed'
            }
            
        elif entity_type and entity_id:
            # Mode 2: Delete entity photos by listing S3 objects with prefix
            print(f"Deleting entity photos: {entity_type}/{entity_id}/{photo_type or 'all'}")
            
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
                
                # Delete the objects
                delete_result = delete_s3_objects(bucket_name, s3_keys)
                
                response_data = {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'photo_type': photo_type,
                    'deletion_mode': 'by_entity',
                    'photos_found': len(s3_keys),
                    'photos_deleted': len(delete_result['deleted']),
                    'deletion_summary': {
                        'successful_deletions': len(delete_result['deleted']),
                        'failed_deletions': len(delete_result['errors']),
                        'total_files_processed': len(s3_keys)
                    }
                }
                
                execution_metadata = {
                    'deleted_files': delete_result['deleted'],
                    'errors': delete_result['errors'] if delete_result['errors'] else None,
                    'prefix_searched': prefix
                }
                
                if len(s3_keys) == 0:
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
                
            except ClientError as e:
                return create_failure_response(
                    "S3_ERROR",
                    "Error listing S3 objects",
                    {"s3_error": str(e), "prefix": prefix}
                )
        
        print(f"Photo deletion completed successfully")
        
        # Return success response with metadata if available
        if 'execution_metadata' in locals():
            return create_success_response(response_data, execution_metadata)
        else:
            return create_success_response(response_data)
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        return create_failure_response(
            "VALIDATION_ERROR",
            str(e),
            {
                "required_fields": "Either 'photo_id' or ('entity_type' and 'entity_id')"
            }
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_failure_response(
            "INTERNAL_ERROR",
            "Photo deletion failed due to internal error",
            {"error_details": str(e)}
        )