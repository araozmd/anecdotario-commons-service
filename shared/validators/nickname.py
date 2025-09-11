"""
Database-aware nickname validation for users, orgs, and other entities
"""
import re
from typing import Dict, List, Any, Optional
from ..constants import ValidationConstants, EntityConstants
from ..validation_utils import normalize_nickname
from ..models.user_org import UserOrg
from ..logger import nickname_logger as logger


class NicknameValidator:
    """
    Comprehensive nickname validator with database awareness and detailed feedback
    """
    
    def __init__(self):
        # Reserved words by entity type
        self.reserved_words = {
            'common': ValidationConstants.COMMON_RESERVED_WORDS,
            'user': ValidationConstants.RESERVED_USER_NICKNAMES,
            'org': ValidationConstants.RESERVED_ORG_NICKNAMES,
            'campaign': ValidationConstants.RESERVED_CAMPAIGN_NICKNAMES
        }
        
        # Validation patterns
        self.valid_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
        self.start_pattern = re.compile(r'^[a-zA-Z0-9]')
        self.end_pattern = re.compile(r'[a-zA-Z0-9]$')
        self.consecutive_special = re.compile(r'[-_]{2,}')
        
        # Length limits
        self.min_length = ValidationConstants.MIN_NICKNAME_LENGTH
        self.max_length = ValidationConstants.MAX_NICKNAME_LENGTH
        
        # Profanity and inappropriate content patterns (basic)
        self.inappropriate_patterns = [
            re.compile(r'admin', re.IGNORECASE),
            re.compile(r'root', re.IGNORECASE),
            re.compile(r'test', re.IGNORECASE),
            re.compile(r'null', re.IGNORECASE),
            re.compile(r'undefined', re.IGNORECASE),
        ]
    
    def validate(self, nickname: str, entity_type: str = 'user') -> Dict[str, Any]:
        """
        Comprehensive nickname validation with detailed feedback
        
        Args:
            nickname: Nickname to validate
            entity_type: Type of entity (user, org, campaign)
            
        Returns:
            Validation result with detailed feedback
        """
        original = nickname
        normalized = normalize_nickname(nickname) if nickname else ""
        entity_type = entity_type.lower()
        
        logger.info("Starting nickname validation", 
                   original=original,
                   normalized=normalized,
                   entity_type=entity_type)
        
        result = {
            'valid': False,
            'original': original,
            'normalized': normalized,
            'entity_type': entity_type,
            'errors': [],
            'warnings': [],
            'hints': [],
            'suggestions': []
        }
        
        # Basic validation
        errors = self._validate_basic(normalized)
        result['errors'].extend(errors)
        
        # Pattern validation
        pattern_errors, warnings = self._validate_patterns(normalized)
        result['errors'].extend(pattern_errors)
        result['warnings'].extend(warnings)
        
        # Reserved words check
        reserved_errors = self._check_reserved_words(normalized, entity_type)
        result['errors'].extend(reserved_errors)
        
        # Database availability check (only if no critical errors)
        if not result['errors']:
            availability_error = self._check_availability(normalized)
            if availability_error:
                result['errors'].append(availability_error)
        
        # Generate suggestions if there are errors
        if result['errors']:
            result['suggestions'] = self._generate_suggestions(normalized, entity_type)
        
        # Generate helpful hints
        result['hints'] = self._generate_hints(result['errors'], result['warnings'])
        
        # Final validation
        result['valid'] = len(result['errors']) == 0
        
        logger.info("Nickname validation completed", 
                   nickname=normalized,
                   valid=result['valid'],
                   error_count=len(result['errors']),
                   warning_count=len(result['warnings']))
        
        return result
    
    def _validate_basic(self, nickname: str) -> List[str]:
        """Basic validation checks"""
        errors = []
        
        if not nickname:
            errors.append("Nickname cannot be empty")
            return errors
        
        if len(nickname) < self.min_length:
            errors.append(f"Nickname must be at least {self.min_length} characters long")
        
        if len(nickname) > self.max_length:
            errors.append(f"Nickname must be no more than {self.max_length} characters long")
        
        return errors
    
    def _validate_patterns(self, nickname: str) -> tuple[List[str], List[str]]:
        """Pattern-based validation"""
        errors = []
        warnings = []
        
        if not nickname:
            return errors, warnings
        
        # Check allowed characters
        if not self.valid_pattern.match(nickname):
            errors.append("Nickname can only contain letters, numbers, hyphens (-), and underscores (_)")
        
        # Check start/end characters
        if not self.start_pattern.match(nickname):
            errors.append("Nickname must start with a letter or number")
        
        if not self.end_pattern.match(nickname):
            errors.append("Nickname must end with a letter or number")
        
        # Check consecutive special characters
        if self.consecutive_special.search(nickname):
            errors.append("Nickname cannot contain consecutive hyphens or underscores")
        
        # Check for inappropriate patterns (warnings)
        for pattern in self.inappropriate_patterns:
            if pattern.search(nickname):
                warnings.append(f"Nickname contains potentially inappropriate content: {pattern.pattern}")
        
        # Check for common typing patterns
        if nickname.lower() in ['qwerty', '123456', 'abcdef']:
            warnings.append("Nickname appears to be a common keyboard pattern")
        
        # Check for all numbers
        if nickname.isdigit():
            warnings.append("Nickname with only numbers may be confusing")
        
        return errors, warnings
    
    def _check_reserved_words(self, nickname: str, entity_type: str) -> List[str]:
        """Check against reserved words"""
        errors = []
        
        if not nickname:
            return errors
        
        nickname_lower = nickname.lower()
        
        # Check common reserved words
        if nickname_lower in self.reserved_words['common']:
            errors.append(f"'{nickname}' is a reserved word and cannot be used")
        
        # Check entity-specific reserved words
        if entity_type in self.reserved_words:
            if nickname_lower in self.reserved_words[entity_type]:
                errors.append(f"'{nickname}' is reserved for {entity_type} entities")
        
        return errors
    
    def _check_availability(self, nickname: str) -> Optional[str]:
        """Check if nickname is available in database"""
        try:
            if UserOrg.nickname_exists(nickname):
                return f"Nickname '{nickname}' is already taken"
            
            logger.debug("Nickname availability check passed", nickname=nickname)
            return None
            
        except Exception as e:
            logger.error("Database availability check failed", error=e, nickname=nickname)
            # Don't fail validation due to database issues
            return None
    
    def _generate_suggestions(self, nickname: str, entity_type: str, count: int = 3) -> List[str]:
        """Generate alternative nickname suggestions"""
        suggestions = []
        
        if not nickname:
            base_suggestions = {
                'user': ['user123', 'myusername', 'newuser2024'],
                'org': ['myorg', 'company123', 'organization'],
                'campaign': ['campaign2024', 'mycampaign', 'newcampaign']
            }
            return base_suggestions.get(entity_type, ['suggestion1', 'suggestion2', 'suggestion3'])
        
        # Try variations
        base = re.sub(r'[^a-zA-Z0-9]', '', nickname)[:15]  # Clean and truncate
        
        if base:
            # Add numbers
            for i in [1, 2, 3, 2024, 123]:
                candidate = f"{base}{i}"
                if self._is_valid_suggestion(candidate, entity_type):
                    suggestions.append(candidate)
                    if len(suggestions) >= count:
                        break
            
            # Add underscores
            if len(suggestions) < count:
                for suffix in ['_1', '_new', '_official']:
                    candidate = f"{base}{suffix}"
                    if self._is_valid_suggestion(candidate, entity_type):
                        suggestions.append(candidate)
                        if len(suggestions) >= count:
                            break
            
            # Variations with prefixes
            if len(suggestions) < count:
                prefixes = {
                    'user': ['my', 'the', 'real'],
                    'org': ['official', 'the', 'team'],
                    'campaign': ['project', 'team', 'group']
                }
                
                for prefix in prefixes.get(entity_type, ['my', 'the']):
                    candidate = f"{prefix}_{base}"
                    if self._is_valid_suggestion(candidate, entity_type):
                        suggestions.append(candidate)
                        if len(suggestions) >= count:
                            break
        
        return suggestions[:count]
    
    def _is_valid_suggestion(self, suggestion: str, entity_type: str) -> bool:
        """Check if suggestion is valid (quick check without database)"""
        if not suggestion or len(suggestion) < self.min_length or len(suggestion) > self.max_length:
            return False
        
        if not self.valid_pattern.match(suggestion):
            return False
        
        if not self.start_pattern.match(suggestion) or not self.end_pattern.match(suggestion):
            return False
        
        suggestion_lower = suggestion.lower()
        
        # Check reserved words
        if suggestion_lower in self.reserved_words['common']:
            return False
        
        if entity_type in self.reserved_words and suggestion_lower in self.reserved_words[entity_type]:
            return False
        
        return True
    
    def _generate_hints(self, errors: List[str], warnings: List[str]) -> List[str]:
        """Generate helpful hints based on validation results"""
        hints = []
        
        if not errors and not warnings:
            hints.append("Great! This nickname looks good.")
            return hints
        
        # Hints for common errors
        error_text = ' '.join(errors)
        
        if 'empty' in error_text:
            hints.append("Please enter a nickname to get started")
        
        if 'characters long' in error_text:
            hints.append(f"Nicknames must be between {self.min_length}-{self.max_length} characters")
        
        if 'only contain' in error_text:
            hints.append("Use only letters (a-z), numbers (0-9), hyphens (-), and underscores (_)")
        
        if 'start with' in error_text or 'end with' in error_text:
            hints.append("Nicknames must begin and end with a letter or number")
        
        if 'consecutive' in error_text:
            hints.append("Avoid using multiple hyphens or underscores in a row (like -- or __)")
        
        if 'reserved' in error_text:
            hints.append("Try adding numbers or your name to make it unique")
        
        if 'already taken' in error_text:
            hints.append("This nickname is in use. Try adding numbers or variations")
        
        # General hints if no specific ones apply
        if not hints and errors:
            hints.append("Check the requirements above and try again")
        
        # Hints for warnings
        if warnings and not errors:
            hints.append("Your nickname is valid but consider the suggestions above")
        
        return hints
    
    def get_validation_rules(self, entity_type: str = 'user') -> Dict[str, Any]:
        """
        Get validation rules for frontend display
        
        Args:
            entity_type: Type of entity
            
        Returns:
            Validation rules dictionary
        """
        entity_type = entity_type.lower()
        
        return {
            'min_length': self.min_length,
            'max_length': self.max_length,
            'allowed_characters': 'Letters (a-z), numbers (0-9), hyphens (-), underscores (_)',
            'pattern_rules': [
                'Must start with a letter or number',
                'Must end with a letter or number', 
                'Cannot contain consecutive special characters (-- or __)',
                'Cannot be empty'
            ],
            'reserved_words': {
                'common': list(self.reserved_words['common']),
                entity_type: list(self.reserved_words.get(entity_type, []))
            },
            'examples': {
                'user': ['john_doe', 'user123', 'jane-smith', 'developer2024'],
                'org': ['acme-corp', 'my_company', 'tech_startup', 'nonprofit123'],
                'campaign': ['save_trees', 'campaign2024', 'help-animals', 'clean_ocean']
            }.get(entity_type, ['example1', 'example2', 'example3']),
            'tips': [
                'Keep it simple and memorable',
                'Avoid using personal information',
                'Consider how it will look to others',
                'You can always change it later (in some cases)'
            ]
        }
    
    def quick_validate(self, nickname: str, entity_type: str = 'user') -> bool:
        """
        Quick validation without detailed feedback (for performance)
        
        Args:
            nickname: Nickname to validate
            entity_type: Type of entity
            
        Returns:
            True if valid, False otherwise
        """
        normalized = normalize_nickname(nickname) if nickname else ""
        
        # Basic checks
        if not normalized or len(normalized) < self.min_length or len(normalized) > self.max_length:
            return False
        
        # Pattern checks
        if not (self.valid_pattern.match(normalized) and 
                self.start_pattern.match(normalized) and
                self.end_pattern.match(normalized) and
                not self.consecutive_special.search(normalized)):
            return False
        
        # Reserved words
        normalized_lower = normalized.lower()
        if (normalized_lower in self.reserved_words['common'] or
            normalized_lower in self.reserved_words.get(entity_type, [])):
            return False
        
        # Skip database check for performance
        return True


# Global validator instance
nickname_validator = NicknameValidator()


def validate_nickname(nickname: str, entity_type: str = 'user') -> Dict[str, Any]:
    """
    Validate nickname with detailed feedback
    
    Args:
        nickname: Nickname to validate
        entity_type: Type of entity
        
    Returns:
        Validation result
    """
    return nickname_validator.validate(nickname, entity_type)


def quick_validate_nickname(nickname: str, entity_type: str = 'user') -> bool:
    """
    Quick nickname validation
    
    Args:
        nickname: Nickname to validate
        entity_type: Type of entity
        
    Returns:
        True if valid, False otherwise
    """
    return nickname_validator.quick_validate(nickname, entity_type)