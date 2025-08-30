"""
User-Organization Unified Model for DynamoDB
Stores both users and organizations in a single table with unified nickname space
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute, BooleanAttribute, UTCDateTimeAttribute,
    NumberAttribute, MapAttribute, ListAttribute
)
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection
import os


class UserOrgTypeIndex(GlobalSecondaryIndex):
    """GSI for querying by user_type (user/org)"""
    class Meta:
        index_name = 'user-type-index'
        projection = AllProjection()
        read_capacity_units = 5
        write_capacity_units = 5
    
    user_type = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class CertificationStatusIndex(GlobalSecondaryIndex):
    """GSI for querying certified users/orgs"""
    class Meta:
        index_name = 'certification-status-index'
        projection = AllProjection()
        read_capacity_units = 2
        write_capacity_units = 2
    
    is_certified = BooleanAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class UserOrg(Model):
    """
    Unified User-Organization model for DynamoDB
    Stores both individual users and organizations in the same table
    to ensure nickname uniqueness across all entity types
    """
    
    class Meta:
        table_name = os.environ.get('USER_ORG_TABLE_NAME', 'UserOrg-dev')
        region = 'us-east-1'
        billing_mode = 'PAY_PER_REQUEST'  # On-demand billing
    
    # Primary Key
    nickname = UnicodeAttribute(hash_key=True)  # Primary key - must be unique across users/orgs
    
    # Core Attributes
    full_name = UnicodeAttribute()
    avatar_thumbnail_url = UnicodeAttribute(null=True)
    is_certified = BooleanAttribute(default=False)
    user_type = UnicodeAttribute()  # 'user' or 'organization'
    
    # Metadata
    created_at = UTCDateTimeAttribute(default=datetime.utcnow)
    updated_at = UTCDateTimeAttribute(default=datetime.utcnow)
    created_by = UnicodeAttribute(null=True)  # Who created this entity
    status = UnicodeAttribute(default='active')  # active, inactive, suspended
    
    # Contact Information (optional)
    email = UnicodeAttribute(null=True)
    phone = UnicodeAttribute(null=True)
    website = UnicodeAttribute(null=True)
    
    # Statistics
    followers_count = NumberAttribute(default=0)
    following_count = NumberAttribute(default=0)
    posts_count = NumberAttribute(default=0)
    
    # Global Secondary Indexes
    user_type_index = UserOrgTypeIndex()
    certification_index = CertificationStatusIndex()
    
    def save(self, **kwargs):
        """Override save to update timestamp"""
        self.updated_at = datetime.utcnow()
        super().save(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses"""
        return {
            'nickname': self.nickname,
            'full_name': self.full_name,
            'avatar_thumbnail_url': self.avatar_thumbnail_url,
            'is_certified': self.is_certified,
            'user_type': self.user_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status': self.status,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'followers_count': self.followers_count,
            'following_count': self.following_count,
            'posts_count': self.posts_count
        }
    
    def to_public_dict(self) -> Dict[str, Any]:
        """Convert to public-safe dictionary (no sensitive info)"""
        return {
            'nickname': self.nickname,
            'full_name': self.full_name,
            'avatar_thumbnail_url': self.avatar_thumbnail_url,
            'is_certified': self.is_certified,
            'user_type': self.user_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status,
            'website': self.website,
            'followers_count': self.followers_count,
            'posts_count': self.posts_count
        }
    
    @classmethod
    def nickname_exists(cls, nickname: str) -> bool:
        """
        Check if nickname exists in the system (users or orgs)
        
        Args:
            nickname: Nickname to check
            
        Returns:
            True if nickname exists, False otherwise
        """
        try:
            cls.get(nickname.lower())
            return True
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def get_by_nickname(cls, nickname: str) -> Optional['UserOrg']:
        """
        Get user/org by nickname (case-insensitive)
        
        Args:
            nickname: Nickname to search for
            
        Returns:
            UserOrg instance or None if not found
        """
        try:
            return cls.get(nickname.lower())
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_users(cls, limit: int = 50, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get all users (not organizations)
        
        Args:
            limit: Maximum number of results
            last_evaluated_key: For pagination
            
        Returns:
            Dictionary with users and pagination info
        """
        query_kwargs = {
            'limit': limit,
            'scan_index_forward': False  # Most recent first
        }
        
        if last_evaluated_key:
            query_kwargs['last_evaluated_key'] = last_evaluated_key
        
        results = cls.user_type_index.query('user', **query_kwargs)
        
        users = []
        last_key = None
        
        for user in results:
            users.append(user.to_public_dict())
            last_key = user.nickname
        
        return {
            'users': users,
            'last_evaluated_key': last_key if len(users) == limit else None,
            'total_returned': len(users)
        }
    
    @classmethod
    def get_organizations(cls, limit: int = 50, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get all organizations (not users)
        
        Args:
            limit: Maximum number of results
            last_evaluated_key: For pagination
            
        Returns:
            Dictionary with organizations and pagination info
        """
        query_kwargs = {
            'limit': limit,
            'scan_index_forward': False  # Most recent first
        }
        
        if last_evaluated_key:
            query_kwargs['last_evaluated_key'] = last_evaluated_key
        
        results = cls.user_type_index.query('organization', **query_kwargs)
        
        orgs = []
        last_key = None
        
        for org in results:
            orgs.append(org.to_public_dict())
            last_key = org.nickname
        
        return {
            'organizations': orgs,
            'last_evaluated_key': last_key if len(orgs) == limit else None,
            'total_returned': len(orgs)
        }
    
    @classmethod
    def get_certified_entities(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all certified users and organizations
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of certified entities
        """
        results = cls.certification_index.query(
            True,  # is_certified = True
            limit=limit,
            scan_index_forward=False
        )
        
        return [entity.to_public_dict() for entity in results]
    
    @classmethod
    def search_by_partial_nickname(cls, partial_nickname: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for entities with nicknames starting with partial_nickname
        Note: This requires a scan operation, use sparingly
        
        Args:
            partial_nickname: Partial nickname to search for
            limit: Maximum results
            
        Returns:
            List of matching entities
        """
        # This is a scan operation - expensive but necessary for partial matching
        filter_condition = cls.nickname.startswith(partial_nickname.lower())
        
        results = cls.scan(
            filter_condition=filter_condition,
            limit=limit
        )
        
        return [entity.to_public_dict() for entity in results]
    
    def update_stats(self, followers_delta: int = 0, following_delta: int = 0, posts_delta: int = 0):
        """
        Update entity statistics
        
        Args:
            followers_delta: Change in followers count
            following_delta: Change in following count  
            posts_delta: Change in posts count
        """
        if followers_delta != 0:
            self.followers_count = max(0, self.followers_count + followers_delta)
        
        if following_delta != 0:
            self.following_count = max(0, self.following_count + following_delta)
        
        if posts_delta != 0:
            self.posts_count = max(0, self.posts_count + posts_delta)
        
        self.save()
    
    def set_certification_status(self, is_certified: bool, certified_by: Optional[str] = None):
        """
        Update certification status
        
        Args:
            is_certified: New certification status
            certified_by: Who granted/revoked certification
        """
        self.is_certified = is_certified
        
        # Could add certification metadata here if needed
        # self.certification_granted_by = certified_by
        # self.certification_date = datetime.utcnow()
        
        self.save()
    
    def update_avatar(self, avatar_url: str):
        """
        Update avatar thumbnail URL
        
        Args:
            avatar_url: New avatar URL
        """
        self.avatar_thumbnail_url = avatar_url
        self.save()
    
    def deactivate(self):
        """Mark entity as inactive"""
        self.status = 'inactive'
        self.save()
    
    def reactivate(self):
        """Mark entity as active"""
        self.status = 'active'
        self.save()
    
    def suspend(self):
        """Mark entity as suspended"""
        self.status = 'suspended'
        self.save()


# Validation constants for the unified model
class UserOrgConstants:
    """Constants for user-org validation"""
    
    VALID_USER_TYPES = ['user', 'organization']
    VALID_STATUSES = ['active', 'inactive', 'suspended']
    
    # Nickname validation
    MIN_NICKNAME_LENGTH = 3
    MAX_NICKNAME_LENGTH = 30
    NICKNAME_PATTERN = r'^[a-z0-9_]+$'
    
    # Full name validation
    MIN_FULL_NAME_LENGTH = 2
    MAX_FULL_NAME_LENGTH = 100
    
    # Reserved nicknames (system reserved)
    SYSTEM_RESERVED_NICKNAMES = {
        'admin', 'administrator', 'root', 'system', 'api', 'www', 'mail',
        'ftp', 'support', 'help', 'info', 'contact', 'about', 'terms',
        'privacy', 'legal', 'anecdotario', 'anecdotes', 'stories'
    }