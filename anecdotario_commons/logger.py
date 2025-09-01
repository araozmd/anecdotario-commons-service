"""
Comprehensive logging strategy for the commons service
Provides structured logging with context, performance metrics, and monitoring integration
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union
from contextlib import contextmanager

# Configure AWS Lambda logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class StructuredLogger:
    """
    Enhanced logger providing structured logging with context,
    performance tracking, and monitoring integration
    """
    
    def __init__(self, name: str, service_name: str = 'commons-service'):
        """
        Initialize structured logger
        
        Args:
            name: Logger name (usually __name__)
            service_name: Name of the service for context
        """
        self.logger = logging.getLogger(name)
        self.service_name = service_name
        self.context = {}
    
    def set_context(self, **kwargs):
        """
        Set context information that will be included in all log messages
        
        Args:
            **kwargs: Context key-value pairs
        """
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear all context information"""
        self.context.clear()
    
    def _log_with_context(self, level: str, message: str, **kwargs):
        """
        Log message with structured context
        
        Args:
            level: Log level (info, warning, error, etc.)
            message: Log message
            **kwargs: Additional context
        """
        # Combine context with additional data
        log_data = {
            'service': self.service_name,
            'timestamp': datetime.utcnow().isoformat(),
            **self.context,
            **kwargs
        }
        
        # Get the logging method
        log_method = getattr(self.logger, level.lower())
        
        # Log with extra data
        log_method(message, extra=log_data)
    
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self._log_with_context('info', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self._log_with_context('warning', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self._log_with_context('error', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context"""
        self._log_with_context('critical', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self._log_with_context('debug', message, **kwargs)
    
    def log_request_start(self, event: Dict[str, Any], context: Any = None):
        """
        Log the start of a Lambda request
        
        Args:
            event: Lambda event object
            context: Lambda context object
        """
        request_info = {
            'event_type': 'request_start',
            'http_method': event.get('httpMethod'),
            'path': event.get('path'),
            'query_params': event.get('queryStringParameters'),
            'has_body': bool(event.get('body')),
            'body_size': len(event.get('body', '')) if event.get('body') else 0,
            'user_agent': event.get('headers', {}).get('User-Agent'),
            'source_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp')
        }
        
        if context:
            request_info.update({
                'function_name': getattr(context, 'function_name', 'unknown'),
                'request_id': getattr(context, 'aws_request_id', 'unknown'),
                'memory_limit': getattr(context, 'memory_limit_in_mb', 'unknown')
            })
        
        self.info("Lambda request started", **request_info)
    
    def log_request_end(self, 
                       response: Dict[str, Any], 
                       duration_ms: float,
                       context: Any = None):
        """
        Log the completion of a Lambda request
        
        Args:
            response: Lambda response object
            duration_ms: Request duration in milliseconds
            context: Lambda context object
        """
        response_info = {
            'event_type': 'request_end',
            'status_code': response.get('statusCode'),
            'response_size': len(str(response.get('body', ''))),
            'duration_ms': round(duration_ms, 2),
            'success': response.get('statusCode', 500) < 400
        }
        
        if context:
            response_info.update({
                'request_id': getattr(context, 'aws_request_id', 'unknown'),
                'remaining_time': getattr(context, 'get_remaining_time_in_millis', lambda: 0)()
            })
        
        # Log as info for successful requests, warning for client errors, error for server errors
        status_code = response.get('statusCode', 500)
        if status_code < 400:
            self.info("Lambda request completed successfully", **response_info)
        elif status_code < 500:
            self.warning("Lambda request completed with client error", **response_info)
        else:
            self.error("Lambda request completed with server error", **response_info)
    
    def log_operation_start(self, operation: str, **kwargs):
        """
        Log the start of a business operation
        
        Args:
            operation: Operation name
            **kwargs: Operation-specific context
        """
        self.info(f"Operation started: {operation}", 
                 event_type='operation_start', 
                 operation=operation, 
                 **kwargs)
    
    def log_operation_end(self, 
                         operation: str, 
                         success: bool = True,
                         duration_ms: Optional[float] = None,
                         **kwargs):
        """
        Log the completion of a business operation
        
        Args:
            operation: Operation name
            success: Whether operation was successful
            duration_ms: Operation duration in milliseconds
            **kwargs: Operation-specific context
        """
        log_data = {
            'event_type': 'operation_end',
            'operation': operation,
            'success': success,
            **kwargs
        }
        
        if duration_ms is not None:
            log_data['duration_ms'] = round(duration_ms, 2)
        
        if success:
            self.info(f"Operation completed successfully: {operation}", **log_data)
        else:
            self.warning(f"Operation failed: {operation}", **log_data)
    
    def log_performance_metric(self, 
                              metric_name: str, 
                              value: Union[int, float],
                              unit: str = 'count',
                              **kwargs):
        """
        Log performance metric
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            **kwargs: Additional context
        """
        self.info(f"Performance metric: {metric_name}", 
                 event_type='metric',
                 metric_name=metric_name,
                 metric_value=value,
                 metric_unit=unit,
                 **kwargs)
    
    def log_business_event(self, event_type: str, **kwargs):
        """
        Log business event (e.g., photo uploaded, entity created)
        
        Args:
            event_type: Type of business event
            **kwargs: Event-specific data
        """
        self.info(f"Business event: {event_type}", 
                 event_type='business_event',
                 business_event_type=event_type,
                 **kwargs)
    
    @contextmanager
    def operation_timer(self, operation: str, **kwargs):
        """
        Context manager for timing operations
        
        Args:
            operation: Operation name
            **kwargs: Operation context
            
        Usage:
            with logger.operation_timer('photo_processing', entity_type='user'):
                # Perform operation
                pass
        """
        start_time = time.time()
        self.log_operation_start(operation, **kwargs)
        
        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.log_operation_end(operation, success, duration_ms, **kwargs)


# Global logger instances
_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str = __name__, service_name: str = 'commons-service') -> StructuredLogger:
    """
    Get or create a structured logger instance
    
    Args:
        name: Logger name (usually __name__)
        service_name: Service name for context
        
    Returns:
        StructuredLogger instance
    """
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name, service_name)
    
    return _loggers[name]


def set_global_context(**kwargs):
    """
    Set context for all loggers
    
    Args:
        **kwargs: Context key-value pairs
    """
    for logger in _loggers.values():
        logger.set_context(**kwargs)


def clear_global_context():
    """Clear context for all loggers"""
    for logger in _loggers.values():
        logger.clear_context()


class RequestLoggingMixin:
    """
    Mixin class to add request logging capabilities to any class
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = get_logger(self.__class__.__module__)
    
    def _log_request_metrics(self, operation: str, **metrics):
        """
        Log request-specific metrics
        
        Args:
            operation: Operation name
            **metrics: Metric key-value pairs
        """
        for metric_name, value in metrics.items():
            self._logger.log_performance_metric(
                f"{operation}_{metric_name}",
                value,
                operation=operation
            )
    
    def _log_business_event(self, event_type: str, **kwargs):
        """
        Log business event
        
        Args:
            event_type: Business event type
            **kwargs: Event context
        """
        self._logger.log_business_event(event_type, **kwargs)


# Convenience functions for Lambda handlers
def log_lambda_request(func):
    """
    Decorator to automatically log Lambda request start and end
    
    Usage:
        @log_lambda_request
        def lambda_handler(event, context):
            return {'statusCode': 200}
    """
    import functools
    
    @functools.wraps(func)
    def wrapper(event, context):
        logger = get_logger(func.__module__)
        
        # Set request context
        logger.set_context(
            function_name=getattr(context, 'function_name', 'unknown'),
            request_id=getattr(context, 'aws_request_id', 'unknown')
        )
        
        # Log request start
        start_time = time.time()
        logger.log_request_start(event, context)
        
        try:
            # Execute handler
            response = func(event, context)
            
            # Log request end
            duration_ms = (time.time() - start_time) * 1000
            logger.log_request_end(response, duration_ms, context)
            
            return response
            
        except Exception as e:
            # Log error and re-raise
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Lambda request failed: {str(e)}", 
                        duration_ms=duration_ms,
                        error_type=type(e).__name__)
            raise
        finally:
            # Clear request context
            logger.clear_context()
    
    return wrapper