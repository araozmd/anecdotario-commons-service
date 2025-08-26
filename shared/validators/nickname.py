"""
Nickname validation utilities for the commons service
Used by both user-service and org-service for consistent validation
"""
import re
from typing import Optional, Dict, List
from ..config import config


class NicknameValidator:
    """
    Comprehensive nickname validator with detailed error hints
    """
    
    def __init__(self):
        # Load configuration
        self.min_length = config.get_int_parameter('nickname-min-length', 3)
        self.max_length = config.get_int_parameter('nickname-max-length', 30)
        self.enable_confusing_filter = config.get_bool_parameter('enable-confusing-char-filter', True)
        self.enable_reserved_check = config.get_bool_parameter('enable-reserved-word-check', True)
    
    def validate(self, nickname: str, entity_type: str = 'user') -> Optional[Dict[str, List[str]]]:
        """
        Validate nickname format and rules with detailed error hints
        
        Args:
            nickname: The nickname to validate
            entity_type: Type of entity ('user', 'org', etc.) for context
            
        Returns:
            Dict with 'error' and 'hints' if invalid, None if valid
        """
        if not nickname:
            return {
                'error': 'Nickname is required',
                'hints': ['Please provide a nickname']
            }
        
        # Length validation (3-30 characters)
        if len(nickname) < self.min_length:
            return {
                'error': 'Nickname is too short',
                'hints': [f'Nickname must be between {self.min_length}-{self.max_length} characters long']
            }
        
        if len(nickname) > self.max_length:
            return {
                'error': 'Nickname is too long', 
                'hints': [f'Nickname must be between {self.min_length}-{self.max_length} characters long']
            }
        
        # Character validation - only lowercase letters, digits, single underscore
        if not re.match(r'^[a-z0-9_]+$', nickname):
            invalid_chars = set(nickname) - set('abcdefghijklmnopqrstuvwxyz0123456789_')
            if invalid_chars:
                return {
                    'error': 'Nickname contains invalid characters',
                    'hints': [
                        'Only lowercase letters (a-z), digits (0-9), and underscores (_) are allowed',
                        f'Invalid characters found: {", ".join(sorted(invalid_chars))}'
                    ]
                }
        
        # Cannot start with underscore
        if nickname.startswith('_'):
            return {
                'error': 'Nickname cannot start with underscore',
                'hints': ['Nickname must start with a letter (a-z) or digit (0-9)']
            }
        
        # Cannot end with underscore
        if nickname.endswith('_'):
            return {
                'error': 'Nickname cannot end with underscore',
                'hints': ['Nickname must end with a letter (a-z) or digit (0-9)']
            }
        
        # No consecutive underscores
        if '__' in nickname:
            return {
                'error': 'Nickname contains consecutive underscores',
                'hints': ['Only single underscores are allowed (no consecutive underscores like "__")']
            }
        
        # Cannot start with digit (to avoid confusion)
        if nickname[0].isdigit():
            return {
                'error': 'Nickname cannot start with a number',
                'hints': ['Nickname must start with a letter (a-z)']
            }
        
        # Reserved words check (case insensitive, comprehensive list)
        if self.enable_reserved_check:
            reserved_result = self._check_reserved_words(nickname, entity_type)
            if reserved_result:
                return reserved_result
        
        # Check for confusing lookalikes (basic homoglyph filtering)
        if self.enable_confusing_filter:
            confusing_result = self._check_confusing_characters(nickname)
            if confusing_result:
                return confusing_result
        
        return None  # Valid nickname
    
    def _check_reserved_words(self, nickname: str, entity_type: str) -> Optional[Dict[str, List[str]]]:
        """Check if nickname is a reserved word"""
        reserved_words = self._get_reserved_words(entity_type)
        
        if nickname.lower() in reserved_words:
            return {
                'error': 'Nickname is reserved',
                'hints': [
                    f'"{nickname}" is a reserved word and cannot be used',
                    'Please choose a different nickname'
                ]
            }
        
        return None
    
    def _check_confusing_characters(self, nickname: str) -> Optional[Dict[str, List[str]]]:
        """Check for confusing character combinations"""
        confusing_patterns = {
            r'[il1|]': 'Contains confusing characters that look similar (i, l, 1, |)',
            r'[o0]': 'Contains confusing characters that look similar (o, 0)',
            r'rn': 'Contains "rn" which can be confused with "m"',
            r'[vw]': 'Contains characters that can be visually confused (v, w)'
        }
        
        for pattern, message in confusing_patterns.items():
            if re.search(pattern, nickname):
                return {
                    'error': 'Nickname contains potentially confusing characters',
                    'hints': [message, 'Please choose characters that are clearly distinguishable']
                }
        
        return None
    
    def _get_reserved_words(self, entity_type: str) -> List[str]:
        """Get reserved words list based on entity type"""
        base_reserved = [
            # System/Admin
            'admin', 'administrator', 'root', 'system', 'user', 'mod', 'moderator',
            
            # Technical
            'api', 'www', 'ftp', 'mail', 'email', 'smtp', 'pop', 'imap',
            'dns', 'ssl', 'tls', 'http', 'https', 'tcp', 'udp', 'ip',
            
            # Support/Contact
            'support', 'help', 'info', 'contact', 'service', 'team',
            
            # Navigation/Pages
            'about', 'profile', 'settings', 'account', 'dashboard', 'home',
            'search', 'browse', 'explore', 'discover',
            
            # Authentication
            'login', 'register', 'signup', 'signin', 'logout', 'signout',
            'password', 'forgot', 'reset', 'verify', 'confirm', 'activate',
            
            # Content/Actions
            'post', 'comment', 'reply', 'share', 'like', 'follow', 'unfollow',
            'create', 'edit', 'delete', 'update', 'save', 'cancel',
            
            # Testing/Development
            'test', 'demo', 'example', 'sample', 'debug', 'staging', 'dev',
            
            # Generic/Reserved
            'null', 'undefined', 'none', 'empty', 'blank', 'default',
            'anonymous', 'guest', 'public', 'private', 'temp', 'tmp',
            
            # Anecdotario-specific
            'anecdotario', 'anecdote', 'story', 'campaign', 'organization', 'org',
            'notification', 'comment', 'photo', 'image', 'upload'
        ]
        
        # Add entity-specific reserved words
        if entity_type == 'org':
            base_reserved.extend([
                'company', 'corp', 'corporation', 'inc', 'llc', 'ltd',
                'business', 'enterprise', 'group', 'foundation', 'nonprofit'
            ])
        elif entity_type == 'user':
            base_reserved.extend([
                'profile', 'account', 'member', 'username'
            ])
        
        return base_reserved
    
    def get_validation_rules(self, entity_type: str = 'user') -> Dict[str, any]:
        """
        Get validation rules for frontend display
        
        Args:
            entity_type: Type of entity for context
            
        Returns:
            Dict with validation rules
        """
        return {
            'length': {
                'min': self.min_length,
                'max': self.max_length,
                'description': f'Must be {self.min_length}-{self.max_length} characters long'
            },
            'characters': {
                'allowed': 'a-z, 0-9, _',
                'description': 'Only lowercase letters, digits, and underscores allowed'
            },
            'format': {
                'start': 'Must start with a letter (a-z)',
                'end': 'Must end with a letter or digit',
                'underscores': 'Single underscores only (no consecutive or at start/end)'
            },
            'restrictions': {
                'no_leading_digits': 'Cannot start with a number',
                'reserved_words': f'Cannot use reserved words ({len(self._get_reserved_words(entity_type))} words)',
                'confusing_chars': 'Avoid confusing character combinations' if self.enable_confusing_filter else None
            },
            'examples': {
                'valid': ['john_doe', 'mycompany', 'user_name'],
                'invalid': ['John', '_user', 'user_', 'user__name', '123user', 'admin']
            }
        }


# Global nickname validator instance
nickname_validator = NicknameValidator()