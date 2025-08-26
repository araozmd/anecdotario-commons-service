"""
Photo Upload Lambda Function
Entity-agnostic photo upload service for users, orgs, campaigns, etc.
"""
import json
import os
import sys
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from config import config
from models.photo import Photo
from processors.image import image_processor
from utils import (
    create_response, create_error_response, generate_photo_id,
    generate_s3_key, generate_public_url, parse_image_data,
    validate_entity_request, calculate_size_reduction
)

# Initialize AWS clients
s3_client = boto3.client('s3')

# Load configuration
PHOTO_BUCKET_NAME = config.get_ssm_parameter('photo-bucket-name', os.environ.get('PHOTO_BUCKET_NAME'))
MAX_IMAGE_SIZE = config.get_int_parameter('max-image-size', 5242880)  # 5MB default
S3_CACHE_CONTROL = config.get_parameter('s3-cache-control', 'max-age=31536000')


def cleanup_entity_photos(entity_type: str, entity_id: str, photo_type: str, bucket_name: str) -> dict:
    """
    Clean up existing photos for an entity before uploading new ones
    
    Args:
        entity_type: Type of entity ('user', 'org', etc.)
        entity_id: Entity identifier
        photo_type: Photo type ('profile', 'logo', etc.)
        bucket_name: S3 bucket name
        
    Returns:
        Cleanup results dict
    """
    cleanup_result = {
        'deleted_files': [],
        'deletion_errors': [],
        'photos_removed': 0
    }
    
    if not bucket_name:
        return cleanup_result
    
    try:
        # Get existing photos from database
        existing_photos = Photo.get_entity_photos(entity_type, entity_id, photo_type)
        
        if not existing_photos:
            print(f"No existing {photo_type} photos for {entity_type} {entity_id}")
            return cleanup_result
        
        print(f"Found {len(existing_photos)} existing photos to clean up")
        
        # Collect all S3 keys to delete
        keys_to_delete = []
        photos_to_delete = []
        
        for photo in existing_photos:
            s3_keys = photo.get_s3_keys()
            keys_to_delete.extend(s3_keys)
            photos_to_delete.append(photo)
        
        # Batch delete from S3
        if keys_to_delete:
            delete_objects = [{'Key': key} for key in keys_to_delete]
            
            try:
                response = s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': delete_objects}
                )
                
                # Track successful deletions
                for deleted in response.get('Deleted', []):
                    cleanup_result['deleted_files'].append(deleted['Key'])
                
                # Track errors
                for error in response.get('Errors', []):
                    cleanup_result['deletion_errors'].append({
                        'key': error['Key'],
                        'error': error['Message'],
                        'error_code': error['Code']
                    })
                
                print(f"Deleted {len(cleanup_result['deleted_files'])} files from S3")
                
            except ClientError as e:
                print(f"S3 batch delete failed: {str(e)}")
                cleanup_result['deletion_errors'].append({
                    'operation': 's3_batch_delete',
                    'error': str(e)
                })
        
        # Delete photo records from database
        for photo in photos_to_delete:
            try:
                photo.delete()
                cleanup_result['photos_removed'] += 1
                print(f"Deleted photo record: {photo.photo_id}")
            except Exception as e:
                print(f"Failed to delete photo record {photo.photo_id}: {str(e)}")
                cleanup_result['deletion_errors'].append({
                    'operation': 'database_delete',
                    'photo_id': photo.photo_id,
                    'error': str(e)
                })
        
        print(f"Cleanup completed: {cleanup_result['photos_removed']} photos removed")
        
    except Exception as e:
        print(f"Unexpected error during cleanup: {str(e)}")
        cleanup_result['deletion_errors'].append({
            'operation': 'cleanup',
            'error': str(e)
        })
    
    return cleanup_result


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
        print(f"Photo upload request received for {event.get('httpMethod', 'INVOKE')} method")
        
        # Parse request body
        if not event.get('body'):
            return create_error_response(
                400,
                'No request body provided',
                event
            )
        
        # Parse image data and metadata
        try:
            image_bytes, metadata = parse_image_data(
                event['body'], 
                event.get('isBase64Encoded', False)
            )
        except ValueError as e:
            return create_error_response(400, str(e), event)
        
        # Validate metadata
        error_message = validate_entity_request(metadata)
        if error_message:
            return create_error_response(400, error_message, event)
        
        entity_type = metadata['entity_type']
        entity_id = metadata['entity_id']
        photo_type = metadata.get('photo_type', 'profile')
        uploaded_by = metadata.get('uploaded_by')
        upload_source = metadata.get('upload_source', 'unknown')
        
        print(f"Processing photo upload: {entity_type}/{entity_id}/{photo_type}")
        
        # Check file size
        if len(image_bytes) > MAX_IMAGE_SIZE:
            return create_error_response(
                400,
                'Image too large',
                event,
                {'max_size_mb': MAX_IMAGE_SIZE / 1024 / 1024}
            )
        
        # Validate image
        is_valid, validation_error = image_processor.validate_image(image_bytes)
        if not is_valid:
            return create_error_response(
                400,
                f'Invalid image: {validation_error}',
                event
            )
        
        # Clean up existing photos BEFORE uploading new ones
        cleanup_result = cleanup_entity_photos(entity_type, entity_id, photo_type, PHOTO_BUCKET_NAME)
        
        # Process image into multiple versions
        try:
            image_versions = image_processor.create_image_versions(image_bytes)
            print(f"Created {len(image_versions)} image versions")
        except ValueError as e:
            return create_error_response(
                400,
                f'Failed to process image: {str(e)}',
                event
            )
        
        # Generate unique photo ID and S3 keys
        photo_id = generate_photo_id()
        s3_keys = {}
        image_urls = {}
        
        print(f"Uploading to S3 with photo ID: {photo_id}")
        
        # Upload all versions to S3
        try:
            for version, image_data in image_versions.items():
                s3_key = generate_s3_key(entity_type, entity_id, photo_type, version, photo_id)
                s3_keys[version] = s3_key
                
                print(f"Uploading {version}: {s3_key} ({len(image_data)} bytes)")
                
                # Upload to S3
                s3_client.put_object(
                    Bucket=PHOTO_BUCKET_NAME,
                    Key=s3_key,
                    Body=image_data,
                    ContentType='image/jpeg',
                    CacheControl=S3_CACHE_CONTROL,
                    Metadata={
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'photo_type': photo_type,
                        'version': version,
                        'photo_id': photo_id,
                        'uploaded_by': uploaded_by or 'unknown',
                        'upload_source': upload_source,
                        'upload_timestamp': datetime.utcnow().isoformat(),
                        'original_size': str(len(image_bytes)),
                        'optimized_size': str(len(image_data))
                    }
                )
                
                # Generate URLs
                if version == 'thumbnail':
                    # Thumbnail is publicly accessible
                    image_urls[version] = generate_public_url(PHOTO_BUCKET_NAME, s3_key)
                else:
                    # Standard and high_res require presigned URLs
                    image_urls[version] = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': PHOTO_BUCKET_NAME, 'Key': s3_key},
                        ExpiresIn=604800  # 7 days
                    )
            
            print(f"All {len(image_versions)} versions uploaded successfully")
            
        except ClientError as e:
            return create_error_response(
                500,
                'Failed to upload image to S3',
                event,
                {'details': str(e)}
            )
        
        # Save photo metadata to database
        total_optimized_size = sum(len(data) for data in image_versions.values())
        
        try:
            photo = Photo(
                photo_id=photo_id,
                entity_type=entity_type,
                entity_id=entity_id,
                photo_type=photo_type,
                bucket_name=PHOTO_BUCKET_NAME,
                thumbnail_key=s3_keys.get('thumbnail'),
                standard_key=s3_keys.get('standard'),
                high_res_key=s3_keys.get('high_res'),
                thumbnail_url=image_urls.get('thumbnail'),
                original_size=len(image_bytes),
                optimized_size=total_optimized_size,
                versions_count=len(image_versions),
                uploaded_by=uploaded_by,
                upload_source=upload_source
            )
            photo.save()
            
            print(f"Photo metadata saved to database: {photo_id}")
            
        except Exception as e:
            print(f"Failed to save photo metadata: {str(e)}")
            # Don't fail the request, but log the error
            # The images are already uploaded to S3
        
        # Calculate size reduction
        size_reduction = calculate_size_reduction(len(image_bytes), total_optimized_size)
        
        # Return success response
        response_data = {
            'message': 'Photo uploaded successfully',
            'photo_id': photo_id,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'photo_type': photo_type,
            'images': image_urls,
            'versions_created': len(image_versions),
            'size_reduction': size_reduction,
            'original_size': len(image_bytes),
            'optimized_size': total_optimized_size,
            'cleanup': {
                'photos_removed': cleanup_result['photos_removed'],
                'files_deleted': len(cleanup_result['deleted_files']),
                'errors': len(cleanup_result['deletion_errors'])
            }
        }
        
        print(f"Photo upload completed successfully: {photo_id}")
        
        return create_response(
            200,
            json.dumps(response_data),
            event,
            ['POST']
        )
        
    except Exception as e:
        print(f"Unexpected error in photo upload: {str(e)}")
        return create_error_response(
            500,
            'Internal server error',
            event,
            {'details': str(e)}
        )