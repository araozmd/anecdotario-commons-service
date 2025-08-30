"""
Nickname validation utilities for the commons service
Used by all services for consistent validation across entity types
Enhanced with robust validation, warnings, and user-friendly hints
"""
import re
from typing import Dict, List
from ..config import config


class NicknameValidator:
    """
    Comprehensive nickname validator with detailed error hints
    Enhanced with the best features from org-service implementation
    """
    
    # Confusing lookalike characters (homoglyphs)
    CONFUSING_CHARS = {
        '0': 'o',  # zero vs letter o
        '1': 'l',  # one vs letter l
        '5': 's',  # five vs letter s
    }
    
    def __init__(self):
        # Load configuration
        self.min_length = config.get_int_parameter('nickname-min-length', 3)
        self.max_length = config.get_int_parameter('nickname-max-length', 30)
        self.enable_confusing_filter = config.get_bool_parameter('enable-confusing-char-filter', True)
        self.enable_reserved_check = config.get_bool_parameter('enable-reserved-word-check', True)
        self.allow_leading_digits = config.get_bool_parameter('allow-leading-digits', False)
    
    def normalize_nickname(self, nickname: str) -> str:
        """
        Normalize nickname for storage and comparison.
        
        Args:
            nickname: Original nickname
            
        Returns:
            Normalized (lowercased, trimmed) nickname
        """
        return nickname.lower().strip()
    
    def validate(self, nickname: str, entity_type: str = 'user') -> Dict:
        """
        Comprehensive nickname validation with detailed feedback.
        Enhanced with separate errors/warnings and normalized version.
        
        Args:
            nickname: The nickname to validate
            entity_type: Type of entity ('user', 'org', 'campaign') for context
            
        Returns:
            Dict with validation results including errors, warnings, and hints
        """
        result = {
            'valid': False,
            'original': nickname,
            'normalized': '',
            'entity_type': entity_type,
            'errors': [],    # Blocking issues
            'warnings': [],  # Non-blocking issues
            'hints': []      # User-friendly suggestions
        }
        
        # Basic cleanup
        nickname = nickname.strip() if nickname else ''
        if not nickname:
            result['errors'].append("Nickname cannot be empty")
            result['hints'].append("Please provide a nickname")
            return result
        
        normalized = self.normalize_nickname(nickname)
        result['normalized'] = normalized
        
        # Rule 1: Length validation
        if len(normalized) < self.min_length:
            result['errors'].append(f"Nickname must be at least {self.min_length} characters long")
            result['hints'].append(f"Try adding more letters or numbers (minimum {self.min_length} characters)")
        elif len(normalized) > self.max_length:
            result['errors'].append(f"Nickname must be {self.max_length} characters or less")
            result['hints'].append(f"Try shortening your nickname (maximum {self.max_length} characters)")
        
        # Rule 2: Character validation
        if not re.match(r'^[a-z0-9_]+$', normalized):
            invalid_chars = [c for c in normalized if not re.match(r'[a-z0-9_]', c)]
            result['errors'].append(f"Invalid characters: {', '.join(set(invalid_chars))}")
            result['hints'].append("Only use lowercase letters (a-z), numbers (0-9), and underscores (_)")
        
        # Rule 3: Underscore rules
        if normalized.startswith('_'):
            result['errors'].append("Nickname cannot start with underscore")
            result['hints'].append("Start with a letter or number instead")
        
        if normalized.endswith('_'):
            result['errors'].append("Nickname cannot end with underscore")
            result['hints'].append("End with a letter or number instead")
        
        if '__' in normalized:
            result['errors'].append("Nickname cannot contain consecutive underscores")
            result['hints'].append("Use single underscores only, like 'my_name' not 'my__name'")
        
        # Rule 4: Case sensitivity check (if original != normalized)
        if nickname != normalized:
            result['warnings'].append("Nickname will be stored as lowercase for uniqueness")
            result['hints'].append(f"Your nickname will appear as '{nickname}' but be unique as '{normalized}'")
        
        # Rule 5: Leading numbers (configurable - error or warning)
        if normalized and normalized[0].isdigit():
            if self.allow_leading_digits:
                result['warnings'].append("Nickname starts with a number")
                result['hints'].append("Starting with a letter may be clearer for users")
            else:
                result['errors'].append("Nickname cannot start with a number")
                result['hints'].append("Nickname must start with a letter (a-z)")
        
        # Rule 6: Confusing lookalikes
        if self.enable_confusing_filter:
            confusing_found = []
            for char, lookalike in self.CONFUSING_CHARS.items():
                if char in normalized:
                    confusing_found.append(f"'{char}' (could be confused with '{lookalike}')")
            
            if confusing_found:
                result['warnings'].append(f"Contains potentially confusing characters: {', '.join(confusing_found)}")
                result['hints'].append("Consider using clearly distinguishable characters to avoid confusion")
        
        # Rule 7: Reserved words check
        if self.enable_reserved_check:
            reserved_words = self._get_reserved_words(entity_type)
            
            if normalized in reserved_words:
                result['errors'].append(f"'{normalized}' is a reserved word and cannot be used")
                if entity_type == 'org':
                    result['hints'].append("Try adding your organization name, like 'mycompany_admin' or 'acme_support'")
                else:
                    result['hints'].append("Try adding numbers or personalizing it, like 'john_admin' or 'admin123'")
            
            # Check for partial matches with reserved words (warnings only)
            for reserved in reserved_words:
                if reserved in normalized and normalized != reserved:
                    # Only warn if reserved word appears as a complete word segment
                    if len(reserved) >= 4 and (normalized.startswith(reserved + '_') or 
                                               normalized.endswith('_' + reserved) or
                                               f'_{reserved}_' in normalized):
                        result['warnings'].append(f"Contains reserved word '{reserved}'")
                        result['hints'].append("This might be confusing - consider a different nickname")
                        break
        
        # Rule 8: Minimum complexity (avoid too simple nicknames)
        if len(set(normalized)) <= 2 and len(normalized) >= 3:
            result['warnings'].append("Nickname has very low complexity")
            result['hints'].append("Consider using more varied characters for a unique identifier")
        
        # Rule 9: All digits check
        if normalized.isdigit():
            result['warnings'].append("Nickname contains only numbers")
            result['hints'].append("Consider adding some letters to make it more memorable")
        
        # Success case
        if not result['errors']:
            result['valid'] = True
            if not result['warnings']:
                result['hints'].append("Great choice! This nickname follows all the rules.")
        
        return result
    
    def _get_reserved_words(self, entity_type: str) -> List[str]:
        """Get reserved words list based on entity type"""
        base_reserved = [
            # Core system words
            'admin', 'administrator', 'api', 'app', 'application',
            'support', 'help', 'system', 'root', 'superuser', 'mod', 'moderator',
            
            # Web/network terms
            'www', 'web', 'mail', 'email', 'smtp', 'pop', 'imap',
            'ftp', 'ssh', 'ssl', 'tls', 'cdn', 'dns', 'http', 'https',
            
            # Authentication & security
            'auth', 'oauth', 'login', 'signin', 'signup', 'register',
            'logout', 'signout', 'password', 'security', 'authentication',
            'verify', 'confirm', 'activate', 'forgot', 'reset',
            
            # Common pages/sections
            'about', 'contact', 'terms', 'privacy', 'legal', 'policy',
            'settings', 'config', 'configuration', 'dashboard', 'profile',
            'account', 'user', 'users', 'home', 'index', 'main',
            
            # Navigation
            'search', 'browse', 'explore', 'discover', 'find',
            
            # Development/deployment
            'dev', 'development', 'test', 'testing', 'stage', 'staging',
            'prod', 'production', 'beta', 'alpha', 'demo', 'debug',
            
            # Programming terms
            'null', 'undefined', 'true', 'false', 'none', 'nil',
            'void', 'empty', 'blank', 'default', 'example', 'sample',
            
            # Status/Info
            'error', 'status', 'health', 'ping', 'info', 'information',
            'news', 'blog', 'feed', 'rss', 'atom',
            
            # Content/Actions
            'post', 'comment', 'reply', 'share', 'like', 'follow', 'unfollow',
            'create', 'edit', 'delete', 'update', 'save', 'cancel',
            
            # Generic/Reserved
            'anonymous', 'guest', 'public', 'private', 'temp', 'tmp',
            'placeholder', 'dummy', 'fake',
            
            # Potential abuse
            'abuse', 'spam', 'phishing', 'scam', 'fraud',
            
            # Anecdotario-specific
            'anecdotario', 'anecdotarios', 'anecdote', 'story', 'stories',
            'campaign', 'campaigns', 'notification', 'notifications',
            'comment', 'comments', 'photo', 'photos', 'image', 'images',
            'upload', 'uploads', 'download', 'downloads'
        ]
        
        # Add entity-specific reserved words
        if entity_type == 'org':
            base_reserved.extend([
                'org', 'organization', 'organizations', 'company', 'companies',
                'team', 'teams', 'group', 'groups', 'official',
                'corp', 'corporation', 'inc', 'llc', 'ltd', 'limited',
                'business', 'enterprise', 'foundation', 'nonprofit',
                'association', 'society', 'club', 'union'
            ])
        elif entity_type == 'campaign':
            base_reserved.extend([
                'event', 'events', 'contest', 'competition', 'challenge',
                'collection', 'submission', 'submissions', 'entry', 'entries'
            ])
        elif entity_type == 'user':
            base_reserved.extend([
                'member', 'members', 'username', 'usernames', 'person', 'people'
            ])
        
        return base_reserved
    
    def get_validation_rules(self, entity_type: str = 'user') -> Dict:
        """
        Get human-readable validation rules for frontend display
        
        Args:
            entity_type: Type of entity for context
            
        Returns:
            Dictionary with validation rules
        """
        reserved_words = self._get_reserved_words(entity_type)
        
        return {
            'length': {
                'min': self.min_length,
                'max': self.max_length,
                'description': f'Must be between {self.min_length} and {self.max_length} characters'
            },
            'characters': {
                'allowed': 'a-z, 0-9, _',
                'description': 'Only lowercase letters, numbers, and underscores'
            },
            'underscores': {
                'rules': [
                    'Cannot start or end with underscore',
                    'No consecutive underscores (__ not allowed)'
                ]
            },
            'case': {
                'description': 'Stored as lowercase for uniqueness, original case preserved for display'
            },
            'reserved': {
                'description': f'Cannot use reserved words like {", ".join(reserved_words[:5])}, etc.',
                'count': len(reserved_words),
                'entity_type': entity_type
            },
            'recommendations': [
                'Start with a letter for clarity' if not self.allow_leading_digits else None,
                'Avoid confusing characters like 0 (zero) vs o (letter)' if self.enable_confusing_filter else None,
                f'Use descriptive names that represent your {entity_type}'
            ],
            'examples': {
                'valid': self._get_valid_examples(entity_type),
                'invalid': ['_user', 'user_', 'user__name', '123user', 'admin', '!!!', 'my org']
            }
        }
    
    def _get_valid_examples(self, entity_type: str) -> List[str]:
        """Get valid example nicknames based on entity type"""
        if entity_type == 'org':
            return ['acme_corp', 'techstartup', 'my_company', 'nonprofit_org']
        elif entity_type == 'campaign':
            return ['summer_2024', 'photo_contest', 'story_collection', 'annual_event']
        else:  # user
            return ['john_doe', 'mary_smith', 'user123', 'creative_writer']


# Global nickname validator instance
nickname_validator = NicknameValidator()