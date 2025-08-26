"""
Photo metadata model for tracking uploaded photos
"""
import os
from datetime import datetime
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute, NumberAttribute
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection


class EntityTypeIndex(GlobalSecondaryIndex):
    """
    Global secondary index for querying photos by entity type
    Allows finding all photos for users, orgs, etc.
    """
    class Meta:
        index_name = 'entity-type-index'
        projection = AllProjection()
    
    entity_type = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class EntityPhotosIndex(GlobalSecondaryIndex):
    """
    Global secondary index for querying photos by entity
    Allows finding all photos for a specific user/org/campaign
    """
    class Meta:
        index_name = 'entity-photos-index'
        projection = AllProjection()
    
    entity_key = UnicodeAttribute(hash_key=True)  # Format: "{entity_type}#{entity_id}"
    created_at = UTCDateTimeAttribute(range_key=True)


class Photo(Model):
    """
    Photo metadata model for tracking uploaded photos across all entity types
    
    This centralized model allows tracking photos for users, orgs, campaigns, etc.
    while maintaining consistency and enabling cross-entity photo operations.
    """
    class Meta:
        table_name = os.environ.get('PHOTO_TABLE_NAME', 'Photos-dev')
        region = os.environ.get('AWS_REGION', 'us-east-1')
        billing_mode = 'PAY_PER_REQUEST'
    
    # Primary key - unique photo ID
    photo_id = UnicodeAttribute(hash_key=True)
    
    # Entity information
    entity_type = UnicodeAttribute()  # 'user', 'org', 'campaign', etc.
    entity_id = UnicodeAttribute()    # nickname, org_id, campaign_id, etc.
    entity_key = UnicodeAttribute()   # Composite key: "{entity_type}#{entity_id}"
    photo_type = UnicodeAttribute()   # 'profile', 'logo', 'banner', 'gallery', etc.
    
    # S3 storage information
    bucket_name = UnicodeAttribute()
    thumbnail_key = UnicodeAttribute(null=True)    # Public thumbnail S3 key
    standard_key = UnicodeAttribute(null=True)     # Standard resolution S3 key
    high_res_key = UnicodeAttribute(null=True)     # High resolution S3 key
    
    # URLs (thumbnail is public, others are presigned)
    thumbnail_url = UnicodeAttribute(null=True)    # Public URL
    
    # Image metadata
    original_size = NumberAttribute(null=True)     # Original file size in bytes
    optimized_size = NumberAttribute(null=True)    # Total optimized size (all versions)
    versions_count = NumberAttribute(default=0)    # Number of versions created
    
    # Upload information
    uploaded_by = UnicodeAttribute(null=True)      # User who uploaded (for audit)
    upload_source = UnicodeAttribute(null=True)    # 'user-service', 'org-service', etc.
    
    # Timestamps
    created_at = UTCDateTimeAttribute(default=datetime.utcnow)
    updated_at = UTCDateTimeAttribute(default=datetime.utcnow)
    
    # Global secondary indexes
    entity_type_index = EntityTypeIndex()
    entity_photos_index = EntityPhotosIndex()
    
    def save(self, **kwargs):
        """Override save to update timestamps and composite keys"""
        self.updated_at = datetime.utcnow()
        
        # Ensure composite key is set
        if self.entity_type and self.entity_id:
            self.entity_key = f"{self.entity_type}#{self.entity_id}"
        
        super().save(**kwargs)
    
    @classmethod
    def get_entity_photos(cls, entity_type: str, entity_id: str, photo_type: str = None):
        """
        Get all photos for a specific entity
        
        Args:
            entity_type: Type of entity ('user', 'org', etc.)
            entity_id: Entity identifier (nickname, org_id, etc.)
            photo_type: Optional photo type filter
            
        Returns:
            List of Photo objects
        """
        entity_key = f"{entity_type}#{entity_id}"
        
        try:
            photos = list(cls.entity_photos_index.query(entity_key))
            
            if photo_type:
                photos = [p for p in photos if p.photo_type == photo_type]
                
            return photos
        except Exception:
            return []
    
    @classmethod
    def get_current_photo(cls, entity_type: str, entity_id: str, photo_type: str):
        """
        Get the current (most recent) photo for an entity
        
        Args:
            entity_type: Type of entity ('user', 'org', etc.)
            entity_id: Entity identifier
            photo_type: Photo type ('profile', 'logo', etc.)
            
        Returns:
            Most recent Photo object or None
        """
        photos = cls.get_entity_photos(entity_type, entity_id, photo_type)
        if photos:
            # Sort by created_at descending and return most recent
            photos.sort(key=lambda p: p.created_at, reverse=True)
            return photos[0]
        return None
    
    def generate_presigned_urls(self, s3_client, expires_in: int = 604800):
        """
        Generate presigned URLs for protected image versions
        
        Args:
            s3_client: boto3 S3 client
            expires_in: URL expiration time in seconds (default: 7 days)
            
        Returns:
            Dict with presigned URLs
        """
        urls = {}
        
        if self.thumbnail_url:
            # Thumbnail is already public
            urls['thumbnail'] = self.thumbnail_url
        
        # Generate presigned URLs for protected versions
        for version, key in [('standard', self.standard_key), ('high_res', self.high_res_key)]:
            if key:
                try:
                    urls[version] = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.bucket_name, 'Key': key},
                        ExpiresIn=expires_in
                    )
                except Exception:
                    # Silently fail if can't generate URL
                    pass
        
        return urls
    
    def to_dict(self, s3_client=None, include_presigned_urls: bool = False):
        """
        Convert photo model to dictionary for API responses
        
        Args:
            s3_client: boto3 S3 client (required for presigned URLs)
            include_presigned_urls: Whether to generate presigned URLs
            
        Returns:
            Dictionary representation
        """
        data = {
            'photo_id': self.photo_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'photo_type': self.photo_type,
            'bucket_name': self.bucket_name,
            'versions_count': self.versions_count,
            'original_size': self.original_size,
            'optimized_size': self.optimized_size,
            'uploaded_by': self.uploaded_by,
            'upload_source': self.upload_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Add URLs
        if include_presigned_urls and s3_client:
            data['images'] = self.generate_presigned_urls(s3_client)
        else:
            # Only include public thumbnail
            data['images'] = {
                'thumbnail': self.thumbnail_url
            } if self.thumbnail_url else {}
        
        return data
    
    def get_s3_keys(self):
        """Get all S3 keys for this photo (for cleanup operations)"""
        keys = []
        for key in [self.thumbnail_key, self.standard_key, self.high_res_key]:
            if key:
                keys.append(key)
        return keys