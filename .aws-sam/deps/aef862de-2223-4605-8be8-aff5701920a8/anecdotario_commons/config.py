"""
Configuration manager for Commons Service
Handles hybrid configuration from local .env files and AWS Parameter Store
"""
import os
import boto3
from typing import Optional, Dict, Any, List
from botocore.exceptions import ClientError


class CommonsServiceConfig:
    """
    Configuration manager for Commons Service
    
    Priority order:
    1. Environment variables (highest priority)
    2. AWS Parameter Store 
    3. Local .env files (defaults)
    """
    
    def __init__(self):
        self.ssm = boto3.client('ssm')
        self.parameter_cache = {}
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.parameter_prefix = os.environ.get('PARAMETER_STORE_PREFIX', f'/anecdotario/{self.environment}/commons-service')
        
        # Load local environment defaults
        self._load_env_defaults()
    
    def _load_env_defaults(self):
        """Load configuration from local .env files"""
        env_files = [
            os.path.join(os.path.dirname(__file__), '.env.defaults'),
            os.path.join(os.path.dirname(__file__), f'.env.{self.environment}')
        ]
        
        for env_file in env_files:
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
    
    def get_ssm_parameter(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get parameter from SSM Parameter Store with caching
        
        Args:
            key: Parameter name (without prefix)
            default: Default value if parameter not found
            
        Returns:
            Parameter value or default
        """
        full_key = f"{self.parameter_prefix}/{key}"
        
        # Check cache first
        if full_key in self.parameter_cache:
            return self.parameter_cache[full_key]
        
        try:
            response = self.ssm.get_parameter(Name=full_key, WithDecryption=True)
            value = response['Parameter']['Value']
            self.parameter_cache[full_key] = value
            return value
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                self.parameter_cache[full_key] = default
                return default
            raise
    
    def get_parameter(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get parameter with priority: env var > SSM > default
        
        Args:
            key: Parameter key (will be converted to env var format)
            default: Default value
            
        Returns:
            Parameter value
        """
        # Convert to environment variable format
        env_key = key.upper().replace('-', '_')
        
        # Check environment variable first
        if env_key in os.environ:
            return os.environ[env_key]
        
        # Check SSM Parameter Store
        ssm_value = self.get_ssm_parameter(key, default)
        return ssm_value
    
    def get_int_parameter(self, key: str, default: int = 0) -> int:
        """Get integer parameter"""
        value = self.get_parameter(key, str(default))
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool_parameter(self, key: str, default: bool = False) -> bool:
        """Get boolean parameter"""
        value = self.get_parameter(key, str(default).lower())
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def get_list_parameter(self, key: str, default: List[str] = None, separator: str = ',') -> List[str]:
        """Get list parameter (comma-separated by default)"""
        if default is None:
            default = []
        value = self.get_parameter(key, separator.join(default))
        if not value:
            return default
        return [item.strip() for item in value.split(separator) if item.strip()]


# Global configuration instance
config = CommonsServiceConfig()