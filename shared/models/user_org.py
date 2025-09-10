"""
PynamoDB model for User-Organization entities
Unified model for users and organizations with shared nickname space
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute, UTCDateTimeAttribute, JSONAttribute, 
    BooleanAttribute, NumberAttribute
)
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection
from pynamodb.exceptions import DoesNotExist, QueryError, PutError, UpdateError, DeleteError
from ..config import config
from ..logger import user_org_logger as logger
from ..error_handler import error_handler


class UserTypeIndex(GlobalSecondaryIndex):
    """GSI for querying entities by type (user/org)"""
    class Meta:
        index_name = 'user-type-index'
        projection = AllProjection()
    
    user_type = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class CertifiedIndex(GlobalSecondaryIndex):
    """GSI for querying certified entities"""
    class Meta:
        index_name = 'certified-index'
        projection = AllProjection()
    
    is_certified = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class UserOrg(Model):
    """
    Unified model for users and organizations
    Maintains global nickname uniqueness across both entity types
    """
    
    class Meta:
        table_name = config.user_org_table_name
        region = 'us-east-1'
        billing_mode = 'PAY_PER_REQUEST'
    
    # Primary key - nickname is globally unique
    nickname = UnicodeAttribute(hash_key=True)
    
    # Entity type and identification
    user_type = UnicodeAttribute()  # 'user' or 'org'
    entity_id = UnicodeAttribute()  # Internal ID (user_id, org_id)
    
    # Display information
    display_name = UnicodeAttribute()
    full_name = UnicodeAttribute(null=True)  # For users: first + last, For orgs: full org name
    bio = UnicodeAttribute(null=True)
    
    # Contact information
    email = UnicodeAttribute(null=True)
    phone = UnicodeAttribute(null=True)
    website = UnicodeAttribute(null=True)
    
    # Location
    location = UnicodeAttribute(null=True)
    country = UnicodeAttribute(null=True)
    timezone = UnicodeAttribute(null=True)
    
    # Photo URLs (from photo service)
    profile_photo_url = UnicodeAttribute(null=True)
    banner_photo_url = UnicodeAttribute(null=True)
    
    # Status and verification
    is_active = BooleanAttribute(default=True)
    is_verified = BooleanAttribute(default=False)
    is_certified = UnicodeAttribute(default='false')  # 'true' or 'false' for GSI
    verification_date = UTCDateTimeAttribute(null=True)
    
    # User-specific fields
    first_name = UnicodeAttribute(null=True)
    last_name = UnicodeAttribute(null=True)
    date_of_birth = UnicodeAttribute(null=True)  # ISO date string
    
    # Organization-specific fields
    org_type = UnicodeAttribute(null=True)  # company, nonprofit, government, etc.
    founded_date = UnicodeAttribute(null=True)  # ISO date string
    employee_count = NumberAttribute(null=True)
    industry = UnicodeAttribute(null=True)
    
    # Social media links
    social_links = JSONAttribute(default=dict)  # {platform: url}
    
    # Metadata
    tags = JSONAttribute(default=list)  # List of tags/keywords
    metadata = JSONAttribute(default=dict)  # Flexible additional data
    
    # Privacy settings
    privacy_settings = JSONAttribute(default=dict)
    
    # Statistics
    stats = JSONAttribute(default=dict)  # Follower counts, campaign counts, etc.
    
    # Timestamps
    created_at = UTCDateTimeAttribute(default=datetime.utcnow)
    updated_at = UTCDateTimeAttribute(default=datetime.utcnow)
    last_login = UTCDateTimeAttribute(null=True)
    
    # Admin fields
    created_by = UnicodeAttribute(null=True)  # Who created this entity
    admin_notes = UnicodeAttribute(null=True)
    
    # Global Secondary Indexes
    user_type_index = UserTypeIndex()
    certified_index = CertifiedIndex()
    
    def save(self, **kwargs):
        """Override save to update timestamp"""
        self.updated_at = datetime.utcnow()
        return super().save(**kwargs)
    
    @classmethod
    def create_entity(cls, entity_data: Dict[str, Any]) -> 'UserOrg':
        """
        Create new user or organization
        
        Args:
            entity_data: Dictionary containing entity information
            
        Returns:
            Created UserOrg instance
            
        Raises:
            ValueError: If required fields are missing or nickname exists
            Exception: If database operation fails
        """
        required_fields = ['nickname', 'user_type', 'entity_id', 'display_name']
        missing_fields = [field for field in required_fields if field not in entity_data]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Validate user_type
        if entity_data['user_type'] not in ['user', 'org']:
            raise ValueError("user_type must be 'user' or 'org'")
        
        # Check if nickname already exists
        if cls.nickname_exists(entity_data['nickname']):
            raise ValueError(f"Nickname '{entity_data['nickname']}' is already taken")
        
        try:
            entity = cls(
                nickname=entity_data['nickname'],
                user_type=entity_data['user_type'],
                entity_id=entity_data['entity_id'],
                display_name=entity_data['display_name'],
                full_name=entity_data.get('full_name'),
                bio=entity_data.get('bio'),
                email=entity_data.get('email'),
                phone=entity_data.get('phone'),
                website=entity_data.get('website'),
                location=entity_data.get('location'),
                country=entity_data.get('country'),
                timezone=entity_data.get('timezone'),
                profile_photo_url=entity_data.get('profile_photo_url'),
                banner_photo_url=entity_data.get('banner_photo_url'),
                is_verified=entity_data.get('is_verified', False),
                is_certified='true' if entity_data.get('is_certified', False) else 'false',
                # User-specific
                first_name=entity_data.get('first_name'),
                last_name=entity_data.get('last_name'),
                date_of_birth=entity_data.get('date_of_birth'),
                # Org-specific
                org_type=entity_data.get('org_type'),
                founded_date=entity_data.get('founded_date'),
                employee_count=entity_data.get('employee_count'),
                industry=entity_data.get('industry'),
                # Additional data
                social_links=entity_data.get('social_links', {}),
                tags=entity_data.get('tags', []),
                metadata=entity_data.get('metadata', {}),
                privacy_settings=entity_data.get('privacy_settings', {}),
                stats=entity_data.get('stats', {}),
                created_by=entity_data.get('created_by')
            )
            
            entity.save()
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='create',
                success=True,
                nickname=entity.nickname,
                user_type=entity.user_type,
                entity_id=entity.entity_id
            )
            
            return entity
            
        except (PutError, Exception) as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='create',
                success=False,
                nickname=entity_data.get('nickname'),
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'create_entity', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    @classmethod
    def get_by_nickname(cls, nickname: str) -> Optional['UserOrg']:
        """
        Get entity by nickname
        
        Args:
            nickname: Entity nickname
            
        Returns:
            UserOrg instance or None if not found
        """
        try:
            entity = cls.get(nickname)
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='get',
                success=True,
                nickname=nickname
            )
            
            return entity
            
        except DoesNotExist:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='get',
                success=False,
                nickname=nickname,
                error='Entity not found'
            )
            return None
            
        except Exception as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='get',
                success=False,
                nickname=nickname,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'get_by_nickname', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    @classmethod
    def nickname_exists(cls, nickname: str) -> bool:
        """
        Check if nickname exists
        
        Args:
            nickname: Nickname to check
            
        Returns:
            True if exists, False otherwise
        """
        return cls.get_by_nickname(nickname) is not None
    
    @classmethod
    def search_entities(
        cls, 
        query: str = None,
        user_type: str = None, 
        is_certified: bool = None,
        limit: int = 50
    ) -> List['UserOrg']:
        """
        Search entities with filters
        
        Args:
            query: Search query (matches nickname, display_name, full_name)
            user_type: Filter by 'user' or 'org'
            is_certified: Filter by certification status
            limit: Maximum number of results
            
        Returns:
            List of matching UserOrg instances
        """
        try:
            results = []
            
            if user_type:
                # Query by user_type index
                query_obj = cls.user_type_index.query(
                    user_type,
                    limit=limit,
                    scan_index_forward=False
                )
                results = list(query_obj)
            
            elif is_certified is not None:
                # Query by certified index
                certified_value = 'true' if is_certified else 'false'
                query_obj = cls.certified_index.query(
                    certified_value,
                    limit=limit,
                    scan_index_forward=False
                )
                results = list(query_obj)
            
            else:
                # Full table scan (limited)
                scan_obj = cls.scan(limit=limit)
                results = list(scan_obj)
            
            # Apply text search filter if query provided
            if query:
                query_lower = query.lower()
                results = [
                    entity for entity in results
                    if (query_lower in entity.nickname.lower() or
                        query_lower in entity.display_name.lower() or
                        (entity.full_name and query_lower in entity.full_name.lower()))
                ]
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='search',
                success=True,
                query=query,
                user_type=user_type,
                is_certified=is_certified,
                result_count=len(results)
            )
            
            return results
            
        except (QueryError, Exception) as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='search',
                success=False,
                query=query,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'search_entities', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    @classmethod 
    def get_by_type(cls, user_type: str, limit: int = 50) -> List['UserOrg']:
        """
        Get entities by type
        
        Args:
            user_type: 'user' or 'org'
            limit: Maximum number of results
            
        Returns:
            List of UserOrg instances
        """
        try:
            query_obj = cls.user_type_index.query(
                user_type,
                limit=limit,
                scan_index_forward=False  # Most recent first
            )
            
            results = list(query_obj)
            
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='query_by_type',
                success=True,
                user_type=user_type,
                result_count=len(results)
            )
            
            return results
            
        except (QueryError, Exception) as e:
            logger.log_database_operation(
                table_name=cls.Meta.table_name,
                operation='query_by_type',
                success=False,
                user_type=user_type,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'get_by_type', cls.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    def update_entity(self, updates: Dict[str, Any]) -> 'UserOrg':
        """
        Update entity attributes
        
        Args:
            updates: Dictionary of fields to update
            
        Returns:
            Updated UserOrg instance
        """
        try:
            # Special handling for is_certified (must be string for GSI)
            if 'is_certified' in updates:
                updates['is_certified'] = 'true' if updates['is_certified'] else 'false'
            
            for key, value in updates.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            self.save()
            
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='update',
                success=True,
                nickname=self.nickname,
                updates=list(updates.keys())
            )
            
            return self
            
        except (UpdateError, Exception) as e:
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='update',
                success=False,
                nickname=self.nickname,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'update_entity', self.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    def soft_delete(self) -> 'UserOrg':
        """
        Soft delete entity (mark as inactive)
        
        Returns:
            Updated UserOrg instance
        """
        return self.update_entity({'is_active': False})
    
    def delete_entity(self) -> bool:
        """
        Hard delete entity record
        
        Returns:
            True if successful
        """
        try:
            self.delete()
            
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='delete',
                success=True,
                nickname=self.nickname,
                user_type=self.user_type
            )
            
            return True
            
        except (DeleteError, Exception) as e:
            logger.log_database_operation(
                table_name=self.Meta.table_name,
                operation='delete',
                success=False,
                nickname=self.nickname,
                error=str(e)
            )
            
            error_response = error_handler.handle_dynamodb_error(e, 'delete_entity', self.Meta.table_name)
            raise Exception(error_response['error_message'])
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert entity to dictionary representation
        
        Args:
            include_sensitive: Whether to include sensitive data (email, phone)
            
        Returns:
            Dictionary representation
        """
        data = {
            'nickname': self.nickname,
            'user_type': self.user_type,
            'entity_id': self.entity_id,
            'display_name': self.display_name,
            'full_name': self.full_name,
            'bio': self.bio,
            'location': self.location,
            'country': self.country,
            'website': self.website,
            'profile_photo_url': self.profile_photo_url,
            'banner_photo_url': self.banner_photo_url,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'is_certified': self.is_certified == 'true',
            'social_links': self.social_links,
            'tags': self.tags,
            'stats': self.stats,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # User-specific fields
        if self.user_type == 'user':
            data.update({
                'first_name': self.first_name,
                'last_name': self.last_name,
                'date_of_birth': self.date_of_birth
            })
        
        # Organization-specific fields  
        elif self.user_type == 'org':
            data.update({
                'org_type': self.org_type,
                'founded_date': self.founded_date,
                'employee_count': self.employee_count,
                'industry': self.industry
            })
        
        # Sensitive information (only if requested)
        if include_sensitive:
            data.update({
                'email': self.email,
                'phone': self.phone,
                'timezone': self.timezone,
                'privacy_settings': self.privacy_settings,
                'metadata': self.metadata
            })
        
        return data
    
    def update_stats(self, stat_updates: Dict[str, Any]) -> 'UserOrg':
        """
        Update statistics
        
        Args:
            stat_updates: Dictionary of stats to update
            
        Returns:
            Updated UserOrg instance
        """
        current_stats = self.stats or {}
        current_stats.update(stat_updates)
        
        return self.update_entity({'stats': current_stats})
    
    def add_tag(self, tag: str) -> 'UserOrg':
        """
        Add tag to entity
        
        Args:
            tag: Tag to add
            
        Returns:
            Updated UserOrg instance
        """
        current_tags = self.tags or []
        if tag not in current_tags:
            current_tags.append(tag)
            return self.update_entity({'tags': current_tags})
        return self
    
    def remove_tag(self, tag: str) -> 'UserOrg':
        """
        Remove tag from entity
        
        Args:
            tag: Tag to remove
            
        Returns:
            Updated UserOrg instance
        """
        current_tags = self.tags or []
        if tag in current_tags:
            current_tags.remove(tag)
            return self.update_entity({'tags': current_tags})
        return self