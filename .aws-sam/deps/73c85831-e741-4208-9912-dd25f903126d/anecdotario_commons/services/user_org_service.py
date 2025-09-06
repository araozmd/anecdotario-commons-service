"""
User-Organization Service Layer
Provides CRUD operations for the unified user-org table with business logic
"""
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..models.user_org import UserOrg, UserOrgConstants
from ..exceptions import ValidationError, DuplicateEntityError, EntityNotFoundError
from ..logger import get_logger
from ..validators.nickname import nickname_validator


class UserOrgService:
    """
    Service layer for user-organization CRUD operations
    Handles business logic, validation, and data consistency
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_entity(self, 
                     nickname: str,
                     full_name: str,
                     user_type: str,
                     avatar_thumbnail_url: Optional[str] = None,
                     is_certified: bool = False,
                     created_by: Optional[str] = None,
                     email: Optional[str] = None,
                     phone: Optional[str] = None,
                     website: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new user or organization
        
        Args:
            nickname: Unique nickname (primary key)
            full_name: Full name or organization name
            user_type: 'user' or 'organization'
            avatar_thumbnail_url: Optional avatar URL
            is_certified: Whether the entity is certified
            created_by: Who created this entity
            email: Optional email address
            phone: Optional phone number
            website: Optional website URL
            
        Returns:
            Created entity data
            
        Raises:
            ValidationError: Invalid input data
            DuplicateEntityError: Nickname already exists
        """
        with self.logger.operation_timer('entity_creation', 
                                        nickname=nickname,
                                        user_type=user_type):
            
            # Validate input data
            self._validate_entity_data(nickname, full_name, user_type)
            
            # Normalize nickname
            normalized_nickname = nickname.lower().strip()
            
            # Check for uniqueness across all entities (users AND orgs)
            if UserOrg.nickname_exists(normalized_nickname):
                raise DuplicateEntityError(
                    f"Nickname '{nickname}' already exists",
                    {'nickname': normalized_nickname, 'user_type': user_type}
                )
            
            # Validate nickname using the existing validator
            validation_result = nickname_validator.validate(normalized_nickname, user_type)
            if not validation_result['valid']:
                raise ValidationError(
                    f"Nickname validation failed: {'; '.join(validation_result['errors'])}",
                    {
                        'nickname': nickname,
                        'errors': validation_result['errors'],
                        'hints': validation_result['hints']
                    }
                )
            
            # Create the entity
            try:
                entity = UserOrg(
                    nickname=normalized_nickname,
                    full_name=full_name.strip(),
                    user_type=user_type,
                    avatar_thumbnail_url=avatar_thumbnail_url,
                    is_certified=is_certified,
                    created_by=created_by,
                    email=email,
                    phone=phone,
                    website=website,
                    status='active'
                )
                
                entity.save()
                
                # Log business event
                self.logger.log_business_event('entity_created',
                                             nickname=normalized_nickname,
                                             user_type=user_type,
                                             full_name=full_name,
                                             is_certified=is_certified)
                
                # Log performance metric
                self.logger.log_performance_metric('entities_created', 1, 'count')
                
                return entity.to_dict()
                
            except Exception as e:
                self.logger.error(f"Failed to create entity: {str(e)}", 
                                nickname=nickname, 
                                user_type=user_type)
                raise ValidationError(f"Failed to create entity: {str(e)}")
    
    def get_entity(self, nickname: str) -> Dict[str, Any]:
        """
        Get entity by nickname
        
        Args:
            nickname: Entity nickname
            
        Returns:
            Entity data
            
        Raises:
            EntityNotFoundError: Entity not found
        """
        entity = UserOrg.get_by_nickname(nickname)
        if not entity:
            raise EntityNotFoundError(
                f"Entity with nickname '{nickname}' not found",
                {'nickname': nickname}
            )
        
        # Log access
        self.logger.log_business_event('entity_accessed',
                                     nickname=entity.nickname,
                                     user_type=entity.user_type)
        
        return entity.to_dict()
    
    def get_public_entity(self, nickname: str) -> Dict[str, Any]:
        """
        Get public-safe entity data by nickname
        
        Args:
            nickname: Entity nickname
            
        Returns:
            Public entity data (no sensitive info)
            
        Raises:
            EntityNotFoundError: Entity not found
        """
        entity = UserOrg.get_by_nickname(nickname)
        if not entity:
            raise EntityNotFoundError(
                f"Entity with nickname '{nickname}' not found",
                {'nickname': nickname}
            )
        
        return entity.to_public_dict()
    
    def update_entity(self,
                     nickname: str,
                     full_name: Optional[str] = None,
                     avatar_thumbnail_url: Optional[str] = None,
                     email: Optional[str] = None,
                     phone: Optional[str] = None,
                     website: Optional[str] = None) -> Dict[str, Any]:
        """
        Update entity data (nickname and user_type cannot be changed)
        
        Args:
            nickname: Entity nickname (immutable)
            full_name: Updated full name
            avatar_thumbnail_url: Updated avatar URL
            email: Updated email
            phone: Updated phone
            website: Updated website
            
        Returns:
            Updated entity data
            
        Raises:
            EntityNotFoundError: Entity not found
            ValidationError: Invalid update data
        """
        with self.logger.operation_timer('entity_update', nickname=nickname):
            
            entity = UserOrg.get_by_nickname(nickname)
            if not entity:
                raise EntityNotFoundError(
                    f"Entity with nickname '{nickname}' not found",
                    {'nickname': nickname}
                )
            
            # Track what fields are being updated
            updated_fields = []
            
            # Update fields if provided
            if full_name is not None:
                self._validate_full_name(full_name)
                entity.full_name = full_name.strip()
                updated_fields.append('full_name')
            
            if avatar_thumbnail_url is not None:
                entity.avatar_thumbnail_url = avatar_thumbnail_url
                updated_fields.append('avatar_thumbnail_url')
            
            if email is not None:
                if email and not self._is_valid_email(email):
                    raise ValidationError("Invalid email format")
                entity.email = email
                updated_fields.append('email')
            
            if phone is not None:
                entity.phone = phone
                updated_fields.append('phone')
            
            if website is not None:
                if website and not self._is_valid_url(website):
                    raise ValidationError("Invalid website URL format")
                entity.website = website
                updated_fields.append('website')
            
            if not updated_fields:
                raise ValidationError("No fields provided for update")
            
            # Save changes
            entity.save()
            
            # Log business event
            self.logger.log_business_event('entity_updated',
                                         nickname=nickname,
                                         user_type=entity.user_type,
                                         updated_fields=updated_fields)
            
            return entity.to_dict()
    
    def delete_entity(self, nickname: str, permanent: bool = False) -> Dict[str, Any]:
        """
        Delete entity (soft delete by default)
        
        Args:
            nickname: Entity nickname
            permanent: If True, permanently delete; if False, soft delete
            
        Returns:
            Deletion result
            
        Raises:
            EntityNotFoundError: Entity not found
        """
        with self.logger.operation_timer('entity_deletion', 
                                        nickname=nickname, 
                                        permanent=permanent):
            
            entity = UserOrg.get_by_nickname(nickname)
            if not entity:
                raise EntityNotFoundError(
                    f"Entity with nickname '{nickname}' not found",
                    {'nickname': nickname}
                )
            
            if permanent:
                # Hard delete
                entity.delete()
                
                # Log business event
                self.logger.log_business_event('entity_permanently_deleted',
                                             nickname=nickname,
                                             user_type=entity.user_type)
                
                return {
                    'nickname': nickname,
                    'permanently_deleted': True,
                    'deleted_at': datetime.utcnow().isoformat()
                }
            else:
                # Soft delete
                entity.deactivate()
                
                # Log business event
                self.logger.log_business_event('entity_deactivated',
                                             nickname=nickname,
                                             user_type=entity.user_type)
                
                return {
                    'nickname': nickname,
                    'deactivated': True,
                    'status': 'inactive',
                    'deactivated_at': entity.updated_at.isoformat()
                }
    
    def list_entities(self,
                     user_type: Optional[str] = None,
                     limit: int = 50,
                     last_evaluated_key: Optional[str] = None) -> Dict[str, Any]:
        """
        List entities with optional filtering
        
        Args:
            user_type: Filter by user type ('user', 'organization', or None for all)
            limit: Maximum results per page
            last_evaluated_key: For pagination
            
        Returns:
            List of entities with pagination info
        """
        with self.logger.operation_timer('entities_list', 
                                        user_type=user_type,
                                        limit=limit):
            
            if user_type == 'user':
                result = UserOrg.get_users(limit, last_evaluated_key)
                self.logger.log_performance_metric('users_listed', len(result['users']), 'count')
            elif user_type == 'organization':
                result = UserOrg.get_organizations(limit, last_evaluated_key)
                self.logger.log_performance_metric('orgs_listed', len(result['organizations']), 'count')
            else:
                # Get both - this requires two queries
                users_result = UserOrg.get_users(limit // 2)
                orgs_result = UserOrg.get_organizations(limit // 2)
                
                result = {
                    'entities': users_result['users'] + orgs_result['organizations'],
                    'total_returned': len(users_result['users']) + len(orgs_result['organizations']),
                    'last_evaluated_key': None  # Simplified for mixed results
                }
                
                self.logger.log_performance_metric('entities_listed', result['total_returned'], 'count')
            
            return result
    
    def search_entities(self, partial_nickname: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search entities by partial nickname
        
        Args:
            partial_nickname: Partial nickname to search for
            limit: Maximum results
            
        Returns:
            List of matching entities
        """
        with self.logger.operation_timer('entities_search', 
                                        partial_nickname=partial_nickname,
                                        limit=limit):
            
            results = UserOrg.search_by_partial_nickname(partial_nickname, limit)
            
            self.logger.log_performance_metric('entities_searched', len(results), 'count')
            self.logger.log_business_event('entities_searched',
                                         partial_nickname=partial_nickname,
                                         results_count=len(results))
            
            return results
    
    def get_certified_entities(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all certified entities
        
        Args:
            limit: Maximum results
            
        Returns:
            List of certified entities
        """
        with self.logger.operation_timer('certified_entities_list', limit=limit):
            
            results = UserOrg.get_certified_entities(limit)
            
            self.logger.log_performance_metric('certified_entities_listed', len(results), 'count')
            
            return results
    
    def set_certification_status(self, 
                                nickname: str, 
                                is_certified: bool, 
                                certified_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Update entity certification status
        
        Args:
            nickname: Entity nickname
            is_certified: New certification status
            certified_by: Who granted/revoked certification
            
        Returns:
            Updated entity data
            
        Raises:
            EntityNotFoundError: Entity not found
        """
        entity = UserOrg.get_by_nickname(nickname)
        if not entity:
            raise EntityNotFoundError(
                f"Entity with nickname '{nickname}' not found",
                {'nickname': nickname}
            )
        
        old_status = entity.is_certified
        entity.set_certification_status(is_certified, certified_by)
        
        # Log business event
        action = 'certified' if is_certified else 'uncertified'
        self.logger.log_business_event(f'entity_{action}',
                                     nickname=nickname,
                                     user_type=entity.user_type,
                                     previous_status=old_status,
                                     certified_by=certified_by)
        
        return entity.to_dict()
    
    def update_stats(self, 
                    nickname: str,
                    followers_delta: int = 0,
                    following_delta: int = 0,
                    posts_delta: int = 0) -> Dict[str, Any]:
        """
        Update entity statistics
        
        Args:
            nickname: Entity nickname
            followers_delta: Change in followers count
            following_delta: Change in following count
            posts_delta: Change in posts count
            
        Returns:
            Updated entity data
            
        Raises:
            EntityNotFoundError: Entity not found
        """
        entity = UserOrg.get_by_nickname(nickname)
        if not entity:
            raise EntityNotFoundError(
                f"Entity with nickname '{nickname}' not found",
                {'nickname': nickname}
            )
        
        entity.update_stats(followers_delta, following_delta, posts_delta)
        
        # Log statistics update
        self.logger.log_business_event('entity_stats_updated',
                                     nickname=nickname,
                                     user_type=entity.user_type,
                                     followers_delta=followers_delta,
                                     following_delta=following_delta,
                                     posts_delta=posts_delta)
        
        return entity.to_dict()
    
    # Private validation methods
    def _validate_entity_data(self, nickname: str, full_name: str, user_type: str):
        """Validate basic entity data"""
        if not nickname or not nickname.strip():
            raise ValidationError("Nickname is required")
        
        if not full_name or not full_name.strip():
            raise ValidationError("Full name is required")
        
        if user_type not in UserOrgConstants.VALID_USER_TYPES:
            raise ValidationError(
                f"Invalid user_type. Must be one of: {', '.join(UserOrgConstants.VALID_USER_TYPES)}"
            )
        
        # Validate nickname format
        if not re.match(UserOrgConstants.NICKNAME_PATTERN, nickname.lower()):
            raise ValidationError("Nickname can only contain lowercase letters, numbers, and underscores")
        
        if len(nickname) < UserOrgConstants.MIN_NICKNAME_LENGTH:
            raise ValidationError(f"Nickname must be at least {UserOrgConstants.MIN_NICKNAME_LENGTH} characters long")
        
        if len(nickname) > UserOrgConstants.MAX_NICKNAME_LENGTH:
            raise ValidationError(f"Nickname cannot exceed {UserOrgConstants.MAX_NICKNAME_LENGTH} characters")
        
        self._validate_full_name(full_name)
    
    def _validate_full_name(self, full_name: str):
        """Validate full name"""
        if len(full_name.strip()) < UserOrgConstants.MIN_FULL_NAME_LENGTH:
            raise ValidationError(f"Full name must be at least {UserOrgConstants.MIN_FULL_NAME_LENGTH} characters long")
        
        if len(full_name.strip()) > UserOrgConstants.MAX_FULL_NAME_LENGTH:
            raise ValidationError(f"Full name cannot exceed {UserOrgConstants.MAX_FULL_NAME_LENGTH} characters")
    
    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None
    
    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return re.match(url_pattern, url, re.IGNORECASE) is not None