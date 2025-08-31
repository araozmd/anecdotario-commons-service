"""
Nickname Validation Contracts
Function signatures for nickname validation from other services
"""
from typing import Dict, Any, List, Optional


class NicknameContracts:
    """Contract definitions for nickname validation with uniqueness checking"""
    
    @staticmethod
    def validate_nickname(
        nickname: str,
        entity_type: str = 'user'  # 'user', 'org', 'campaign'
    ) -> Dict[str, Any]:
        """
        Comprehensive nickname validation with global uniqueness checking
        
        Lambda: anecdotario-nickname-validate-{env}
        Method: POST
        
        Input Payload:
        {
            "nickname": "john_doe",
            "entity_type": "user"  # 'user', 'org', 'campaign'
        }
        
        Response Format:
        {
            "success": bool,
            "valid": bool,              # True if available and valid
            "original": str,            # Original input nickname
            "normalized": str,          # Lowercase normalized version
            "entity_type": str,         # Entity type used for validation
            "errors": List[str],        # Blocking validation errors
            "warnings": List[str],      # Non-blocking warnings
            "hints": List[str],         # User-friendly suggestions
            "message": str,             # Success/failure message
            "validation_passed": bool,  # Same as 'valid' (backward compatibility)
            "error": str               # Joined error string (backward compatibility)
        }
        
        Validation Rules Applied:
        ✓ Length: 3-30 characters
        ✓ Characters: a-z, 0-9, _ only (normalized to lowercase)
        ✓ No leading/trailing underscores
        ✓ No consecutive underscores (__) 
        ✓ Reserved words blocked (entity-specific lists)
        ✓ Global uniqueness across ALL users & organizations
        ✓ Entity-specific reserved words (admin, api, etc.)
        
        Uniqueness Check:
        - Checks UserOrg table for existing nicknames
        - Case-insensitive comparison
        - Cross-entity validation (users can't use org names, vice versa)
        - Provides alternative suggestions if taken
        
        Error Examples:
        - "Nickname must be at least 3 characters"
        - "Nickname 'admin' is a reserved word"
        - "Nickname 'john_doe' is already taken"
        - "Invalid characters detected. Use only a-z, 0-9, _"
        
        Suggestion Examples:
        - "john_doe1", "john_doe_user", "john_doe2024"
        - "Try adding numbers or modifying to make unique"
        """
        pass
    
    @staticmethod
    def get_validation_rules(
        entity_type: str = 'user'
    ) -> Dict[str, Any]:
        """
        Get validation rules and constraints for entity type
        
        Lambda: anecdotario-nickname-validate-{env}
        Method: POST
        
        Input Payload:
        {
            "get_rules": true,
            "entity_type": "user"
        }
        
        Response Format:
        {
            "success": bool,
            "message": str,
            "entity_type": str,
            "rules": {
                "min_length": int,
                "max_length": int,
                "allowed_characters": str,
                "pattern": str,
                "reserved_words": List[str],
                "examples": {
                    "valid": List[str],
                    "invalid": List[str]
                }
            }
        }
        """
        pass

    # Helper methods for common use cases
    @staticmethod
    def is_nickname_available(nickname: str, entity_type: str = 'user') -> bool:
        """
        Quick availability check - returns True if nickname is available
        
        Usage Example:
        available = NicknameContracts.is_nickname_available('john_doe', 'user')
        """
        # Implementation would call validate_nickname and return result['valid']
        pass
    
    @staticmethod 
    def get_nickname_suggestions(base_nickname: str, entity_type: str = 'user') -> List[str]:
        """
        Get alternative nickname suggestions
        
        Usage Example:
        suggestions = NicknameContracts.get_nickname_suggestions('john_doe', 'user')
        # Returns: ['john_doe1', 'john_doe_user', 'john_doe2024']
        """
        # Implementation would call validate_nickname on taken nickname and return hints
        pass