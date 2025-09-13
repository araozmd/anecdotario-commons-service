"""
Photo service with complete upload/delete/refresh operations
Handles photo processing, S3 storage, and database operations
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from ..constants import ImageConstants
from ..validation_utils import generate_photo_id, parse_base64_image
from ..config import config
from ..logger import photo_logger as logger
from ..error_handler import error_handler
from ..processors.image import image_processor
from ..models.photo import Photo
from ..utils import (
    generate_s3_key, upload_to_s3, delete_s3_objects, 
    generate_presigned_url, generate_public_url
)


class PhotoService:
    """
    Comprehensive photo service for all entity types
    Handles upload, processing, storage, and cleanup
    """
    
    def __init__(self):
        self.bucket_name = config.photo_bucket_name
        self.image_processor = image_processor
    
    def upload_photo(
        self,
        image_data: str,
        entity_type: str,
        entity_id: str,
        photo_type: str,
        uploaded_by: str = None,
        upload_source: str = None,
        cleanup_old: bool = True
    ) -> Dict[str, Any]:
        """
        Complete photo upload workflow
        
        Args:
            image_data: Base64 encoded image data
            entity_type: Type of entity (user, org, campaign)
            entity_id: Entity identifier
            photo_type: Photo type (profile, logo, banner, gallery)
            uploaded_by: User ID who uploaded the photo
            upload_source: Source service (user-service, org-service, etc.)
            cleanup_old: Whether to clean up old photos of same type
            
        Returns:
            Upload result with URLs and metadata
        """
        logger.log_service_operation(
            "photo_upload",
            entity_type=entity_type,
            entity_id=entity_id,
            photo_type=photo_type,
            upload_source=upload_source
        )
        
        try:
            # Generate photo ID
            photo_id = generate_photo_id()
            
            # Parse and validate image data
            image_bytes = parse_base64_image(image_data)
            logger.info("Image data parsed", 
                       photo_id=photo_id,
                       image_size=len(image_bytes))
            
            # Process image into multiple versions
            processing_result = self.image_processor.process_image(image_bytes)
            logger.info("Image processing completed", 
                       photo_id=photo_id,
                       versions=list(processing_result['versions'].keys()))
            
            # Upload all versions to S3
            upload_results = self._upload_versions_to_s3(
                processing_result['versions'],
                entity_type,
                entity_id, 
                photo_type,
                photo_id
            )
            
            # Generate URLs
            urls = self._generate_photo_urls(upload_results)
            
            # Create database record
            photo_record = self._create_photo_record(
                photo_id=photo_id,
                entity_type=entity_type,
                entity_id=entity_id,
                photo_type=photo_type,
                s3_keys=upload_results['s3_keys'],
                urls=urls,
                processing_result=processing_result,
                uploaded_by=uploaded_by,
                upload_source=upload_source
            )
            
            # Clean up old photos if requested
            cleanup_result = {}
            if cleanup_old:
                cleanup_result = self._cleanup_old_photos(
                    entity_type, entity_id, photo_type, keep_count=1
                )
            
            result = {
                'photo_id': photo_id,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'photo_type': photo_type,
                'urls': urls,
                'metadata': {
                    'original_size': processing_result['original_info']['file_size'],
                    'processed_sizes': {
                        version: stats['file_size'] 
                        for version, stats in processing_result['processing_stats'].items()
                    },
                    'processing_stats': processing_result['processing_stats'],
                    'total_reduction': processing_result.get('total_reduction', '0%')
                },
                'cleanup_result': cleanup_result,
                'created_at': photo_record.created_at.isoformat()
            }
            
            logger.log_service_operation(
                "photo_upload_success",
                entity_type=entity_type,
                entity_id=entity_id,
                photo_id=photo_id,
                versions_uploaded=len(upload_results['s3_keys']),
                cleanup_count=cleanup_result.get('deleted_count', 0)
            )
            
            return result
            
        except Exception as e:
            logger.error("Photo upload failed", 
                        error=e,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        photo_type=photo_type)
            raise
    
    def delete_photo(
        self,
        photo_id: str = None,
        entity_type: str = None,
        entity_id: str = None,
        photo_type: str = None
    ) -> Dict[str, Any]:
        """
        Delete photo(s) - supports single photo by ID or all photos by entity/type
        
        Args:
            photo_id: Specific photo ID to delete
            entity_type: Entity type (for bulk deletion)
            entity_id: Entity ID (for bulk deletion)
            photo_type: Photo type filter (for bulk deletion)
            
        Returns:
            Deletion result
        """
        logger.log_service_operation(
            "photo_delete",
            photo_id=photo_id,
            entity_type=entity_type,
            entity_id=entity_id,
            photo_type=photo_type
        )
        
        try:
            photos_to_delete = []
            
            if photo_id:
                # Single photo deletion
                photo = Photo.get_photo(photo_id)
                if photo:
                    photos_to_delete.append(photo)
                else:
                    raise ValueError(f"Photo with ID '{photo_id}' not found")
            
            elif entity_type and entity_id:
                # Bulk deletion by entity
                photos_to_delete = Photo.get_entity_photos(
                    entity_type, entity_id, photo_type
                )
                if not photos_to_delete:
                    logger.info("No photos found to delete", 
                               entity_type=entity_type,
                               entity_id=entity_id,
                               photo_type=photo_type)
                    return {
                        'success': True,
                        'deleted_count': 0,
                        'deleted_photos': [],
                        'message': 'No photos found to delete'
                    }
            
            else:
                raise ValueError("Must provide either photo_id or entity_type/entity_id")
            
            # Delete photos
            deletion_results = []
            s3_keys_to_delete = []
            
            for photo in photos_to_delete:
                # Collect S3 keys
                photo_s3_keys = [
                    photo.thumbnail_key,
                    photo.standard_key,
                    photo.high_res_key
                ]
                s3_keys_to_delete.extend([key for key in photo_s3_keys if key])
                
                # Delete database record
                try:
                    photo.delete_photo()
                    deletion_results.append({
                        'photo_id': photo.photo_id,
                        'success': True
                    })
                except Exception as e:
                    deletion_results.append({
                        'photo_id': photo.photo_id,
                        'success': False,
                        'error': str(e)
                    })
                    logger.error("Failed to delete photo record", 
                               error=e,
                               photo_id=photo.photo_id)
            
            # Delete S3 objects in batch
            s3_deletion_result = delete_s3_objects(self.bucket_name, s3_keys_to_delete)
            
            # Summary
            successful_deletions = [r for r in deletion_results if r['success']]
            failed_deletions = [r for r in deletion_results if not r['success']]
            
            result = {
                'success': len(failed_deletions) == 0,
                'deleted_count': len(successful_deletions),
                'failed_count': len(failed_deletions),
                'deleted_photos': [r['photo_id'] for r in successful_deletions],
                'failed_photos': [r['photo_id'] for r in failed_deletions],
                's3_cleanup': s3_deletion_result
            }
            
            logger.log_service_operation(
                "photo_delete_complete",
                deleted_count=len(successful_deletions),
                failed_count=len(failed_deletions),
                s3_deleted=s3_deletion_result.get('deleted_count', 0)
            )
            
            return result
            
        except Exception as e:
            logger.error("Photo deletion failed", 
                        error=e,
                        photo_id=photo_id,
                        entity_type=entity_type,
                        entity_id=entity_id)
            raise
    
    def refresh_photo_urls(
        self,
        photo_id: str = None,
        entity_type: str = None,
        entity_id: str = None,
        photo_type: str = None,
        expiry_seconds: int = None
    ) -> Dict[str, Any]:
        """
        Refresh presigned URLs for photos
        
        Args:
            photo_id: Specific photo ID
            entity_type: Entity type (for bulk refresh)
            entity_id: Entity ID (for bulk refresh)
            photo_type: Photo type filter
            expiry_seconds: URL expiry in seconds
            
        Returns:
            Refreshed URLs
        """
        logger.log_service_operation(
            "photo_url_refresh",
            photo_id=photo_id,
            entity_type=entity_type,
            entity_id=entity_id,
            photo_type=photo_type
        )
        
        try:
            photos = []
            
            if photo_id:
                # Single photo refresh
                photo = Photo.get_photo(photo_id)
                if photo:
                    photos.append(photo)
                else:
                    raise ValueError(f"Photo with ID '{photo_id}' not found")
            
            elif entity_type and entity_id:
                # Bulk refresh by entity
                photos = Photo.get_entity_photos(entity_type, entity_id, photo_type)
                if not photos:
                    return {
                        'success': True,
                        'refreshed_count': 0,
                        'photos': [],
                        'message': 'No photos found to refresh'
                    }
            
            else:
                raise ValueError("Must provide either photo_id or entity_type/entity_id")
            
            # Refresh URLs for each photo
            refreshed_photos = []
            expiry = expiry_seconds or config.presigned_url_expiry
            
            for photo in photos:
                urls = {
                    'thumbnail_url': photo.thumbnail_url,  # Already public
                    'standard_url': None,
                    'high_res_url': None
                }
                
                # Generate new presigned URLs
                if photo.standard_key:
                    urls['standard_url'] = generate_presigned_url(
                        photo.bucket_name, photo.standard_key, expiry
                    )
                
                if photo.high_res_key:
                    urls['high_res_url'] = generate_presigned_url(
                        photo.bucket_name, photo.high_res_key, expiry
                    )
                
                refreshed_photos.append({
                    'photo_id': photo.photo_id,
                    'entity_type': photo.entity_type,
                    'entity_id': photo.entity_id,
                    'photo_type': photo.photo_type,
                    'urls': urls,
                    'expires_at': datetime.now(timezone.utc).timestamp() + expiry
                })
            
            result = {
                'success': True,
                'refreshed_count': len(refreshed_photos),
                'photos': refreshed_photos,
                'expiry_seconds': expiry
            }
            
            logger.log_service_operation(
                "photo_url_refresh_complete",
                refreshed_count=len(refreshed_photos),
                expiry_seconds=expiry
            )
            
            return result
            
        except Exception as e:
            logger.error("Photo URL refresh failed", 
                        error=e,
                        photo_id=photo_id,
                        entity_type=entity_type,
                        entity_id=entity_id)
            raise
    
    def get_photo_info(self, photo_id: str) -> Dict[str, Any]:
        """
        Get comprehensive photo information
        
        Args:
            photo_id: Photo identifier
            
        Returns:
            Photo information with URLs
        """
        try:
            photo = Photo.get_photo(photo_id)
            if not photo:
                raise ValueError(f"Photo with ID '{photo_id}' not found")
            
            return photo.to_dict(include_presigned_urls=True)
            
        except Exception as e:
            logger.error("Failed to get photo info", error=e, photo_id=photo_id)
            raise
    
    def _upload_versions_to_s3(
        self,
        versions: Dict[str, bytes],
        entity_type: str,
        entity_id: str,
        photo_type: str,
        photo_id: str
    ) -> Dict[str, Any]:
        """
        Upload all image versions to S3
        
        Args:
            versions: Dictionary of version_name -> image_bytes
            entity_type: Entity type
            entity_id: Entity ID
            photo_type: Photo type
            photo_id: Photo ID
            
        Returns:
            Upload results with S3 keys
        """
        upload_results = {
            's3_keys': {},
            'upload_success': {},
            'upload_errors': []
        }
        
        for version_name, image_bytes in versions.items():
            try:
                # Generate S3 key
                s3_key = generate_s3_key(
                    entity_type, entity_id, photo_type, version_name
                )
                
                # Upload to S3
                upload_success = upload_to_s3(
                    self.bucket_name, s3_key, image_bytes, 'image/jpeg'
                )
                
                if upload_success:
                    upload_results['s3_keys'][version_name] = s3_key
                    upload_results['upload_success'][version_name] = True
                    
                    logger.log_s3_operation(
                        self.bucket_name, f"upload_{version_name}",
                        s3_key, True,
                        size=len(image_bytes)
                    )
                else:
                    upload_results['upload_success'][version_name] = False
                    upload_results['upload_errors'].append({
                        'version': version_name,
                        'error': 'Upload failed'
                    })
                    
                    logger.log_s3_operation(
                        self.bucket_name, f"upload_{version_name}",
                        s3_key, False
                    )
            
            except Exception as e:
                upload_results['upload_success'][version_name] = False
                upload_results['upload_errors'].append({
                    'version': version_name,
                    'error': str(e)
                })
                
                logger.error("Failed to upload version", 
                           error=e,
                           version=version_name,
                           photo_id=photo_id)
        
        # Check if all uploads succeeded
        if upload_results['upload_errors']:
            failed_versions = [e['version'] for e in upload_results['upload_errors']]
            raise Exception(f"Failed to upload versions: {failed_versions}")
        
        return upload_results
    
    def _generate_photo_urls(self, upload_results: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate URLs for uploaded photos
        
        Args:
            upload_results: Results from S3 upload
            
        Returns:
            Dictionary of URLs
        """
        urls = {}
        s3_keys = upload_results['s3_keys']
        
        # Thumbnail URL (public)
        if 'thumbnail' in s3_keys:
            urls['thumbnail_url'] = generate_public_url(
                self.bucket_name, s3_keys['thumbnail']
            )
        
        # Protected URLs (presigned)
        if 'standard' in s3_keys:
            urls['standard_url'] = generate_presigned_url(
                self.bucket_name, s3_keys['standard']
            )
        
        if 'high_res' in s3_keys:
            urls['high_res_url'] = generate_presigned_url(
                self.bucket_name, s3_keys['high_res']
            )
        
        return urls
    
    def _create_photo_record(
        self,
        photo_id: str,
        entity_type: str,
        entity_id: str,
        photo_type: str,
        s3_keys: Dict[str, str],
        urls: Dict[str, str],
        processing_result: Dict[str, Any],
        uploaded_by: str = None,
        upload_source: str = None
    ) -> Photo:
        """
        Create photo database record
        
        Args:
            photo_id: Photo ID
            entity_type: Entity type
            entity_id: Entity ID
            photo_type: Photo type
            s3_keys: S3 keys for each version
            urls: Generated URLs
            processing_result: Image processing results
            uploaded_by: User who uploaded
            upload_source: Source service
            
        Returns:
            Created Photo instance
        """
        photo_data = {
            'photo_id': photo_id,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'photo_type': photo_type,
            'bucket_name': self.bucket_name,
            'thumbnail_key': s3_keys.get('thumbnail'),
            'standard_key': s3_keys.get('standard'),
            'high_res_key': s3_keys.get('high_res'),
            'thumbnail_url': urls.get('thumbnail_url'),
            'file_size': processing_result['original_info']['file_size'],
            'processed_sizes': {
                version: stats['file_size']
                for version, stats in processing_result['processing_stats'].items()
            },
            'image_format': processing_result['original_info']['format'],
            'image_dimensions': {
                'width': processing_result['original_info']['size'][0],
                'height': processing_result['original_info']['size'][1]
            },
            'processing_stats': processing_result['processing_stats'],
            'uploaded_by': uploaded_by,
            'upload_source': upload_source
        }
        
        return Photo.create_photo(photo_data)
    
    def _cleanup_old_photos(
        self,
        entity_type: str,
        entity_id: str,
        photo_type: str,
        keep_count: int = 1
    ) -> Dict[str, Any]:
        """
        Clean up old photos, keeping only the most recent
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            photo_type: Photo type
            keep_count: Number of photos to keep
            
        Returns:
            Cleanup results
        """
        try:
            # Get all photos for cleanup
            old_photos = Photo.get_entity_photos(
                entity_type, entity_id, photo_type, limit=100
            )
            
            # Sort by creation date (newest first) and skip the ones to keep
            old_photos.sort(key=lambda p: p.created_at, reverse=True)
            photos_to_delete = old_photos[keep_count:]
            
            if not photos_to_delete:
                return {
                    'deleted_count': 0,
                    'deleted_photos': [],
                    's3_cleanup': {'deleted_count': 0, 'failed_count': 0}
                }
            
            # Collect S3 keys and delete photos
            s3_keys_to_delete = []
            deleted_photo_ids = []
            
            for photo in photos_to_delete:
                try:
                    # Collect S3 keys
                    photo_s3_keys = [
                        photo.thumbnail_key,
                        photo.standard_key,
                        photo.high_res_key
                    ]
                    s3_keys_to_delete.extend([key for key in photo_s3_keys if key])
                    
                    # Delete database record
                    photo.delete_photo()
                    deleted_photo_ids.append(photo.photo_id)
                    
                except Exception as e:
                    logger.error("Failed to cleanup old photo", 
                               error=e,
                               photo_id=photo.photo_id)
            
            # Delete S3 objects
            s3_cleanup_result = delete_s3_objects(self.bucket_name, s3_keys_to_delete)
            
            result = {
                'deleted_count': len(deleted_photo_ids),
                'deleted_photos': deleted_photo_ids,
                's3_cleanup': s3_cleanup_result
            }
            
            if deleted_photo_ids:
                logger.info("Old photos cleaned up", 
                           entity_type=entity_type,
                           entity_id=entity_id,
                           photo_type=photo_type,
                           deleted_count=len(deleted_photo_ids))
            
            return result
            
        except Exception as e:
            logger.error("Photo cleanup failed", 
                        error=e,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        photo_type=photo_type)
            return {
                'deleted_count': 0,
                'deleted_photos': [],
                's3_cleanup': {'deleted_count': 0, 'failed_count': 0},
                'error': str(e)
            }


# Global photo service instance
photo_service = PhotoService()