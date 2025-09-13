"""
PynamoDB model for Photo entities
"""
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute, UTCDateTimeAttribute, JSONAttribute, 
    NumberAttribute, BooleanAttribute
)
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection
from pynamodb.exceptions import DoesNotExist, QueryError, PutError, UpdateError, DeleteError
from ..config import config
from ..logger import photo_logger as logger
from ..error_handler import error_handler


class EntityTypeIndex(GlobalSecondaryIndex):
    """GSI for querying photos by entity type"""
    class Meta:
        index_name = 'entity-type-index'
        projection = AllProjection()
    
    entity_type = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class EntityPhotosIndex(GlobalSecondaryIndex):
    """GSI for querying all photos for a specific entity"""
    class Meta:
        index_name = 'entity-photos-index' 
        projection = AllProjection()
    
    entity_key = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class Photo(Model):
    """
    Photo model for storing metadata about uploaded photos
    Supports users, orgs, campaigns, and other entity types
    """
    
    class Meta:
        table_name = config.photo_table_name
        region = 'us-east-1'
        billing_mode = 'PAY_PER_REQUEST'
    
    # Primary key
    photo_id = UnicodeAttribute(hash_key=True)
    
    # Entity identification
    entity_type = UnicodeAttribute()  # user, org, campaign
    entity_id = UnicodeAttribute()    # nickname, org_id, etc.
    entity_key = UnicodeAttribute()   # Composite: {entity_type}#{entity_id}
    
    # Photo metadata
    photo_type = UnicodeAttribute()   # profile, logo, banner, gallery
    bucket_name = UnicodeAttribute()
    
    # S3 keys for different versions
    thumbnail_key = UnicodeAttribute()
    standard_key = UnicodeAttribute() 
    high_res_key = UnicodeAttribute()
    
    # URLs (thumbnail public, others presigned)
    thumbnail_url = UnicodeAttribute()
    
    # File metadata
    original_filename = UnicodeAttribute(null=True)
    file_size = NumberAttribute()  # Original file size
    processed_sizes = JSONAttribute()  # Sizes of each version
    
    # Processing metadata  
    image_format = UnicodeAttribute()
    image_dimensions = JSONAttribute()  # {width: int, height: int}
    processing_stats = JSONAttribute(null=True)
    
    # Upload tracking
    uploaded_by = UnicodeAttribute(null=True)
    upload_source = UnicodeAttribute(null=True)  # user-service, org-service, etc.
    upload_ip = UnicodeAttribute(null=True)
    
    # Timestamps
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    
    # Status
    is_active = BooleanAttribute(default=True)
    
    # Global Secondary Indexes
    entity_type_index = EntityTypeIndex()
    entity_photos_index = EntityPhotosIndex()
    
    def save(self, **kwargs):
        """Override save to update timestamp"""
        self.updated_at = datetime.now(timezone.utc)
        return super().save(**kwargs)
    
    @classmethod
    def create_photo(cls, photo_data: Dict[str, Any]) -> 'Photo':
        """
        Create new photo record
        
        Args:
            photo_data: Dictionary containing photo information
            
        Returns:
            Created Photo instance
            
        Raises:
            ValueError: If required fields are missing
            Exception: If database operation fails
        """
        required_fields = ['photo_id', 'entity_type', 'entity_id', 'photo_type', 'bucket_name']
        missing_fields = [field for field in required_fields if field not in photo_data]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        try:
            # Create entity_key composite
            entity_key = f"{photo_data['entity_type']}#{photo_data['entity_id']}"
            
            photo = cls(
                photo_id=photo_data['photo_id'],
                entity_type=photo_data['entity_type'],
                entity_id=photo_data['entity_id'],
                entity_key=entity_key,
                photo_type=photo_data['photo_type'],
                bucket_name=photo_data['bucket_name'],
                thumbnail_key=photo_data.get('thumbnail_key'),
                standard_key=photo_data.get('standard_key'),
                high_res_key=photo_data.get('high_res_key'),
                thumbnail_url=photo_data.get('thumbnail_url'),
                original_filename=photo_data.get('original_filename'),
                file_size=photo_data.get('file_size', 0),
                processed_sizes=photo_data.get('processed_sizes', {}),
                image_format=photo_data.get('image_format'),
                image_dimensions=photo_data.get('image_dimensions', {}),
                processing_stats=photo_data.get('processing_stats'),
                uploaded_by=photo_data.get('uploaded_by'),
                upload_source=photo_data.get('upload_source'),
                upload_ip=photo_data.get('upload_ip'),
                is_active=photo_data.get('is_active', True)
            )
            
            photo.save()
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='create',
                success=True,
                photo_id=photo.photo_id,
                entity_type=photo.entity_type,
                entity_id=photo.entity_id
            )
            
            return photo
            
        except (PutError, Exception) as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='create',
                success=False,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'create_photo', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    @classmethod
    def get_photo(cls, photo_id: str) -> Optional['Photo']:
        """
        Get photo by ID
        
        Args:
            photo_id: Photo identifier
            
        Returns:
            Photo instance or None if not found
        """
        try:
            photo = cls.get(photo_id)
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='get',
                success=True,
                photo_id=photo_id
            )
            
            return photo
            
        except DoesNotExist:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='get',
                success=False,
                photo_id=photo_id,
                error='Photo not found'
            )
            return None
            
        except Exception as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='get',
                success=False,
                photo_id=photo_id,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'get_photo', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    @classmethod
    def get_entity_photos(cls, entity_type: str, entity_id: str, photo_type: str = None, limit: int = 50) -> List['Photo']:
        """
        Get all photos for an entity
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier  
            photo_type: Optional photo type filter
            limit: Maximum number of photos to return
            
        Returns:
            List of Photo instances
        """
        try:
            entity_key = f"{entity_type}#{entity_id}"
            
            query = cls.entity_photos_index.query(
                entity_key,
                limit=limit,
                scan_index_forward=False  # Most recent first
            )
            
            photos = list(query)
            
            # Filter by photo_type if specified
            if photo_type:
                photos = [p for p in photos if p.photo_type == photo_type]
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='query',
                success=True,
                entity_type=entity_type,
                entity_id=entity_id,
                count=len(photos)
            )
            
            return photos
            
        except (QueryError, Exception) as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='query',
                success=False,
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'get_entity_photos', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    @classmethod
    def get_current_photo(cls, entity_type: str, entity_id: str, photo_type: str) -> Optional['Photo']:
        """
        Get current active photo for entity and type
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            photo_type: Photo type (profile, logo, etc.)
            
        Returns:
            Most recent active photo or None
        """
        try:
            photos = cls.get_entity_photos(entity_type, entity_id, photo_type, limit=1)
            
            # Return first active photo
            for photo in photos:
                if photo.is_active:
                    return photo
            
            return None
            
        except Exception as e:
            logger.error("Failed to get current photo", 
                        error=e,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        photo_type=photo_type)
            raise
    
    def update_photo(self, updates: Dict[str, Any]) -> 'Photo':
        """
        Update photo attributes
        
        Args:
            updates: Dictionary of fields to update
            
        Returns:
            Updated Photo instance
        """
        try:
            for key, value in updates.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            self.save()
            
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='update',
                success=True,
                photo_id=self.photo_id,
                updates=list(updates.keys())
            )
            
            return self
            
        except (UpdateError, Exception) as e:
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='update',
                success=False,
                photo_id=self.photo_id,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'update_photo', self.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    def soft_delete(self) -> 'Photo':
        """
        Soft delete photo (mark as inactive)
        
        Returns:
            Updated Photo instance
        """
        return self.update_photo({'is_active': False})
    
    def delete_photo(self) -> bool:
        """
        Hard delete photo record
        
        Returns:
            True if successful
        """
        try:
            self.delete()
            
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='delete',
                success=True,
                photo_id=self.photo_id,
                entity_type=self.entity_type,
                entity_id=self.entity_id
            )
            
            return True
            
        except (DeleteError, Exception) as e:
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='delete',
                success=False,
                photo_id=self.photo_id,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'delete_photo', self.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    def to_dict(self, include_presigned_urls: bool = False, presigned_expiry: int = None) -> Dict[str, Any]:
        """
        Convert photo to dictionary representation
        
        Args:
            include_presigned_urls: Whether to generate presigned URLs
            presigned_expiry: Presigned URL expiry in seconds
            
        Returns:
            Dictionary representation
        """
        from ..utils import generate_presigned_url
        
        data = {
            'photo_id': self.photo_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'photo_type': self.photo_type,
            'thumbnail_url': self.thumbnail_url,
            'file_size': self.file_size,
            'processed_sizes': self.processed_sizes,
            'image_format': self.image_format,
            'image_dimensions': self.image_dimensions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active
        }
        
        # Add presigned URLs if requested
        if include_presigned_urls:
            expiry = presigned_expiry or config.presigned_url_expiry
            
            data['standard_url'] = generate_presigned_url(
                self.bucket_name, self.standard_key, expiry
            ) if self.standard_key else None
            
            data['high_res_url'] = generate_presigned_url(
                self.bucket_name, self.high_res_key, expiry  
            ) if self.high_res_key else None
        
        # Optional fields
        if self.uploaded_by:
            data['uploaded_by'] = self.uploaded_by
        if self.upload_source:
            data['upload_source'] = self.upload_source
        if self.original_filename:
            data['original_filename'] = self.original_filename
        
        return data
    
    @classmethod
    def cleanup_old_photos(cls, entity_type: str, entity_id: str, photo_type: str, keep_count: int = 1) -> List[str]:
        """
        Clean up old photos, keeping only the most recent ones
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            photo_type: Photo type
            keep_count: Number of photos to keep
            
        Returns:
            List of deleted photo IDs
        """
        try:
            # Get all photos for this entity and type
            all_photos = cls.get_entity_photos(entity_type, entity_id, photo_type, limit=100)
            
            # Sort by creation date (newest first)
            all_photos.sort(key=lambda p: p.created_at, reverse=True)
            
            # Identify photos to delete
            photos_to_delete = all_photos[keep_count:]
            deleted_photo_ids = []
            
            for photo in photos_to_delete:
                try:
                    photo.delete_photo()
                    deleted_photo_ids.append(photo.photo_id)
                except Exception as e:
                    logger.error("Failed to delete old photo", 
                               error=e,
                               photo_id=photo.photo_id)
                    # Continue with other deletions
            
            if deleted_photo_ids:
                logger.info("Old photos cleaned up",
                           entity_type=entity_type,
                           entity_id=entity_id,
                           photo_type=photo_type,
                           deleted_count=len(deleted_photo_ids))
            
            return deleted_photo_ids
            
        except Exception as e:
            logger.error("Failed to cleanup old photos",
                        error=e,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        photo_type=photo_type)
            return []