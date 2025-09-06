"""
Service Container for Dependency Injection
Provides centralized service management and configuration
"""
import boto3
from typing import Dict, Any, Optional, Type, TypeVar
from ..config import config

T = TypeVar('T')


class ServiceContainer:
    """
    Simple service container implementing dependency injection pattern
    Manages service instances and their dependencies
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._config = config
        
        # Register default AWS clients
        self._register_aws_clients()
    
    def _register_aws_clients(self):
        """Register AWS service clients as singletons"""
        self._singletons['s3_client'] = boto3.client('s3')
        self._singletons['lambda_client'] = boto3.client('lambda')
        self._singletons['ssm_client'] = boto3.client('ssm')
    
    def register_singleton(self, name: str, instance: Any) -> None:
        """
        Register a singleton service instance
        
        Args:
            name: Service name
            instance: Service instance
        """
        self._singletons[name] = instance
    
    def register_factory(self, name: str, factory_func: callable) -> None:
        """
        Register a factory function for service creation
        
        Args:
            name: Service name
            factory_func: Function that creates the service instance
        """
        self._services[name] = factory_func
    
    def get(self, name: str) -> Any:
        """
        Get service instance by name
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            KeyError: Service not found
        """
        # Check singletons first
        if name in self._singletons:
            return self._singletons[name]
        
        # Check factories
        if name in self._services:
            return self._services[name]()
        
        raise KeyError(f"Service '{name}' not registered")
    
    def get_or_create(self, name: str, factory_func: callable) -> Any:
        """
        Get service instance or create if not exists
        
        Args:
            name: Service name
            factory_func: Factory function to create service
            
        Returns:
            Service instance
        """
        try:
            return self.get(name)
        except KeyError:
            instance = factory_func()
            self.register_singleton(name, instance)
            return instance
    
    def create_photo_service(self) -> 'PhotoService':
        """
        Factory method for PhotoService with proper dependency injection
        
        Returns:
            Configured PhotoService instance
        """
        from .photo_service import PhotoService
        
        return PhotoService(
            s3_client=self.get('s3_client'),
            config_manager=self._config
        )
    
    def create_user_org_service(self) -> 'UserOrgService':
        """
        Factory method for UserOrgService
        
        Returns:
            Configured UserOrgService instance
        """
        from .user_org_service import UserOrgService
        
        return UserOrgService()
    
    def create_notification_service(self) -> Any:
        """
        Factory method for NotificationService (placeholder for future implementation)
        
        Returns:
            Configured NotificationService instance
        """
        # Placeholder for future notification service
        pass
    
    def create_validation_service(self) -> Any:
        """
        Factory method for ValidationService (placeholder for future implementation)
        
        Returns:
            Configured ValidationService instance
        """
        # Placeholder for future validation service
        pass


# Global service container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """
    Get the global service container instance
    Creates one if it doesn't exist (singleton pattern)
    
    Returns:
        Global ServiceContainer instance
    """
    global _container
    if _container is None:
        _container = ServiceContainer()
        
        # Register default services
        _container.register_factory('photo_service', _container.create_photo_service)
        _container.register_factory('user_org_service', _container.create_user_org_service)
    
    return _container


def get_service(name: str) -> Any:
    """
    Convenience function to get service from global container
    
    Args:
        name: Service name
        
    Returns:
        Service instance
    """
    return get_container().get(name)


def register_service(name: str, instance: Any) -> None:
    """
    Convenience function to register singleton service in global container
    
    Args:
        name: Service name
        instance: Service instance
    """
    get_container().register_singleton(name, instance)


def register_factory(name: str, factory_func: callable) -> None:
    """
    Convenience function to register factory in global container
    
    Args:
        name: Service name
        factory_func: Factory function
    """
    get_container().register_factory(name, factory_func)


def reset_container() -> None:
    """
    Reset the global container (useful for testing)
    """
    global _container
    _container = None