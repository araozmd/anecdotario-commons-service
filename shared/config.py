"""
Configuration management for commons-service
Supports environment variables, SSM Parameter Store, and local .env files
"""
import os
import json
from typing import Optional, Any, Dict
from functools import lru_cache
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class Config:
    """
    Configuration manager with hybrid approach:
    1. Environment Variables (highest priority)
    2. AWS Parameter Store (environment-specific)
    3. Local defaults (development fallback)
    """
    
    def __init__(self):
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.parameter_store_prefix = os.environ.get(
            'PARAMETER_STORE_PREFIX', 
            f'/anecdotario/{self.environment}/commons-service'
        )
        self._ssm_client = None
        self._parameter_cache = {}
    
    @property
    def ssm_client(self):
        """Lazy initialization of SSM client"""
        if self._ssm_client is None:
            try:
                self._ssm_client = boto3.client('ssm')
            except (NoCredentialsError, Exception):
                # For local development or testing without AWS credentials
                self._ssm_client = None
        return self._ssm_client
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get configuration parameter with fallback hierarchy:
        1. Environment variable
        2. SSM Parameter Store
        3. Default value
        """
        # Try environment variable first (with commons service prefix)
        env_key = f"COMMONS_SERVICE_{key.upper().replace('-', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value
        
        # Try standard environment variable
        env_value = os.environ.get(key.upper().replace('-', '_'))
        if env_value is not None:
            return env_value
        
        # Try SSM Parameter Store
        ssm_value = self.get_ssm_parameter(key)
        if ssm_value is not None:
            return ssm_value
        
        # Return default
        return default
    
    @lru_cache(maxsize=128)
    def get_ssm_parameter(self, key: str) -> Optional[str]:
        """
        Get parameter from AWS SSM Parameter Store with caching
        """
        if not self.ssm_client:
            return None
        
        parameter_name = f"{self.parameter_store_prefix}/{key}"
        
        try:
            response = self.ssm_client.get_parameter(Name=parameter_name)
            value = response['Parameter']['Value']
            return value
        except ClientError as e:
            if e.response['Error']['Code'] != 'ParameterNotFound':
                print(f"Error getting SSM parameter {parameter_name}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error getting SSM parameter {parameter_name}: {e}")
            return None
    
    def get_int_parameter(self, key: str, default: int = 0) -> int:
        """Get integer parameter"""
        value = self.get_parameter(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool_parameter(self, key: str, default: bool = False) -> bool:
        """Get boolean parameter"""
        value = self.get_parameter(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return default
    
    def get_json_parameter(self, key: str, default: dict = None) -> dict:
        """Get JSON parameter"""
        value = self.get_parameter(key)
        if value is None:
            return default or {}
        
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value
        except (json.JSONDecodeError, TypeError):
            return default or {}
    
    def get_list_parameter(self, key: str, default: list = None, separator: str = ',') -> list:
        """Get list parameter (comma-separated string)"""
        value = self.get_parameter(key)
        if value is None:
            return default or []
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, str):
            return [item.strip() for item in value.split(separator) if item.strip()]
        
        return default or []
    
    # Common configuration getters
    @property
    def photo_table_name(self) -> str:
        """Get photo table name"""
        return self.get_parameter('photo-table-name', f'Photos-{self.environment}')
    
    @property
    def photo_bucket_name(self) -> str:
        """Get photo bucket name"""
        return self.get_parameter('photo-bucket-name', f'anecdotario-photos-{self.environment}')
    
    @property
    def user_org_table_name(self) -> str:
        """Get user-org table name"""
        return self.get_parameter('user-org-table-name', f'UserOrg-{self.environment}')
    
    @property
    def max_image_size(self) -> int:
        """Get maximum image size in bytes"""
        return self.get_int_parameter('max-image-size', 5 * 1024 * 1024)  # 5MB
    
    @property
    def allowed_image_types(self) -> list:
        """Get allowed image MIME types"""
        return self.get_list_parameter('allowed-image-types', ['image/jpeg', 'image/png', 'image/webp'])
    
    @property
    def presigned_url_expiry(self) -> int:
        """Get presigned URL expiry in seconds"""
        return self.get_int_parameter('presigned-url-expiry', 604800)  # 7 days
    
    @property
    def enable_debug_logging(self) -> bool:
        """Get debug logging flag"""
        return self.get_bool_parameter('enable-debug-logging', False)
    
    @property
    def cors_allowed_origins(self) -> list:
        """Get CORS allowed origins"""
        if self.environment == 'dev':
            return ['*']
        return self.get_list_parameter('allowed-origins', [f'https://{self.environment}.anecdotario.com', 'https://anecdotario.com'])


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get global configuration instance"""
    return config


def get_env_var(key: str, default: str = None) -> str:
    """
    Simple environment variable getter with commons-service namespace
    
    Args:
        key: Configuration key
        default: Default value if not found
        
    Returns:
        Configuration value
    """
    return config.get_parameter(key, default)