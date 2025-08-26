"""
Photo Delete Lambda Function
Entity-agnostic photo deletion service for users, orgs, campaigns, etc.
"""
import json
import os
import sys
import boto3
from botocore.exceptions import ClientError

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from config import config
from models.photo import Photo
from utils import create_response, create_error_response

# Initialize AWS clients
s3_client = boto3.client('s3')

# Load configuration
PHOTO_BUCKET_NAME = config.get_ssm_parameter('photo-bucket-name', os.environ.get('PHOTO_BUCKET_NAME'))


def delete_photo_by_id(photo_id: str) -> dict:
    """
    Delete a specific photo by ID
    
    Args:
        photo_id: Unique photo identifier
        
    Returns:
        Deletion results dict
    """
    result = {
        'photo_deleted': False,
        's3_files_deleted': [],
        'deletion_errors': [],
        'photo_info': None
    }
    
    try:
        # Get photo from database
        photo = Photo.get(photo_id)
        result['photo_info'] = photo.to_dict()
        
        # Get all S3 keys for this photo
        s3_keys = photo.get_s3_keys()
        
        if s3_keys:
            # Batch delete from S3
            delete_objects = [{'Key': key} for key in s3_keys]
            
            try:
                response = s3_client.delete_objects(
                    Bucket=PHOTO_BUCKET_NAME,
                    Delete={'Objects': delete_objects}
                )
                
                # Track successful deletions
                for deleted in response.get('Deleted', []):
                    result['s3_files_deleted'].append(deleted['Key'])
                
                # Track errors
                for error in response.get('Errors', []):
                    result['deletion_errors'].append({
                        'key': error['Key'],
                        'error': error['Message'],
                        'error_code': error['Code']
                    })
                
            except ClientError as e:
                result['deletion_errors'].append({
                    'operation': 's3_batch_delete',
                    'error': str(e)
                })
        
        # Delete from database
        photo.delete()
        result['photo_deleted'] = True
        
        print(f"Photo {photo_id} deleted successfully")
        
    except Photo.DoesNotExist:
        result['deletion_errors'].append({
            'operation': 'photo_lookup',
            'error': 'Photo not found'
        })
    except Exception as e:
        result['deletion_errors'].append({
            'operation': 'photo_delete',
            'error': str(e)
        })
    
    return result


def delete_entity_photos(entity_type: str, entity_id: str, photo_type: str = None) -> dict:
    """
    Delete all photos for an entity
    
    Args:
        entity_type: Type of entity ('user', 'org', etc.)
        entity_id: Entity identifier
        photo_type: Optional photo type filter
        
    Returns:
        Deletion results dict
    """
    result = {
        'photos_deleted': 0,
        's3_files_deleted': [],
        'deletion_errors': [],
        'photos_processed': []
    }
    
    try:
        # Get all photos for the entity
        photos = Photo.get_entity_photos(entity_type, entity_id, photo_type)
        
        if not photos:
            print(f"No photos found for {entity_type} {entity_id}")
            return result
        
        print(f"Found {len(photos)} photos to delete for {entity_type} {entity_id}")
        
        # Collect all S3 keys to delete
        all_s3_keys = []
        for photo in photos:
            s3_keys = photo.get_s3_keys()
            all_s3_keys.extend(s3_keys)
            result['photos_processed'].append({
                'photo_id': photo.photo_id,
                'photo_type': photo.photo_type,
                's3_keys': s3_keys
            })
        
        # Batch delete from S3
        if all_s3_keys:
            delete_objects = [{'Key': key} for key in all_s3_keys]
            
            try:
                response = s3_client.delete_objects(
                    Bucket=PHOTO_BUCKET_NAME,
                    Delete={'Objects': delete_objects}
                )
                
                # Track successful deletions
                for deleted in response.get('Deleted', []):
                    result['s3_files_deleted'].append(deleted['Key'])
                
                # Track errors
                for error in response.get('Errors', []):
                    result['deletion_errors'].append({
                        'key': error['Key'],
                        'error': error['Message'],
                        'error_code': error['Code']
                    })
                
            except ClientError as e:
                result['deletion_errors'].append({
                    'operation': 's3_batch_delete',
                    'error': str(e)
                })
        
        # Delete photos from database
        for photo in photos:
            try:
                photo.delete()
                result['photos_deleted'] += 1
                print(f"Deleted photo: {photo.photo_id}")
            except Exception as e:
                result['deletion_errors'].append({
                    'operation': 'database_delete',
                    'photo_id': photo.photo_id,
                    'error': str(e)
                })
        
        print(f"Entity photo deletion completed: {result['photos_deleted']} photos deleted")
        
    except Exception as e:
        result['deletion_errors'].append({
            'operation': 'entity_photo_delete',
            'error': str(e)
        })
    
    return result


def lambda_handler(event, context):
    """
    Photo deletion handler
    
    Supports two modes:
    1. Delete specific photo by ID: {"photo_id": "photo_123"}
    2. Delete all entity photos: {"entity_type": "user", "entity_id": "john", "photo_type": "profile"}
    """
    try:
        print(f"Photo deletion request received")
        
        # Parse request body
        if not event.get('body'):
            return create_error_response(
                400,
                'No request body provided',
                event
            )
        
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return create_error_response(
                400,
                'Invalid JSON in request body',
                event
            )
        
        # Determine deletion mode
        photo_id = body.get('photo_id')
        entity_type = body.get('entity_type')
        entity_id = body.get('entity_id')
        photo_type = body.get('photo_type')
        
        if photo_id:
            # Mode 1: Delete specific photo by ID
            print(f"Deleting photo by ID: {photo_id}")
            result = delete_photo_by_id(photo_id)
            
            if not result['photo_deleted'] and result['deletion_errors']:
                error_msg = result['deletion_errors'][0].get('error', 'Unknown error')
                return create_error_response(
                    404 if 'not found' in error_msg.lower() else 500,
                    f'Failed to delete photo: {error_msg}',
                    event,
                    {'photo_id': photo_id, 'errors': result['deletion_errors']}
                )
            
            response_data = {
                'message': 'Photo deleted successfully',
                'photo_id': photo_id,
                'photo_info': result['photo_info'],
                's3_files_deleted': len(result['s3_files_deleted']),
                'deleted_files': result['s3_files_deleted'],
                'errors': result['deletion_errors'] if result['deletion_errors'] else None
            }
            
        elif entity_type and entity_id:
            # Mode 2: Delete entity photos
            print(f"Deleting entity photos: {entity_type}/{entity_id}/{photo_type or 'all'}")
            
            result = delete_entity_photos(entity_type, entity_id, photo_type)
            
            if result['photos_deleted'] == 0 and not result['deletion_errors']:
                return create_error_response(
                    404,
                    'No photos found for the specified entity',
                    event,
                    {'entity_type': entity_type, 'entity_id': entity_id, 'photo_type': photo_type}
                )
            
            response_data = {
                'message': f'Entity photos deleted successfully',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'photo_type': photo_type,
                'photos_deleted': result['photos_deleted'],
                's3_files_deleted': len(result['s3_files_deleted']),
                'deleted_files': result['s3_files_deleted'],
                'photos_processed': result['photos_processed'],
                'errors': result['deletion_errors'] if result['deletion_errors'] else None
            }
            
        else:
            return create_error_response(
                400,
                'Must provide either photo_id or entity_type+entity_id',
                event,
                {'usage': 'POST with {"photo_id": "id"} or {"entity_type": "user", "entity_id": "nickname"}'}
            )
        
        print(f"Photo deletion completed successfully")
        
        return create_response(
            200,
            json.dumps(response_data),
            event,
            ['POST', 'DELETE']
        )
        
    except Exception as e:
        print(f"Unexpected error in photo deletion: {str(e)}")
        return create_error_response(
            500,
            'Internal server error',
            event,
            {'details': str(e)}
        )