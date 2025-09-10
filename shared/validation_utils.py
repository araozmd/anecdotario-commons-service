"""
Commons Service Validation Utilities
Validation functions migrated from anecdotario-commons
"""
import re
import base64
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from .constants import ValidationConstants, EntityConstants, ImageConstants
from .exceptions import ValidationError


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """
    Validate that all required fields are present in the data.
    
    Args:
        data: Dictionary containing the data to validate
        required_fields: List of required field names
        
    Returns:
        List of missing field names (empty if all fields are present)
    """
    if not isinstance(data, dict):
        return required_fields
    
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing_fields.append(field)
    
    return missing_fields


def normalize_nickname(nickname: str) -> str:
    """
    Normalize a nickname by converting to lowercase and stripping whitespace.
    
    Args:
        nickname: Raw nickname string
        
    Returns:
        Normalized nickname
    """
    if not isinstance(nickname, str):
        return ""
    
    return nickname.strip().lower()


def validate_nickname(nickname: str, entity_type: str = 'user') -> Dict[str, Any]:
    """
    Validate a nickname according to rules for the specified entity type.
    
    Args:
        nickname: Nickname to validate
        entity_type: Type of entity ('user', 'org', 'campaign')
        
    Returns:
        Dictionary with validation results:
        {
            'valid': bool,
            'nickname': str (normalized),
            'errors': List[str],
            'hints': List[str]
        }
    """
    result = {
        'valid': False,
        'nickname': normalize_nickname(nickname),
        'errors': [],
        'hints': []
    }
    
    # Basic validation
    if not nickname or not isinstance(nickname, str):
        result['errors'].append('Nickname is required')
        result['hints'].append('Please provide a valid nickname')
        return result
    
    normalized = result['nickname']
    
    # Length validation
    if len(normalized) < ValidationConstants.MIN_NICKNAME_LENGTH:
        result['errors'].append(f'Nickname must be at least {ValidationConstants.MIN_NICKNAME_LENGTH} characters long')
        result['hints'].append(f'Try adding more characters (minimum {ValidationConstants.MIN_NICKNAME_LENGTH})')
        
    if len(normalized) > ValidationConstants.MAX_NICKNAME_LENGTH:
        result['errors'].append(f'Nickname must be no more than {ValidationConstants.MAX_NICKNAME_LENGTH} characters long')
        result['hints'].append(f'Try shortening the nickname (maximum {ValidationConstants.MAX_NICKNAME_LENGTH} characters)')
    
    # Pattern validation
    if not re.match(ValidationConstants.NICKNAME_PATTERN, normalized):
        result['errors'].append('Nickname can only contain letters, numbers, underscores, and hyphens')
        result['hints'].append('Use only a-z, A-Z, 0-9, _ and - characters')
    
    # Reserved words validation
    reserved_words = []
    if entity_type == 'user':
        reserved_words = ValidationConstants.RESERVED_USER_NICKNAMES
    elif entity_type == 'org':
        reserved_words = ValidationConstants.RESERVED_ORG_NICKNAMES  
    elif entity_type == 'campaign':
        reserved_words = ValidationConstants.RESERVED_CAMPAIGN_NICKNAMES
    
    if normalized in reserved_words:
        result['errors'].append('This nickname is reserved and cannot be used')
        result['hints'].append('Please choose a different nickname')
    
    # Set valid flag
    result['valid'] = len(result['errors']) == 0
    
    return result


def validate_name(name: str) -> Dict[str, Any]:
    """
    Validate a display name.
    
    Args:
        name: Name to validate
        
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': False,
        'name': name.strip() if isinstance(name, str) else '',
        'errors': [],
        'hints': []
    }
    
    if not name or not isinstance(name, str):
        result['errors'].append('Name is required')
        result['hints'].append('Please provide a valid name')
        return result
    
    trimmed = result['name']
    
    # Length validation
    if len(trimmed) < ValidationConstants.MIN_NAME_LENGTH:
        result['errors'].append(f'Name must be at least {ValidationConstants.MIN_NAME_LENGTH} character long')
        result['hints'].append('Please provide a name')
        
    if len(trimmed) > ValidationConstants.MAX_NAME_LENGTH:
        result['errors'].append(f'Name must be no more than {ValidationConstants.MAX_NAME_LENGTH} characters long')
        result['hints'].append(f'Try shortening the name (maximum {ValidationConstants.MAX_NAME_LENGTH} characters)')
    
    # Pattern validation (no leading/trailing spaces)
    if trimmed and not re.match(ValidationConstants.NAME_PATTERN, trimmed):
        result['errors'].append('Name cannot start or end with spaces')
        result['hints'].append('Remove leading and trailing spaces')
    
    result['valid'] = len(result['errors']) == 0
    return result


def validate_description(description: str) -> Dict[str, Any]:
    """
    Validate a description field.
    
    Args:
        description: Description to validate
        
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': False,
        'description': description.strip() if isinstance(description, str) else '',
        'errors': [],
        'hints': []
    }
    
    # Description is optional, so empty is valid
    if not description:
        result['valid'] = True
        return result
    
    trimmed = result['description']
    
    # Length validation
    if len(trimmed) > ValidationConstants.MAX_DESCRIPTION_LENGTH:
        result['errors'].append(f'Description must be no more than {ValidationConstants.MAX_DESCRIPTION_LENGTH} characters long')
        result['hints'].append(f'Try shortening the description (maximum {ValidationConstants.MAX_DESCRIPTION_LENGTH} characters)')
    
    result['valid'] = len(result['errors']) == 0
    return result


def validate_bio(bio: str) -> Dict[str, Any]:
    """
    Validate a bio field.
    
    Args:
        bio: Bio to validate
        
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': False,
        'bio': bio.strip() if isinstance(bio, str) else '',
        'errors': [],
        'hints': []
    }
    
    # Bio is optional, so empty is valid
    if not bio:
        result['valid'] = True
        return result
    
    trimmed = result['bio']
    
    # Length validation
    if len(trimmed) > ValidationConstants.MAX_BIO_LENGTH:
        result['errors'].append(f'Bio must be no more than {ValidationConstants.MAX_BIO_LENGTH} characters long')
        result['hints'].append(f'Try shortening the bio (maximum {ValidationConstants.MAX_BIO_LENGTH} characters)')
    
    result['valid'] = len(result['errors']) == 0
    return result


def parse_base64_image(image_data: str) -> Tuple[str, bytes]:
    """
    Parse base64 encoded image data.
    
    Args:
        image_data: Base64 encoded image string with data URL prefix
        
    Returns:
        Tuple of (format, image_bytes)
        
    Raises:
        ValidationError: If image data is invalid
    """
    if not isinstance(image_data, str):
        raise ValidationError('Image data must be a string')
    
    # Check for data URL prefix
    if not image_data.startswith('data:image/'):
        raise ValidationError('Image data must start with data:image/ prefix')
    
    try:
        # Extract the format and base64 data
        header, base64_data = image_data.split(',', 1)
        
        # Extract format from header (e.g., "data:image/jpeg;base64" -> "jpeg")
        format_part = header.split('/')[1].split(';')[0].upper()
        
        # Normalize format names
        if format_part in ['JPG', 'JPEG']:
            format_part = 'JPEG'
        elif format_part == 'PNG':
            format_part = 'PNG'
        elif format_part == 'WEBP':
            format_part = 'WEBP'
        else:
            raise ValidationError(f'Unsupported image format: {format_part}')
        
        if format_part not in ImageConstants.SUPPORTED_FORMATS:
            raise ValidationError(f'Unsupported image format: {format_part}')
        
        # Decode base64 data
        image_bytes = base64.b64decode(base64_data)
        
        if len(image_bytes) == 0:
            raise ValidationError('Image data is empty')
        
        if len(image_bytes) > ImageConstants.MAX_FILE_SIZE:
            max_mb = ImageConstants.MAX_FILE_SIZE / (1024 * 1024)
            raise ValidationError(f'Image file too large. Maximum size: {max_mb:.1f}MB')
        
        return format_part, image_bytes
    
    except (ValueError, base64.binascii.Error) as e:
        raise ValidationError(f'Invalid base64 image data: {str(e)}')


def generate_photo_id() -> str:
    """
    Generate a unique photo ID.
    
    Returns:
        Unique photo ID string
    """
    return str(uuid.uuid4())


def generate_storage_key(entity_type: str, entity_id: str, photo_type: str, version: str, 
                        timestamp: str = None, hash_suffix: str = None) -> str:
    """
    Generate S3 storage key for photo.
    
    Args:
        entity_type: Type of entity (user, org, campaign)
        entity_id: ID of the entity
        photo_type: Type of photo (profile, logo, banner, gallery)
        version: Photo version (thumbnail, standard, high_res)
        timestamp: Optional timestamp string
        hash_suffix: Optional hash suffix for uniqueness
        
    Returns:
        S3 storage key string
    """
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    
    if not hash_suffix:
        # Generate a short hash for uniqueness
        hash_input = f"{entity_type}_{entity_id}_{photo_type}_{version}_{timestamp}"
        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    
    filename = f"{version}_{timestamp}_{hash_suffix}.jpg"
    return f"{entity_type}/{entity_id}/{photo_type}/{filename}"


def validate_entity_type(entity_type: str, valid_types: List[str] = None) -> bool:
    """
    Validate entity type.
    
    Args:
        entity_type: Entity type to validate
        valid_types: List of valid entity types (defaults to all types)
        
    Returns:
        True if valid, False otherwise
    """
    if not entity_type or not isinstance(entity_type, str):
        return False
    
    valid_types = valid_types or EntityConstants.ALL_ENTITY_TYPES
    return entity_type.lower() in valid_types


def validate_photo_type(photo_type: str, entity_type: str = None) -> bool:
    """
    Validate photo type for the given entity type.
    
    Args:
        photo_type: Photo type to validate
        entity_type: Entity type for context-specific validation
        
    Returns:
        True if valid, False otherwise
    """
    if not photo_type or not isinstance(photo_type, str):
        return False
    
    photo_type = photo_type.lower()
    
    # If no entity type specified, check against all photo types
    if not entity_type:
        return photo_type in EntityConstants.ALL_PHOTO_TYPES
    
    # Entity-specific validation
    entity_type = entity_type.lower()
    if entity_type == EntityConstants.USER:
        return photo_type in EntityConstants.USER_PHOTO_TYPES
    elif entity_type == EntityConstants.ORG:
        return photo_type in EntityConstants.ORG_PHOTO_TYPES
    elif entity_type == EntityConstants.CAMPAIGN:
        return photo_type in EntityConstants.CAMPAIGN_PHOTO_TYPES
    else:
        return False


def validate_page_params(page: int, page_size: int, max_page_size: int = 100) -> Dict[str, Any]:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number (0-based)
        page_size: Items per page
        max_page_size: Maximum allowed page size
        
    Returns:
        Dictionary with validation results and normalized values
    """
    result = {
        'valid': False,
        'page': max(0, page) if isinstance(page, int) else 0,
        'page_size': page_size,
        'errors': [],
        'hints': []
    }
    
    # Validate page number
    if not isinstance(page, int) or page < 0:
        result['errors'].append('Page number must be a non-negative integer')
        result['hints'].append('Use page=0 for the first page')
    
    # Validate page size
    if not isinstance(page_size, int) or page_size <= 0:
        result['errors'].append('Page size must be a positive integer')
        result['hints'].append(f'Use a page size between 1 and {max_page_size}')
    elif page_size > max_page_size:
        result['errors'].append(f'Page size cannot exceed {max_page_size}')
        result['hints'].append(f'Use a page size between 1 and {max_page_size}')
        result['page_size'] = max_page_size  # Auto-correct
    
    result['valid'] = len(result['errors']) == 0
    return result


def sanitize_search_query(query: str) -> str:
    """
    Sanitize search query string.
    
    Args:
        query: Raw search query
        
    Returns:
        Sanitized query string
    """
    if not isinstance(query, str):
        return ""
    
    # Strip whitespace and normalize
    sanitized = query.strip().lower()
    
    # Remove special characters that might cause issues
    sanitized = re.sub(r'[^\w\s\-_]', '', sanitized)
    
    # Normalize multiple spaces to single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    return sanitized[:100]  # Limit length


def validate_user_type(user_type: str) -> bool:
    """
    Validate user type field.
    
    Args:
        user_type: User type to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not user_type or not isinstance(user_type, str):
        return False
    
    valid_user_types = ['individual', 'organization']
    return user_type.lower() in valid_user_types