"""
Nickname Validation Contracts
Function signatures for nickname validation from other services
"""
from typing import Dict, Any


class NicknameContracts:
    """Contract definitions for nickname validation"""
    
    @staticmethod
    def validate_nickname(
        nickname: str,
        entity_type: str = 'user'  # 'user', 'org', 'campaign'
    ) -> Dict[str, Any]:
        """
        Comprehensive nickname validation with uniqueness checking
        
        Lambda: anecdotario-nickname-validate-{env}
        
        Returns:
        {
            'valid': bool,
            'original': str,
            'normalized': str, 
            'entity_type': str,
            'errors': List[str],     # Blocking issues
            'warnings': List[str],   # Non-blocking issues  
            'hints': List[str]       # User-friendly suggestions
        }
        
        Validation Rules:
        - Length: 3-30 characters
        - Characters: a-z, 0-9, _ only
        - No leading/trailing underscores
        - No consecutive underscores
        - Reserved words blocked (entity-specific)
        - Global uniqueness across users & orgs
        """
        pass