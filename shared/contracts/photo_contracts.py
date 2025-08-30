"""
Photo Service Contracts
Function signatures for photo operations from other services
"""
from typing import Dict, Any, Optional


class PhotoContracts:
    """Contract definitions for photo Lambda functions"""
    
    @staticmethod
    def upload_photo(
        image: str,  # Base64 encoded image data
        entity_type: str,  # 'user', 'org', 'campaign'
        entity_id: str,    # Entity nickname/identifier
        photo_type: str,   # 'profile', 'logo', 'banner', 'gallery'
        uploaded_by: Optional[str] = None,
        upload_source: str = 'api'
    ) -> Dict[str, Any]:
        """
        Upload and process photo for any entity type
        
        Lambda: anecdotario-photo-upload-{env}
        
        Returns: 
        {
            'photo_id': str,
            'thumbnail_url': str (public),
            'standard_url': str (presigned),
            'high_res_url': str (presigned),
            'versions': {...}
        }
        """
        pass
    
    @staticmethod
    def delete_photo(
        entity_type: str,  # 'user', 'org', 'campaign'
        entity_id: str,    # Entity nickname/identifier
        photo_type: str,   # 'profile', 'logo', 'banner', 'gallery'
        photo_id: Optional[str] = None  # Delete specific photo, or all photos of type
    ) -> Dict[str, Any]:
        """
        Delete photos for entity
        
        Lambda: anecdotario-photo-delete-{env}
        
        Returns: Deletion confirmation with cleanup details
        """
        pass
    
    @staticmethod
    def refresh_photo_urls(
        entity_type: str,  # 'user', 'org', 'campaign' 
        entity_id: str,    # Entity nickname/identifier
        photo_type: str,   # 'profile', 'logo', 'banner', 'gallery'
        expiry_hours: int = 168  # Default 7 days
    ) -> Dict[str, Any]:
        """
        Generate fresh presigned URLs for existing photos
        
        Lambda: anecdotario-photo-refresh-{env}
        
        Returns: Updated URLs with new expiry times
        """
        pass