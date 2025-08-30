"""
Photo service layer - Business logic for photo operations
Provides clean separation of concerns and dependency injection
"""
import json
import boto3
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from botocore.exceptions import ClientError

from ..config import config
from ..models.photo import Photo
from ..processors.image import image_processor
from ..utils import generate_photo_id, generate_s3_key, generate_public_url, calculate_size_reduction
from ..exceptions import ValidationError, ImageProcessingError, StorageError
from ..logger import get_logger


class PhotoService:
    """
    Photo service handling all photo-related business logic
    Supports dependency injection for testability
    """
    
    def __init__(self, s3_client=None, config_manager=None):
        """
        Initialize photo service with optional dependency injection
        
        Args:
            s3_client: Optional S3 client for testing
            config_manager: Optional config manager for testing
        """
        self.s3_client = s3_client or boto3.client('s3')
        self.config = config_manager or config
        self.logger = get_logger(__name__)
        
        # Load configuration
        self.bucket_name = self.config.get_ssm_parameter(
            'photo-bucket-name', 
            self.config.get_env('PHOTO_BUCKET_NAME')
        )
        self.max_image_size = self.config.get_int_parameter('max-image-size', 5242880)  # 5MB
        self.cache_control = self.config.get_parameter('s3-cache-control', 'max-age=31536000')
    
    def upload_photo(self, 
                    image_data: str, 
                    entity_type: str, 
                    entity_id: str, 
                    photo_type: str, 
                    uploaded_by: Optional[str] = None,
                    upload_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload photo with all processing and cleanup
        
        Args:
            image_data: Base64 encoded image data
            entity_type: Type of entity (user, org, campaign)
            entity_id: Entity identifier
            photo_type: Photo type (profile, logo, banner, gallery)
            uploaded_by: User ID who uploaded the photo
            upload_source: Source service name
            
        Returns:
            Upload result with photo_id, URLs, and metadata
            
        Raises:
            ValidationError: Invalid input data
            ImageProcessingError: Image processing failed
            StorageError: S3 or database operation failed
        """
        # Decode and validate image
        try:
            image_bytes = self._decode_image_data(image_data)
        except ValueError as e:
            raise ValidationError(f"Invalid image data: {str(e)}")
        
        # Check file size
        if len(image_bytes) > self.max_image_size:
            raise ValidationError(
                f"Image too large: {len(image_bytes)} bytes (max: {self.max_image_size})",
                {'max_size_mb': self.max_image_size / 1024 / 1024}
            )
        
        # Validate image format
        is_valid, validation_error = image_processor.validate_image(image_bytes)
        if not is_valid:
            raise ValidationError(f"Invalid image format: {validation_error}")
        
        # Clean up existing photos before upload
        with self.logger.operation_timer('photo_cleanup', entity_type=entity_type, entity_id=entity_id):
            cleanup_result = self.cleanup_entity_photos(entity_type, entity_id, photo_type)
        
        # Process image into multiple versions
        with self.logger.operation_timer('image_processing', 
                                        original_size=len(image_bytes),
                                        entity_type=entity_type):
            try:
                image_versions = image_processor.create_image_versions(image_bytes)
                # Log processing metrics
                total_optimized_size = sum(len(data) for data in image_versions.values())
                self.logger.log_performance_metric('image_size_reduction', 
                                                 len(image_bytes) - total_optimized_size,
                                                 'bytes')
                self.logger.log_performance_metric('image_versions_created', 
                                                 len(image_versions),
                                                 'count')
            except Exception as e:
                raise ImageProcessingError(f"Failed to process image: {str(e)}")
        
        # Generate photo metadata
        photo_id = generate_photo_id()
        s3_keys = {}
        image_urls = {}
        
        # Upload all versions to S3
        with self.logger.operation_timer('s3_upload', 
                                        entity_type=entity_type,
                                        photo_id=photo_id,
                                        versions_count=len(image_versions)):
            try:
                for version, processed_data in image_versions.items():
                    s3_key = generate_s3_key(entity_type, entity_id, photo_type, version, photo_id)
                    s3_keys[version] = s3_key
                
                    # Upload to S3
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        Body=processed_data,
                        ContentType='image/jpeg',
                        CacheControl=self.cache_control,
                        Metadata={
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'photo_type': photo_type,
                            'version': version,
                            'photo_id': photo_id,
                            'uploaded_by': uploaded_by or 'unknown',
                            'upload_source': upload_source or 'unknown',
                            'upload_timestamp': datetime.utcnow().isoformat(),
                            'original_size': str(len(image_bytes)),
                            'optimized_size': str(len(processed_data))
                        }
                    )
                
                    # Generate appropriate URL for each version
                    image_urls[version] = self._generate_image_url(version, s3_key)
                
            except ClientError as e:
                raise StorageError(f"Failed to upload to S3: {str(e)}")
        
        # Save photo metadata to database
        total_optimized_size = sum(len(data) for data in image_versions.values())
        
        try:
            photo = Photo(
                photo_id=photo_id,
                entity_type=entity_type,
                entity_id=entity_id,
                photo_type=photo_type,
                bucket_name=self.bucket_name,
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
            
        except Exception as e:
            # Don't fail the request since S3 upload succeeded
            # But log the database error
            self.logger.warning(f"Failed to save photo metadata: {str(e)}", 
                              photo_id=photo_id, 
                              entity_type=entity_type)
        
        # Log successful business event
        self.logger.log_business_event('photo_uploaded', 
                                     entity_type=entity_type,
                                     entity_id=entity_id,
                                     photo_type=photo_type,
                                     photo_id=photo_id,
                                     original_size=len(image_bytes),
                                     optimized_size=total_optimized_size,
                                     versions_count=len(image_versions))
        
        # Prepare response
        size_reduction = calculate_size_reduction(len(image_bytes), total_optimized_size)
        
        return {
            'photo_id': photo_id,
            'urls': image_urls,
            'metadata': {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'photo_type': photo_type,
                'versions_created': len(image_versions),
                'size_reduction': size_reduction,
                'original_size': len(image_bytes),
                'optimized_size': total_optimized_size
            },
            'cleanup_result': cleanup_result
        }
    
    def delete_photo_by_id(self, photo_id: str) -> Dict[str, Any]:
        """
        Delete photo by ID
        
        Args:
            photo_id: Photo identifier to delete
            
        Returns:
            Deletion result
            
        Raises:
            ValidationError: Photo not found
            StorageError: Deletion failed
        """
        try:
            photo = Photo.get(photo_id)
        except Photo.DoesNotExist:
            raise ValidationError(f"Photo not found: {photo_id}")
        
        # Delete from S3
        s3_keys = photo.get_s3_keys()
        deletion_result = self._delete_s3_objects(s3_keys)
        
        # Delete from database
        try:
            photo.delete()
        except Exception as e:
            raise StorageError(f"Failed to delete photo record: {str(e)}")
        
        return {
            'photo_id': photo_id,
            'deleted_files': deletion_result['deleted_files'],
            'deletion_errors': deletion_result['errors']
        }
    
    def delete_entity_photos(self, entity_type: str, entity_id: str, photo_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete all photos for an entity
        
        Args:
            entity_type: Type of entity (user, org, campaign)
            entity_id: Entity identifier
            photo_type: Optional photo type filter
            
        Returns:
            Deletion result summary
            
        Raises:
            StorageError: Deletion operation failed
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
                return result
            
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
                deletion_result = self._delete_s3_objects(all_s3_keys)
                result['s3_files_deleted'] = deletion_result['deleted_files']
                result['deletion_errors'].extend(deletion_result['errors'])
            
            # Delete photos from database
            for photo in photos:
                try:
                    photo.delete()
                    result['photos_deleted'] += 1
                except Exception as e:
                    result['deletion_errors'].append({
                        'operation': 'database_delete',
                        'photo_id': photo.photo_id,
                        'error': str(e)
                    })
            
        except Exception as e:
            result['deletion_errors'].append({
                'operation': 'entity_photo_delete',
                'error': str(e)
            })
        
        return result
    
    def refresh_photo_urls(self, photo_id: str) -> Dict[str, Any]:
        """
        Refresh presigned URLs for a photo
        
        Args:
            photo_id: Photo identifier
            
        Returns:
            New URLs for the photo
            
        Raises:
            ValidationError: Photo not found
        """
        try:
            photo = Photo.get(photo_id)
        except Photo.DoesNotExist:
            raise ValidationError(f"Photo not found: {photo_id}")
        
        urls = {}
        
        # Generate new URLs for each version
        if photo.thumbnail_key:
            urls['thumbnail'] = self._generate_image_url('thumbnail', photo.thumbnail_key)
        
        if photo.standard_key:
            urls['standard'] = self._generate_image_url('standard', photo.standard_key)
        
        if photo.high_res_key:
            urls['high_res'] = self._generate_image_url('high_res', photo.high_res_key)
        
        return {
            'photo_id': photo_id,
            'urls': urls,
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def refresh_entity_photo_urls(self, entity_type: str, entity_id: str, photo_type: Optional[str] = None, expires_in: Optional[int] = None) -> Dict[str, Any]:
        """
        Refresh presigned URLs for all photos of an entity
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            photo_type: Optional photo type filter
            expires_in: URL expiration time in seconds
            
        Returns:
            Refresh results for all photos
            
        Raises:
            ValidationError: Invalid parameters
        """
        if expires_in is None:
            expires_in = 604800  # 7 days default
        
        result = {
            'photos_found': 0,
            'photos_refreshed': [],
            'errors': []
        }
        
        try:
            # Get all photos for the entity
            photos = Photo.get_entity_photos(entity_type, entity_id, photo_type)
            result['photos_found'] = len(photos)
            
            if not photos:
                return result
            
            # Refresh URLs for each photo
            for photo in photos:
                try:
                    urls = self._generate_all_urls_for_photo(photo, expires_in)
                    result['photos_refreshed'].append({
                        'photo_id': photo.photo_id,
                        'photo_type': photo.photo_type,
                        'urls': urls,
                        'expires_in': expires_in
                    })
                    
                except Exception as e:
                    result['errors'].append({
                        'operation': 'photo_url_refresh',
                        'photo_id': photo.photo_id,
                        'error': str(e)
                    })
            
        except Exception as e:
            result['errors'].append({
                'operation': 'entity_url_refresh',
                'error': str(e)
            })
        
        return result
    
    def get_current_entity_photo(self, entity_type: str, entity_id: str, photo_type: str, expires_in: Optional[int] = None) -> Dict[str, Any]:
        """
        Get the current (most recent) photo for an entity with fresh URLs
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            photo_type: Photo type
            expires_in: URL expiration time in seconds
            
        Returns:
            Current photo info with URLs
            
        Raises:
            ValidationError: Photo not found
        """
        if expires_in is None:
            expires_in = 604800  # 7 days default
        
        try:
            # Get current photo
            photo = Photo.get_current_photo(entity_type, entity_id, photo_type)
            
            if not photo:
                raise ValidationError(f"No {photo_type} photo found for {entity_type} {entity_id}")
            
            # Generate fresh presigned URLs
            urls = self._generate_all_urls_for_photo(photo, expires_in)
            
            return {
                'photo_found': True,
                'photo_info': photo.to_dict(),
                'urls': urls,
                'expires_in': expires_in,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Failed to get current photo: {str(e)}")
    
    def _generate_all_urls_for_photo(self, photo: Photo, expires_in: int) -> Dict[str, str]:
        """
        Generate URLs for all versions of a photo
        
        Args:
            photo: Photo model instance
            expires_in: URL expiration time in seconds
            
        Returns:
            Dictionary of version -> URL mappings
        """
        urls = {}
        
        # Generate URL for each version that exists
        if photo.thumbnail_key:
            urls['thumbnail'] = self._generate_image_url('thumbnail', photo.thumbnail_key)
        
        if photo.standard_key:
            urls['standard'] = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': photo.standard_key},
                ExpiresIn=expires_in
            )
        
        if photo.high_res_key:
            urls['high_res'] = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': photo.high_res_key},
                ExpiresIn=expires_in
            )
        
        return urls
    
    def cleanup_entity_photos(self, entity_type: str, entity_id: str, photo_type: str) -> Dict[str, Any]:
        """
        Clean up existing photos for an entity before uploading new ones
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            photo_type: Photo type to clean up
            
        Returns:
            Cleanup result summary
        """
        cleanup_result = {
            'deleted_files': [],
            'deletion_errors': [],
            'photos_removed': 0
        }
        
        if not self.bucket_name:
            return cleanup_result
        
        try:
            # Get existing photos from database
            existing_photos = Photo.get_entity_photos(entity_type, entity_id, photo_type)
            
            if not existing_photos:
                return cleanup_result
            
            # Collect all S3 keys to delete
            keys_to_delete = []
            photos_to_delete = []
            
            for photo in existing_photos:
                s3_keys = photo.get_s3_keys()
                keys_to_delete.extend(s3_keys)
                photos_to_delete.append(photo)
            
            # Batch delete from S3
            if keys_to_delete:
                deletion_result = self._delete_s3_objects(keys_to_delete)
                cleanup_result['deleted_files'] = deletion_result['deleted_files']
                cleanup_result['deletion_errors'].extend(deletion_result['errors'])
            
            # Delete photo records from database
            for photo in photos_to_delete:
                try:
                    photo.delete()
                    cleanup_result['photos_removed'] += 1
                except Exception as e:
                    cleanup_result['deletion_errors'].append({
                        'operation': 'database_delete',
                        'photo_id': photo.photo_id,
                        'error': str(e)
                    })
            
        except Exception as e:
            cleanup_result['deletion_errors'].append({
                'operation': 'cleanup',
                'error': str(e)
            })
        
        return cleanup_result
    
    def _decode_image_data(self, image_data: str) -> bytes:
        """
        Decode base64 image data
        
        Args:
            image_data: Base64 encoded image with or without data URL prefix
            
        Returns:
            Decoded image bytes
            
        Raises:
            ValueError: Invalid base64 data
        """
        import base64
        
        # Remove data URL prefix if present (data:image/jpeg;base64,...)
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        try:
            return base64.b64decode(image_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 image data: {str(e)}")
    
    def _generate_image_url(self, version: str, s3_key: str) -> str:
        """
        Generate appropriate URL for image version
        
        Args:
            version: Image version (thumbnail, standard, high_res)
            s3_key: S3 object key
            
        Returns:
            Public URL for thumbnails, presigned URL for others
        """
        if version == 'thumbnail':
            # Thumbnail is publicly accessible
            return generate_public_url(self.bucket_name, s3_key)
        else:
            # Standard and high_res require presigned URLs
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=604800  # 7 days
            )
    
    def _delete_s3_objects(self, keys: List[str]) -> Dict[str, Any]:
        """
        Delete multiple objects from S3
        
        Args:
            keys: List of S3 object keys to delete
            
        Returns:
            Deletion result with successful deletions and errors
        """
        result = {
            'deleted_files': [],
            'errors': []
        }
        
        if not keys:
            return result
        
        try:
            delete_objects = [{'Key': key} for key in keys]
            
            response = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': delete_objects}
            )
            
            # Track successful deletions
            for deleted in response.get('Deleted', []):
                result['deleted_files'].append(deleted['Key'])
            
            # Track errors
            for error in response.get('Errors', []):
                result['errors'].append({
                    'key': error['Key'],
                    'error': error['Message'],
                    'error_code': error['Code']
                })
                
        except ClientError as e:
            result['errors'].append({
                'operation': 's3_batch_delete',
                'error': str(e)
            })
        
        return result