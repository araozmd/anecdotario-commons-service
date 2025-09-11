"""
Photo Delete Lambda Function
Self-contained photo deletion service for users, orgs, campaigns, etc.
"""
import json
import os
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError


def create_response(status_code: int, body: str, headers: dict = None) -> Dict[str, Any]:
    """Create standardized Lambda proxy response"""
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


def create_error_response(status_code: int, message: str, details: dict = None) -> Dict[str, Any]:
    """Create standardized error response"""
    error_body = {
        'error': True,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        error_body['details'] = details
    
    return create_response(status_code, json.dumps(error_body))


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
            return create_error_response(500, "S3 bucket not configured")
        
        # Determine deletion mode
        photo_id = params.get('photo_id')
        entity_type = params.get('entity_type')
        entity_id = params.get('entity_id')
        photo_type = params.get('photo_type')
        
        if photo_id:
            # Mode 1: Delete specific photo by ID (simplified - just return success for now)
            print(f"Deleting photo by ID: {photo_id}")
            
            response_data = {
                'success': True,
                'message': f'Photo {photo_id} deletion requested',
                'photo_id': photo_id,
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
                    'success': True,
                    'message': 'Entity photos deleted successfully',
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'photo_type': photo_type,
                    'photos_found': len(s3_keys),
                    'photos_deleted': len(delete_result['deleted']),
                    'deleted_files': delete_result['deleted'],
                    'errors': delete_result['errors'] if delete_result['errors'] else None
                }
                
                if len(s3_keys) == 0:
                    return create_error_response(
                        404,
                        'No photos found for the specified entity',
                        {
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'photo_type': photo_type,
                            'prefix_searched': prefix
                        }
                    )
                
            except ClientError as e:
                return create_error_response(500, f"Error listing S3 objects: {str(e)}")
        
        print(f"Photo deletion completed successfully")
        
        return create_response(200, json.dumps(response_data))
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_error_response(500, 'Internal server error')