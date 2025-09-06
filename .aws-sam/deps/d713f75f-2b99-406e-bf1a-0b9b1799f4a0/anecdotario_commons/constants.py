"""
Shared constants for the commons service
Centralizes magic numbers and configuration values
"""
from enum import Enum
from typing import Dict, List


class TimeConstants:
    """Time-related constants in seconds"""
    SECONDS_IN_MINUTE = 60
    SECONDS_IN_HOUR = 3600
    SECONDS_IN_DAY = 86400
    SECONDS_IN_WEEK = 604800
    SECONDS_IN_MONTH = 2592000  # 30 days
    
    # Presigned URL expiry times
    MIN_PRESIGNED_URL_EXPIRY = 5 * SECONDS_IN_MINUTE      # 5 minutes
    DEFAULT_PRESIGNED_URL_EXPIRY = SECONDS_IN_WEEK        # 7 days
    MAX_PRESIGNED_URL_EXPIRY = SECONDS_IN_WEEK            # 7 days
    
    # Cache expiry times
    CONFIG_CACHE_EXPIRY = 5 * SECONDS_IN_MINUTE           # 5 minutes
    VALIDATION_RULES_CACHE_EXPIRY = 1 * SECONDS_IN_HOUR   # 1 hour


class ImageConstants:
    """Image processing and storage constants"""
    # File size limits
    MAX_IMAGE_SIZE = 5 * 1024 * 1024        # 5MB
    MIN_IMAGE_SIZE = 1024                   # 1KB
    
    # Image dimension limits
    MIN_IMAGE_DIMENSION = 50                # 50px minimum
    MAX_IMAGE_DIMENSION = 5000              # 5000px maximum
    
    # Standard image sizes
    THUMBNAIL_SIZE = 150                    # 150x150
    STANDARD_SIZE = 320                     # 320x320  
    HIGH_RES_SIZE = 800                     # 800x800
    
    # Image quality settings
    THUMBNAIL_QUALITY = 85
    STANDARD_QUALITY = 90
    HIGH_RES_QUALITY = 95
    
    # Supported formats
    SUPPORTED_IMAGE_FORMATS = ['JPEG', 'PNG', 'WEBP']
    OUTPUT_FORMAT = 'JPEG'
    
    # EXIF orientation values
    EXIF_ORIENTATION_TAG = 274


class ValidationConstants:
    """Validation-related constants"""
    # Nickname validation
    MIN_NICKNAME_LENGTH = 3
    MAX_NICKNAME_LENGTH = 30
    NICKNAME_PATTERN = r'^[a-z0-9_]+$'
    
    # Reserved words categories
    RESERVED_WORD_MIN_LENGTH_FOR_PARTIAL = 4  # Minimum length to check partial matches
    
    # Complexity thresholds
    MIN_NICKNAME_UNIQUE_CHARS = 3  # For low complexity warning


class EntityConstants:
    """Entity type constants"""
    VALID_ENTITY_TYPES = ['user', 'org', 'campaign']  # All entities for photo operations
    NICKNAME_ENTITY_TYPES = ['user', 'org']            # Only user/org have nicknames
    
    # Photo types by entity
    VALID_PHOTO_TYPES: Dict[str, List[str]] = {
        'user': ['profile', 'gallery'],
        'org': ['logo', 'banner', 'gallery'],
        'campaign': ['banner', 'thumbnail', 'gallery']
    }


class StorageConstants:
    """Storage and S3 constants"""
    # S3 key patterns
    S3_KEY_PATTERN = "{entity_type}s/{entity_id}/{photo_type}/{version}_{photo_id}.jpg"
    
    # Public URL pattern
    PUBLIC_URL_PATTERN = "https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    
    # Image versions
    IMAGE_VERSIONS = ['thumbnail', 'standard', 'high_res']
    
    # Public vs protected versions
    PUBLIC_VERSIONS = ['thumbnail']
    PROTECTED_VERSIONS = ['standard', 'high_res']


class HTTPConstants:
    """HTTP status codes and headers"""
    # Status codes
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500
    
    # Headers
    CONTENT_TYPE_JSON = 'application/json'
    CONTENT_TYPE_IMAGE = 'image/jpeg'


class ErrorMessages:
    """Standard error messages"""
    # Request validation
    NO_BODY = "No request body provided"
    INVALID_JSON = "Invalid JSON in request body"
    MISSING_FIELD = "Missing required field: {field}"
    INVALID_ENTITY_TYPE = "Invalid entity_type. Must be one of: {valid_types}"
    INVALID_PHOTO_TYPE = "Invalid photo_type for {entity_type}. Must be one of: {valid_types}"
    
    # Image validation
    INVALID_IMAGE_FORMAT = "Invalid image format. Must be a valid JPEG, PNG, or WebP image"
    IMAGE_TOO_LARGE = "Image size exceeds maximum limit of {max_size_mb}MB"
    IMAGE_TOO_SMALL = "Image is too small. Minimum size is {min_size}KB"
    INVALID_IMAGE_DATA = "Invalid or corrupted image data"
    
    # General errors
    INTERNAL_ERROR = "Internal server error"
    NOT_FOUND_ERROR = "Resource not found"


class ConfigDefaults:
    """Default configuration values"""
    # Environment defaults
    DEFAULT_ENVIRONMENT = 'dev'
    DEFAULT_REGION = 'us-east-1'
    
    # Service defaults
    DEFAULT_LAMBDA_TIMEOUT = 30
    DEFAULT_LAMBDA_MEMORY = 128
    
    # Table names
    DEFAULT_PHOTO_TABLE_PATTERN = "Photos-{environment}"
    
    # Bucket names  
    DEFAULT_PHOTO_BUCKET_PATTERN = "anecdotario-photos-{environment}"
    
    # Parameter Store paths
    DEFAULT_PARAMETER_STORE_PREFIX = "/anecdotario/{environment}/commons-service"
    
    # Feature flags
    DEFAULT_ENABLE_CONFUSING_FILTER = True
    DEFAULT_ENABLE_RESERVED_CHECK = True
    DEFAULT_ALLOW_LEADING_DIGITS = False


class LoggingConstants:
    """Logging-related constants"""
    # Log levels
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'
    
    # Log format
    TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
    
    # Context fields
    TRACE_ID_HEADER = 'X-Amzn-Trace-Id'
    REQUEST_ID_HEADER = 'X-Request-ID'


# Convenience mappings
ENTITY_TO_PHOTO_TYPES = EntityConstants.VALID_PHOTO_TYPES
ALL_PHOTO_TYPES = list(set().union(*ENTITY_TO_PHOTO_TYPES.values()))