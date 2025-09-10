"""
Commons Service Constants
All constants needed for commons-service operations, migrated from anecdotario-commons
"""


class HTTPConstants:
    """HTTP status codes and headers"""
    
    # Status codes
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    
    # Headers
    CONTENT_TYPE = 'Content-Type'
    AUTHORIZATION = 'Authorization'
    ACCESS_CONTROL_ALLOW_ORIGIN = 'Access-Control-Allow-Origin'
    ACCESS_CONTROL_ALLOW_HEADERS = 'Access-Control-Allow-Headers'
    ACCESS_CONTROL_ALLOW_METHODS = 'Access-Control-Allow-Methods'
    ACCESS_CONTROL_ALLOW_CREDENTIALS = 'Access-Control-Allow-Credentials'
    
    # MIME types
    JSON = 'application/json'
    TEXT = 'text/plain'
    HTML = 'text/html'


class EntityConstants:
    """Entity type and photo type constants"""
    
    # Entity types
    USER = 'user'
    ORG = 'org' 
    CAMPAIGN = 'campaign'
    
    ALL_ENTITY_TYPES = [USER, ORG, CAMPAIGN]
    
    # Photo types by entity
    USER_PHOTO_TYPES = ['profile']
    ORG_PHOTO_TYPES = ['logo', 'banner']
    CAMPAIGN_PHOTO_TYPES = ['banner', 'gallery']
    
    # All photo types
    PROFILE = 'profile'
    LOGO = 'logo'
    BANNER = 'banner'
    GALLERY = 'gallery'
    
    ALL_PHOTO_TYPES = [PROFILE, LOGO, BANNER, GALLERY]
    
    # Photo version types
    THUMBNAIL = 'thumbnail'
    STANDARD = 'standard'
    HIGH_RES = 'high_res'
    
    # Photo dimensions
    THUMBNAIL_SIZE = (150, 150)
    STANDARD_SIZE = (320, 320)
    HIGH_RES_SIZE = (800, 800)


class ImageConstants:
    """Image processing constants"""
    
    # Supported formats
    JPEG = 'JPEG'
    PNG = 'PNG'
    WEBP = 'WEBP'
    
    SUPPORTED_FORMATS = [JPEG, PNG, WEBP]
    
    # Quality settings
    THUMBNAIL_QUALITY = 85
    STANDARD_QUALITY = 90
    HIGH_RES_QUALITY = 95
    
    # Size limits (bytes)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_DIMENSION = 2048  # pixels
    
    # Base64 prefixes
    BASE64_JPEG_PREFIX = 'data:image/jpeg;base64,'
    BASE64_PNG_PREFIX = 'data:image/png;base64,'
    BASE64_WEBP_PREFIX = 'data:image/webp;base64,'


class ValidationConstants:
    """Validation rules and patterns"""
    
    # Nickname validation
    MIN_NICKNAME_LENGTH = 2
    MAX_NICKNAME_LENGTH = 30
    NICKNAME_PATTERN = r'^[a-zA-Z0-9_-]+$'
    
    # Reserved words for different entity types
    RESERVED_USER_NICKNAMES = [
        'admin', 'administrator', 'root', 'system', 'api', 'www',
        'mail', 'email', 'support', 'help', 'info', 'contact',
        'service', 'services', 'app', 'application', 'test', 'testing',
        'dev', 'development', 'prod', 'production', 'staging', 'stage',
        'user', 'users', 'account', 'accounts', 'profile', 'profiles',
        'settings', 'config', 'configuration', 'dashboard', 'admin',
        'moderator', 'mod', 'staff', 'team', 'about', 'terms',
        'privacy', 'legal', 'copyright', 'trademark', 'null', 'undefined',
        'true', 'false', 'login', 'logout', 'register', 'signup',
        'signin', 'auth', 'authentication', 'authorization', 'oauth',
        'anecdotario', 'story', 'stories', 'campaign', 'campaigns'
    ]
    
    RESERVED_ORG_NICKNAMES = [
        'organization', 'organizations', 'org', 'orgs', 'company',
        'companies', 'business', 'businesses', 'corporation', 'corp',
        'enterprise', 'group', 'team', 'official', 'verified',
        'brand', 'brands', 'partner', 'partners', 'sponsor', 'sponsors'
    ] + RESERVED_USER_NICKNAMES  # Include user reserved words
    
    RESERVED_CAMPAIGN_NICKNAMES = [
        'campaign', 'campaigns', 'story', 'stories', 'collection',
        'collections', 'event', 'events', 'project', 'projects'
    ] + RESERVED_USER_NICKNAMES  # Include user reserved words
    
    # Name validation
    MIN_NAME_LENGTH = 1
    MAX_NAME_LENGTH = 100
    NAME_PATTERN = r'^[^\s].*[^\s]$'  # No leading/trailing spaces
    
    # Description validation
    MAX_DESCRIPTION_LENGTH = 500
    
    # Bio validation
    MAX_BIO_LENGTH = 250


class TimeConstants:
    """Time-related constants"""
    
    # Presigned URL expiration (seconds)
    PRESIGNED_URL_EXPIRY = 7 * 24 * 60 * 60  # 7 days
    SHORT_PRESIGNED_URL_EXPIRY = 60 * 60      # 1 hour
    
    # Cache durations
    CONFIG_CACHE_TTL = 5 * 60  # 5 minutes
    
    # Time formats
    ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
    DATE_FORMAT = '%Y-%m-%d'
    
    # Timezone
    DEFAULT_TIMEZONE = 'UTC'


class DatabaseConstants:
    """Database-related constants"""
    
    # DynamoDB
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # GSI names
    ENTITY_TYPE_INDEX = 'entity-type-index'
    ENTITY_PHOTOS_INDEX = 'entity-photos-index'
    USER_TYPE_INDEX = 'user-type-index'
    CERTIFIED_INDEX = 'certified-index'
    
    # Sort orders
    ASCENDING = 'ASC'
    DESCENDING = 'DESC'


class S3Constants:
    """S3-related constants"""
    
    # Path patterns
    PHOTO_PATH_PATTERN = '{entity_type}/{entity_id}/{photo_type}'
    FILE_NAME_PATTERN = '{version}_{timestamp}_{hash}.jpg'
    
    # Default bucket regions
    DEFAULT_REGION = 'us-east-1'
    
    # CORS settings
    CORS_MAX_AGE = 3600
    CORS_ALLOWED_METHODS = ['GET', 'PUT', 'POST', 'DELETE', 'HEAD']
    CORS_ALLOWED_HEADERS = ['*']
    CORS_EXPOSED_HEADERS = ['ETag']


class SecurityConstants:
    """Security-related constants"""
    
    # JWT
    JWT_ALGORITHM = 'RS256'
    JWT_HEADER = 'Authorization'
    JWT_PREFIX = 'Bearer '
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = 10  # requests per second
    BURST_RATE_LIMIT = 50    # burst capacity
    
    # Encryption
    DEFAULT_KMS_KEY_ALIAS = 'alias/anecdotario-commons'


class ErrorConstants:
    """Error message constants"""
    
    # Generic errors
    INTERNAL_ERROR = 'Internal server error'
    INVALID_REQUEST = 'Invalid request format'
    MISSING_REQUIRED_FIELDS = 'Missing required fields'
    UNAUTHORIZED_ACCESS = 'Unauthorized access'
    FORBIDDEN_ACCESS = 'Access forbidden'
    RESOURCE_NOT_FOUND = 'Resource not found'
    RESOURCE_CONFLICT = 'Resource conflict'
    RATE_LIMIT_EXCEEDED = 'Rate limit exceeded'
    
    # Validation errors
    INVALID_ENTITY_TYPE = 'Invalid entity type'
    INVALID_PHOTO_TYPE = 'Invalid photo type'
    INVALID_NICKNAME = 'Invalid nickname format'
    NICKNAME_TOO_SHORT = 'Nickname too short'
    NICKNAME_TOO_LONG = 'Nickname too long'
    NICKNAME_RESERVED = 'Nickname is reserved'
    NICKNAME_TAKEN = 'Nickname already taken'
    
    # Image errors
    INVALID_IMAGE_FORMAT = 'Invalid image format'
    IMAGE_TOO_LARGE = 'Image file too large'
    IMAGE_DIMENSIONS_TOO_LARGE = 'Image dimensions too large'
    IMAGE_PROCESSING_FAILED = 'Image processing failed'
    
    # S3 errors
    S3_UPLOAD_FAILED = 'Failed to upload to S3'
    S3_DELETE_FAILED = 'Failed to delete from S3'
    S3_ACCESS_DENIED = 'S3 access denied'
    
    # DynamoDB errors
    DYNAMODB_ERROR = 'Database operation failed'
    ITEM_NOT_FOUND = 'Item not found in database'
    CONDITION_CHECK_FAILED = 'Condition check failed'


class LogConstants:
    """Logging constants"""
    
    # Log levels
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'
    
    # Log categories
    REQUEST = 'REQUEST'
    RESPONSE = 'RESPONSE'
    DATABASE = 'DATABASE'
    S3 = 'S3'
    VALIDATION = 'VALIDATION'
    PROCESSING = 'PROCESSING'
    
    # Log formats
    LAMBDA_LOG_FORMAT = '[{timestamp}] [{level}] [{category}] {message}'