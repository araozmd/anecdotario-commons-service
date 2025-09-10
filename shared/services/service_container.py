"""
Service container for dependency injection
"""
from typing import Dict, Any
from .photo_service import PhotoService
from .user_org_service import UserOrgService


class ServiceContainer:
    """
    Simple service container for dependency injection
    Provides lazy loading of services to avoid circular imports
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
    
    def get_service(self, service_name: str):
        """
        Get service instance with lazy initialization
        
        Args:
            service_name: Name of the service to retrieve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
        """
        if service_name not in self._services:
            self._services[service_name] = self._create_service(service_name)
        
        return self._services[service_name]
    
    def _create_service(self, service_name: str):
        """
        Create service instance
        
        Args:
            service_name: Name of service to create
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is unknown
        """
        if service_name == 'photo_service':
            return PhotoService()
        elif service_name == 'user_org_service':
            return UserOrgService()
        else:
            raise ValueError(f"Unknown service: {service_name}")
    
    def register_service(self, service_name: str, service_instance):
        """
        Register a service instance
        
        Args:
            service_name: Name of the service
            service_instance: Service instance to register
        """
        self._services[service_name] = service_instance
    
    def clear_services(self):
        """Clear all cached services (useful for testing)"""
        self._services.clear()


# Global service container instance
_service_container = ServiceContainer()


def get_service(service_name: str):
    """
    Get service from global container
    
    Args:
        service_name: Name of service to retrieve
        
    Returns:
        Service instance
    """
    return _service_container.get_service(service_name)


def register_service(service_name: str, service_instance):
    """
    Register service in global container
    
    Args:
        service_name: Name of the service
        service_instance: Service instance to register
    """
    _service_container.register_service(service_name, service_instance)


def clear_services():
    """Clear all services (useful for testing)"""
    _service_container.clear_services()