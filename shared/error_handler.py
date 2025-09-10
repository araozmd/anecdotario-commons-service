"""
AWS error handling utilities for commons-service
"""
import json
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, BotoCoreError
from pynamodb.exceptions import (
    PynamoDBException, DoesNotExist, QueryError, 
    UpdateError, DeleteError, PutError
)
from .constants import HTTPConstants
from .logger import logger


class AWSErrorHandler:
    """
    Centralized AWS error handling for commons-service
    """
    
    @staticmethod
    def handle_dynamodb_error(error: Exception, operation: str, table_name: str = None) -> Dict[str, Any]:
        """
        Handle DynamoDB-related errors
        
        Args:
            error: The exception that occurred
            operation: The operation being performed
            table_name: Optional table name for context
            
        Returns:
            Standardized error response
        """
        error_context = {
            'operation': operation,
            'table_name': table_name or 'unknown',
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        
        if isinstance(error, DoesNotExist):
            logger.warning("DynamoDB item not found", **error_context)
            return {
                'success': False,
                'error_type': 'NotFound',
                'error_message': 'The requested item was not found',
                'status_code': HTTPConstants.NOT_FOUND,
                'retryable': False
            }
        
        elif isinstance(error, (QueryError, UpdateError, DeleteError, PutError)):
            logger.error(f"DynamoDB operation failed: {operation}", error=error, **error_context)
            return {
                'success': False,
                'error_type': 'DatabaseError',
                'error_message': f'Database operation failed: {operation}',
                'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                'retryable': True
            }
        
        elif isinstance(error, PynamoDBException):
            logger.error("PynamoDB error occurred", error=error, **error_context)
            return {
                'success': False,
                'error_type': 'DatabaseError',
                'error_message': 'Database operation failed',
                'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                'retryable': True
            }
        
        elif isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_context['aws_error_code'] = error_code
            
            logger.error("DynamoDB ClientError", error=error, **error_context)
            
            if error_code in ['ThrottlingException', 'ProvisionedThroughputExceededException']:
                return {
                    'success': False,
                    'error_type': 'ThrottlingError',
                    'error_message': 'Database is temporarily busy. Please try again.',
                    'status_code': HTTPConstants.TOO_MANY_REQUESTS,
                    'retryable': True
                }
            elif error_code == 'ResourceNotFoundException':
                return {
                    'success': False,
                    'error_type': 'ResourceNotFound',
                    'error_message': 'Database resource not found',
                    'status_code': HTTPConstants.NOT_FOUND,
                    'retryable': False
                }
            else:
                return {
                    'success': False,
                    'error_type': 'AWSError',
                    'error_message': f'AWS error: {error_code}',
                    'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                    'retryable': True
                }
        
        else:
            logger.error("Unexpected database error", error=error, **error_context)
            return {
                'success': False,
                'error_type': 'DatabaseError',
                'error_message': 'Unexpected database error occurred',
                'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                'retryable': False
            }
    
    @staticmethod
    def handle_s3_error(error: Exception, operation: str, bucket_name: str = None, key: str = None) -> Dict[str, Any]:
        """
        Handle S3-related errors
        
        Args:
            error: The exception that occurred
            operation: The operation being performed
            bucket_name: Optional bucket name for context
            key: Optional S3 key for context
            
        Returns:
            Standardized error response
        """
        error_context = {
            'operation': operation,
            'bucket_name': bucket_name or 'unknown',
            's3_key': key or 'unknown',
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_context['aws_error_code'] = error_code
            
            logger.error("S3 ClientError", error=error, **error_context)
            
            if error_code == 'NoSuchBucket':
                return {
                    'success': False,
                    'error_type': 'BucketNotFound',
                    'error_message': 'Storage bucket not found',
                    'status_code': HTTPConstants.NOT_FOUND,
                    'retryable': False
                }
            elif error_code == 'NoSuchKey':
                return {
                    'success': False,
                    'error_type': 'FileNotFound',
                    'error_message': 'File not found in storage',
                    'status_code': HTTPConstants.NOT_FOUND,
                    'retryable': False
                }
            elif error_code == 'AccessDenied':
                return {
                    'success': False,
                    'error_type': 'AccessDenied',
                    'error_message': 'Access denied to storage resource',
                    'status_code': HTTPConstants.FORBIDDEN,
                    'retryable': False
                }
            elif error_code in ['SlowDown', 'RequestLimitExceeded']:
                return {
                    'success': False,
                    'error_type': 'ThrottlingError',
                    'error_message': 'Storage service is busy. Please try again.',
                    'status_code': HTTPConstants.TOO_MANY_REQUESTS,
                    'retryable': True
                }
            else:
                return {
                    'success': False,
                    'error_type': 'StorageError',
                    'error_message': f'Storage error: {error_code}',
                    'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                    'retryable': True
                }
        
        else:
            logger.error("Unexpected S3 error", error=error, **error_context)
            return {
                'success': False,
                'error_type': 'StorageError',
                'error_message': 'Unexpected storage error occurred',
                'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                'retryable': False
            }
    
    @staticmethod
    def handle_ssm_error(error: Exception, parameter_name: str = None) -> Dict[str, Any]:
        """
        Handle SSM Parameter Store errors
        
        Args:
            error: The exception that occurred
            parameter_name: Optional parameter name for context
            
        Returns:
            Standardized error response
        """
        error_context = {
            'parameter_name': parameter_name or 'unknown',
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_context['aws_error_code'] = error_code
            
            logger.warning("SSM Parameter error", error=error, **error_context)
            
            if error_code == 'ParameterNotFound':
                return {
                    'success': False,
                    'error_type': 'ParameterNotFound',
                    'error_message': f'Configuration parameter not found: {parameter_name}',
                    'status_code': HTTPConstants.NOT_FOUND,
                    'retryable': False
                }
            else:
                return {
                    'success': False,
                    'error_type': 'ConfigurationError',
                    'error_message': f'Configuration error: {error_code}',
                    'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                    'retryable': True
                }
        
        else:
            logger.error("Unexpected SSM error", error=error, **error_context)
            return {
                'success': False,
                'error_type': 'ConfigurationError',
                'error_message': 'Configuration service error',
                'status_code': HTTPConstants.INTERNAL_SERVER_ERROR,
                'retryable': False
            }
    
    @staticmethod
    def handle_validation_error(error: Exception, field_name: str = None) -> Dict[str, Any]:
        """
        Handle validation errors
        
        Args:
            error: The exception that occurred
            field_name: Optional field name for context
            
        Returns:
            Standardized error response
        """
        error_context = {
            'field_name': field_name or 'unknown',
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        
        logger.info("Validation error", **error_context)
        
        return {
            'success': False,
            'error_type': 'ValidationError',
            'error_message': str(error),
            'status_code': HTTPConstants.BAD_REQUEST,
            'retryable': False,
            'field': field_name
        }
    
    @staticmethod
    def create_lambda_error_response(error_data: Dict[str, Any], event: dict = None) -> Dict[str, Any]:
        """
        Create Lambda-compatible error response
        
        Args:
            error_data: Error data from handle_* methods
            event: Original Lambda event for context
            
        Returns:
            Lambda proxy integration response
        """
        response_body = {
            'success': error_data['success'],
            'error': error_data['error_message'],
            'error_type': error_data['error_type'],
            'retryable': error_data.get('retryable', False)
        }
        
        # Add field-specific info for validation errors
        if 'field' in error_data:
            response_body['field'] = error_data['field']
        
        return {
            'statusCode': error_data['status_code'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps(response_body)
        }


# Global error handler instance
error_handler = AWSErrorHandler()