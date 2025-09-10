"""
User-Organization Service
Business logic for managing users and organizations in unified table
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from ..models.user_org import UserOrg
from ..config import config
from ..logger import logger
from ..exceptions import ValidationError, DuplicateEntityError, EntityNotFoundError
from ..constants import EntityConstants


class UserOrgService:
    """
    Service for managing user and organization entities
    """
    
    def __init__(self):
        """Initialize the service with configuration"""
        self.config = config
    
    def create_entity(
        self,
        nickname: str,
        full_name: str,
        user_type: str,
        avatar_thumbnail_url: Optional[str] = None,
        is_certified: bool = False,
        created_by: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user or organization entity
        
        Args:
            nickname: Unique nickname/identifier
            full_name: Display name
            user_type: 'user' or 'organization'
            avatar_thumbnail_url: Optional avatar URL
            is_certified: Whether entity is certified
            created_by: Who created this entity
            email: Email address (optional)
            phone: Phone number (optional)
            website: Website URL (optional)
            
        Returns:
            Dict containing created entity data
            
        Raises:
            ValidationError: If validation fails
            DuplicateEntityError: If nickname already exists
        """
        # Validate input
        self._validate_create_input(nickname, full_name, user_type)
        
        # Check if nickname already exists
        if self._nickname_exists(nickname):
            raise DuplicateEntityError(f"Nickname '{nickname}' already exists")
        
        # Create entity
        current_time = datetime.now(timezone.utc).isoformat()
        
        entity = UserOrg(
            nickname=nickname,
            full_name=full_name,
            user_type=user_type,
            avatar_thumbnail_url=avatar_thumbnail_url,
            is_certified='yes' if is_certified else 'no',
            created_at=current_time,
            updated_at=current_time,
            created_by=created_by,
            email=email,
            phone=phone,
            website=website,
            is_active=True,
            version=1
        )
        
        try:
            entity.save()
            logger.info(f"Created {user_type}: {nickname}")
            
            return self._entity_to_dict(entity)
            
        except Exception as e:
            logger.error(f"Failed to create {user_type} {nickname}", error=e)
            if "ConditionalCheckFailedException" in str(e):
                raise DuplicateEntityError(f"Nickname '{nickname}' already exists")
            raise
    
    def get_entity(
        self,
        nickname: str,
        include_inactive: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get entity by nickname
        
        Args:
            nickname: Entity nickname
            include_inactive: Whether to include inactive entities
            
        Returns:
            Entity data or None if not found
        """
        try:
            entity = UserOrg.get(nickname)
            
            # Check if entity is active (unless explicitly including inactive)
            if not include_inactive and not entity.is_active:
                return None
            
            return self._entity_to_dict(entity)
            
        except UserOrg.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to get entity {nickname}", error=e)
            raise
    
    def update_entity(
        self,
        nickname: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update entity fields
        
        Args:
            nickname: Entity nickname
            updates: Fields to update
            updated_by: Who is making the update
            
        Returns:
            Updated entity data
            
        Raises:
            EntityNotFoundError: If entity doesn't exist
            ValidationError: If validation fails
        """
        try:
            entity = UserOrg.get(nickname)
        except UserOrg.DoesNotExist:
            raise EntityNotFoundError(f"Entity '{nickname}' not found")
        
        # Validate updates
        self._validate_update_input(updates)
        
        # Apply updates
        for field, value in updates.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        
        # Update metadata
        entity.updated_at = datetime.now(timezone.utc).isoformat()
        if updated_by:
            entity.updated_by = updated_by
        entity.version += 1
        
        try:
            entity.save()
            logger.info(f"Updated entity: {nickname}")
            
            return self._entity_to_dict(entity)
            
        except Exception as e:
            logger.error(f"Failed to update entity {nickname}", error=e)
            raise
    
    def delete_entity(
        self,
        nickname: str,
        soft_delete: bool = True,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete entity (soft or hard delete)
        
        Args:
            nickname: Entity nickname
            soft_delete: Whether to soft delete (default) or hard delete
            deleted_by: Who is deleting the entity
            
        Returns:
            Result of deletion operation
            
        Raises:
            EntityNotFoundError: If entity doesn't exist
        """
        try:
            entity = UserOrg.get(nickname)
        except UserOrg.DoesNotExist:
            raise EntityNotFoundError(f"Entity '{nickname}' not found")
        
        if soft_delete:
            # Soft delete - mark as inactive
            entity.is_active = False
            entity.deleted_at = datetime.now(timezone.utc).isoformat()
            if deleted_by:
                entity.deleted_by = deleted_by
            entity.version += 1
            
            entity.save()
            logger.info(f"Soft deleted entity: {nickname}")
            
            return {
                'success': True,
                'operation': 'soft_delete',
                'nickname': nickname,
                'deleted_at': entity.deleted_at
            }
        else:
            # Hard delete - remove from database
            entity.delete()
            logger.info(f"Hard deleted entity: {nickname}")
            
            return {
                'success': True,
                'operation': 'hard_delete',
                'nickname': nickname,
                'deleted_at': datetime.now(timezone.utc).isoformat()
            }
    
    def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        certified_only: bool = False,
        limit: int = 20,
        last_evaluated_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search entities by nickname or full name
        
        Args:
            query: Search query string
            entity_type: Filter by entity type ('user' or 'organization')
            certified_only: Whether to return only certified entities
            limit: Maximum number of results
            last_evaluated_key: Pagination key
            
        Returns:
            Search results with pagination info
        """
        results = []
        
        try:
            # Search by entity type if specified
            if entity_type:
                index = UserOrg.user_type_index
                scan_kwargs = {
                    'limit': limit,
                    'filter_condition': None
                }
                
                # Add pagination
                if last_evaluated_key:
                    scan_kwargs['last_evaluated_key'] = last_evaluated_key
                
                # Build filter conditions
                filter_conditions = []
                
                # Add query filter (search in nickname and full_name)
                if query:
                    filter_conditions.append(
                        UserOrg.nickname.contains(query) | 
                        UserOrg.full_name.contains(query)
                    )
                
                # Add certified filter
                if certified_only:
                    filter_conditions.append(UserOrg.is_certified == 'yes')
                
                # Add active filter
                filter_conditions.append(UserOrg.is_active == True)
                
                # Combine all filters
                if filter_conditions:
                    combined_filter = filter_conditions[0]
                    for condition in filter_conditions[1:]:
                        combined_filter = combined_filter & condition
                    scan_kwargs['filter_condition'] = combined_filter
                
                # Execute query
                scan_result = index.query(
                    entity_type,
                    **scan_kwargs
                )
                
                results = [self._entity_to_dict(entity) for entity in scan_result]
                
            else:
                # Scan all entities
                scan_kwargs = {
                    'limit': limit,
                    'filter_condition': None
                }
                
                # Add pagination
                if last_evaluated_key:
                    scan_kwargs['last_evaluated_key'] = last_evaluated_key
                
                # Build filter conditions
                filter_conditions = []
                
                # Add query filter
                if query:
                    filter_conditions.append(
                        UserOrg.nickname.contains(query) | 
                        UserOrg.full_name.contains(query)
                    )
                
                # Add certified filter
                if certified_only:
                    filter_conditions.append(UserOrg.is_certified == 'yes')
                
                # Add active filter
                filter_conditions.append(UserOrg.is_active == True)
                
                # Combine all filters
                if filter_conditions:
                    combined_filter = filter_conditions[0]
                    for condition in filter_conditions[1:]:
                        combined_filter = combined_filter & condition
                    scan_kwargs['filter_condition'] = combined_filter
                
                # Execute scan
                scan_result = UserOrg.scan(**scan_kwargs)
                results = [self._entity_to_dict(entity) for entity in scan_result]
            
            return {
                'results': results,
                'count': len(results),
                'query': query,
                'entity_type': entity_type,
                'certified_only': certified_only,
                'last_evaluated_key': getattr(scan_result, 'last_evaluated_key', None)
            }
            
        except Exception as e:
            logger.error(f"Failed to search entities with query: {query}", error=e)
            raise
    
    def _validate_create_input(self, nickname: str, full_name: str, user_type: str):
        """Validate input for entity creation"""
        if not nickname or not nickname.strip():
            raise ValidationError("Nickname is required")
        
        if not full_name or not full_name.strip():
            raise ValidationError("Full name is required")
        
        if user_type not in ['user', 'organization']:
            raise ValidationError("user_type must be 'user' or 'organization'")
        
        # Validate nickname format
        nickname = nickname.strip().lower()
        if len(nickname) < 3:
            raise ValidationError("Nickname must be at least 3 characters long")
        
        if len(nickname) > 30:
            raise ValidationError("Nickname must be no more than 30 characters long")
        
        # Check for valid characters (alphanumeric and underscores)
        if not nickname.replace('_', '').isalnum():
            raise ValidationError("Nickname can only contain letters, numbers, and underscores")
    
    def _validate_update_input(self, updates: Dict[str, Any]):
        """Validate input for entity updates"""
        # List of fields that can be updated
        updatable_fields = {
            'full_name', 'avatar_thumbnail_url', 'is_certified', 
            'email', 'phone', 'website', 'updated_by'
        }
        
        # Check for invalid fields
        invalid_fields = set(updates.keys()) - updatable_fields
        if invalid_fields:
            raise ValidationError(f"Cannot update fields: {', '.join(invalid_fields)}")
        
        # Validate specific fields
        if 'full_name' in updates:
            if not updates['full_name'] or not updates['full_name'].strip():
                raise ValidationError("Full name cannot be empty")
        
        if 'is_certified' in updates:
            if updates['is_certified'] not in ['yes', 'no', True, False]:
                raise ValidationError("is_certified must be 'yes', 'no', True, or False")
    
    def _nickname_exists(self, nickname: str) -> bool:
        """Check if nickname already exists"""
        try:
            UserOrg.get(nickname)
            return True
        except UserOrg.DoesNotExist:
            return False
    
    def _entity_to_dict(self, entity: UserOrg) -> Dict[str, Any]:
        """Convert entity to dictionary"""
        return {
            'nickname': entity.nickname,
            'full_name': entity.full_name,
            'user_type': entity.user_type,
            'avatar_thumbnail_url': entity.avatar_thumbnail_url,
            'is_certified': entity.is_certified == 'yes',
            'created_at': entity.created_at,
            'updated_at': entity.updated_at,
            'created_by': entity.created_by,
            'updated_by': getattr(entity, 'updated_by', None),
            'email': entity.email,
            'phone': entity.phone,
            'website': entity.website,
            'is_active': entity.is_active,
            'version': entity.version,
            'deleted_at': getattr(entity, 'deleted_at', None),
            'deleted_by': getattr(entity, 'deleted_by', None)
        }