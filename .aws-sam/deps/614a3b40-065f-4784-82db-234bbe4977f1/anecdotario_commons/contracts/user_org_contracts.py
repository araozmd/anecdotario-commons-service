"""
User-Organization Service Contracts
Function signatures for Lambda invocation from other services
"""
from typing import Dict, Any, Optional, List


class UserOrgContracts:
    """Contract definitions for user-org Lambda functions"""
    
    @staticmethod
    def create_entity(
        nickname: str,
        full_name: str, 
        user_type: str,  # 'user' or 'organization'
        avatar_thumbnail_url: Optional[str] = None,
        is_certified: bool = False,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        created_by: Optional[str] = None,
        upload_source: str = 'api'
    ) -> Dict[str, Any]:
        """
        Create new user or organization entity
        
        Lambda: anecdotario-user-org-create-{env}
        
        Returns: Created entity data with metadata
        Raises: ValidationError, DuplicateEntityError
        """
        pass
    
    @staticmethod
    def get_entity(
        nickname: Optional[str] = None,
        user_type: Optional[str] = None,  # 'user' or 'organization'
        search: Optional[str] = None,
        certified: Optional[bool] = None,
        limit: int = 20,
        last_evaluated_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get entity or list entities with flexible querying
        
        Lambda: anecdotario-user-org-get-{env}
        
        Query modes:
        - Single entity: provide nickname
        - List by type: provide user_type
        - Search: provide search term
        - Certified: provide certified=True
        """
        pass
    
    @staticmethod
    def update_entity(
        nickname: str,
        full_name: Optional[str] = None,
        avatar_thumbnail_url: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        certification: Optional[Dict[str, Any]] = None,  # {'is_certified': bool, 'certified_by': str}
        stats_update: Optional[Dict[str, int]] = None     # {'followers_delta': int, 'posts_delta': int}
    ) -> Dict[str, Any]:
        """
        Update entity data (nickname and user_type are immutable)
        
        Lambda: anecdotario-user-org-update-{env}
        
        Returns: Updated entity data
        """
        pass
    
    @staticmethod
    def delete_entity(
        nickname: str,
        hard_delete: bool = False  # False = soft delete (set inactive)
    ) -> Dict[str, Any]:
        """
        Delete entity (soft or hard delete)
        
        Lambda: anecdotario-user-org-delete-{env}
        
        Returns: Deletion confirmation
        """
        pass