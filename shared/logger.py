"""
CloudWatch logging utilities for commons-service
"""
import json
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from .config import config


class CommonsLogger:
    """
    Structured logger for commons-service with CloudWatch optimization
    """
    
    def __init__(self, service_name: str = "commons-service"):
        self.service_name = service_name
        self.environment = config.environment
        self.debug_enabled = config.enable_debug_logging
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal log method with structured format"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.upper(),
            'service': self.service_name,
            'environment': self.environment,
            'message': message
        }
        
        # Add any additional context
        if kwargs:
            log_entry.update(kwargs)
        
        # Print to stdout (CloudWatch will capture this)
        print(json.dumps(log_entry))
    
    def debug(self, message: str, **kwargs):
        """Log debug message (only if debug enabled)"""
        if self.debug_enabled:
            self._log('debug', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log('info', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log('warning', message, **kwargs)
    
    def warn(self, message: str, **kwargs):
        """Alias for warning"""
        self.warning(message, **kwargs)
    
    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with optional exception details"""
        log_data = kwargs.copy()
        
        if error:
            log_data['error_type'] = type(error).__name__
            log_data['error_message'] = str(error)
            log_data['traceback'] = traceback.format_exc()
        
        self._log('error', message, **log_data)
    
    def critical(self, message: str, error: Exception = None, **kwargs):
        """Log critical message"""
        log_data = kwargs.copy()
        
        if error:
            log_data['error_type'] = type(error).__name__
            log_data['error_message'] = str(error)
            log_data['traceback'] = traceback.format_exc()
        
        self._log('critical', message, **log_data)
    
    def log_lambda_start(self, function_name: str, event: dict, context = None):
        """Log Lambda function start"""
        log_data = {
            'function_name': function_name,
            'request_id': getattr(context, 'aws_request_id', 'unknown') if context else 'unknown',
            'event_keys': list(event.keys()) if isinstance(event, dict) else 'non-dict',
        }
        
        # Add safe event data (avoid logging sensitive information)
        if isinstance(event, dict):
            safe_event = {}
            for key, value in event.items():
                if key.lower() in ['image', 'password', 'token', 'secret', 'key']:
                    safe_event[key] = '[REDACTED]'
                elif isinstance(value, (str, int, float, bool)):
                    safe_event[key] = value
                else:
                    safe_event[key] = str(type(value).__name__)
            log_data['event'] = safe_event
        
        self._log('info', f"Lambda function {function_name} started", **log_data)
    
    def log_lambda_end(self, function_name: str, success: bool = True, duration_ms: float = None, **kwargs):
        """Log Lambda function completion"""
        log_data = {
            'function_name': function_name,
            'success': success,
        }
        
        if duration_ms is not None:
            log_data['duration_ms'] = round(duration_ms, 2)
        
        log_data.update(kwargs)
        
        level = 'info' if success else 'error'
        message = f"Lambda function {function_name} {'completed' if success else 'failed'}"
        
        self._log(level, message, **log_data)
    
    def log_service_operation(self, operation: str, entity_type: str = None, entity_id: str = None, **kwargs):
        """Log service operation"""
        log_data = {
            'operation': operation
        }
        
        if entity_type:
            log_data['entity_type'] = entity_type
        
        if entity_id:
            log_data['entity_id'] = entity_id
        
        log_data.update(kwargs)
        
        self._log('info', f"Service operation: {operation}", **log_data)
    
    def log_database_operation(self, table_name: str, operation: str, success: bool = True, **kwargs):
        """Log database operation"""
        log_data = {
            'table_name': table_name,
            'operation': operation,
            'success': success
        }
        
        log_data.update(kwargs)
        
        level = 'info' if success else 'error'
        message = f"Database {operation} on {table_name} {'succeeded' if success else 'failed'}"
        
        self._log(level, message, **log_data)
    
    def log_s3_operation(self, bucket_name: str, operation: str, key: str = None, success: bool = True, **kwargs):
        """Log S3 operation"""
        log_data = {
            'bucket_name': bucket_name,
            'operation': operation,
            'success': success
        }
        
        if key:
            log_data['s3_key'] = key
        
        log_data.update(kwargs)
        
        level = 'info' if success else 'error'
        message = f"S3 {operation} on {bucket_name} {'succeeded' if success else 'failed'}"
        
        self._log(level, message, **log_data)


# Global logger instances
logger = CommonsLogger("commons-service")
photo_logger = CommonsLogger("photo-service")
nickname_logger = CommonsLogger("nickname-service")
user_org_logger = CommonsLogger("user-org-service")


def get_logger(service_name: str = "commons-service") -> CommonsLogger:
    """Get logger instance for specific service"""
    return CommonsLogger(service_name)