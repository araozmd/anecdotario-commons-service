"""
Commons Service Usage Examples
Practical examples for using the nickname validation and user-org services
"""
import boto3
import json
from typing import Dict, Any, Optional


class CommonsServiceUsage:
    """Usage examples for Commons Service functions"""
    
    def __init__(self, environment: str = 'dev'):
        self.lambda_client = boto3.client('lambda')
        self.env = environment
    
    def check_nickname_availability(self, nickname: str, entity_type: str = 'user') -> Dict[str, Any]:
        """
        Check if a nickname is available and valid
        
        Args:
            nickname: The nickname to check (e.g., 'john_doe')
            entity_type: 'user', 'org', or 'campaign'
            
        Returns:
            Full validation result with availability status
            
        Example:
            usage = CommonsServiceUsage('dev')
            result = usage.check_nickname_availability('john_doe', 'user')
            
            if result['valid']:
                print(f"✅ Nickname '{result['normalized']}' is available!")
            else:
                print(f"❌ Issues: {', '.join(result['errors'])}")
                print(f"💡 Suggestions: {', '.join(result['hints'])}")
        """
        payload = {
            'nickname': nickname,
            'entity_type': entity_type
        }
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=f'anecdotario-nickname-validate-{self.env}',
                Payload=json.dumps({'body': json.dumps(payload)})
            )
            
            result = json.loads(response['Payload'].read())
            
            if result['statusCode'] == 200:
                return json.loads(result['body'])
            else:
                return {
                    'valid': False,
                    'error': f"Service error: {result.get('body', 'Unknown error')}",
                    'errors': [f"Service returned status {result['statusCode']}"]
                }
                
        except Exception as e:
            return {
                'valid': False,
                'error': f"Failed to check nickname: {str(e)}",
                'errors': [f"Service unavailable: {str(e)}"]
            }
    
    def is_nickname_available(self, nickname: str, entity_type: str = 'user') -> bool:
        """
        Simple boolean check for nickname availability
        
        Args:
            nickname: The nickname to check
            entity_type: 'user', 'org', or 'campaign'
            
        Returns:
            True if available and valid, False otherwise
            
        Example:
            usage = CommonsServiceUsage('dev')
            if usage.is_nickname_available('john_doe', 'user'):
                print("Nickname is available!")
            else:
                print("Nickname is taken or invalid")
        """
        result = self.check_nickname_availability(nickname, entity_type)
        return result.get('valid', False)
    
    def get_validation_rules(self, entity_type: str = 'user') -> Dict[str, Any]:
        """
        Get validation rules for an entity type
        
        Args:
            entity_type: 'user', 'org', or 'campaign'
            
        Returns:
            Validation rules and constraints
            
        Example:
            usage = CommonsServiceUsage('dev')
            rules = usage.get_validation_rules('user')
            print(f"Min length: {rules['rules']['min_length']}")
            print(f"Reserved words: {rules['rules']['reserved_words']}")
        """
        payload = {
            'get_rules': True,
            'entity_type': entity_type
        }
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=f'anecdotario-nickname-validate-{self.env}',
                Payload=json.dumps({'body': json.dumps(payload)})
            )
            
            result = json.loads(response['Payload'].read())
            return json.loads(result['body']) if result['statusCode'] == 200 else {}
            
        except Exception as e:
            return {'error': f"Failed to get rules: {str(e)}"}
    
    def create_user_or_org(self, nickname: str, full_name: str, user_type: str, **kwargs) -> Dict[str, Any]:
        """
        Create a user or organization entity
        
        Args:
            nickname: Unique nickname (will be validated first)
            full_name: Display name
            user_type: 'user' or 'organization'
            **kwargs: Additional fields (email, phone, website, etc.)
            
        Returns:
            Created entity data or error information
            
        Example:
            usage = CommonsServiceUsage('dev')
            result = usage.create_user_or_org(
                nickname='john_doe',
                full_name='John Doe', 
                user_type='user',
                email='john@example.com'
            )
            
            if 'nickname' in result:
                print(f"✅ User created: {result['nickname']}")
            else:
                print(f"❌ Creation failed: {result.get('error', 'Unknown error')}")
        """
        # First validate the nickname
        validation = self.check_nickname_availability(nickname, user_type)
        if not validation.get('valid', False):
            return {
                'error': 'Nickname validation failed',
                'validation_errors': validation.get('errors', []),
                'suggestions': validation.get('hints', [])
            }
        
        # Create the entity
        payload = {
            'nickname': nickname,
            'full_name': full_name,
            'user_type': user_type,
            **kwargs
        }
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=f'anecdotario-user-org-create-{self.env}',
                Payload=json.dumps({'body': json.dumps(payload)})
            )
            
            result = json.loads(response['Payload'].read())
            return json.loads(result['body']) if result['statusCode'] == 200 else {'error': result.get('body', 'Creation failed')}
            
        except Exception as e:
            return {'error': f"Failed to create entity: {str(e)}"}
    
    def get_entity(self, nickname: str) -> Optional[Dict[str, Any]]:
        """
        Get an existing user or organization by nickname
        
        Args:
            nickname: The nickname to look up
            
        Returns:
            Entity data if found, None if not found
            
        Example:
            usage = CommonsServiceUsage('dev')
            entity = usage.get_entity('john_doe')
            if entity:
                print(f"Found: {entity['full_name']} ({entity['user_type']})")
            else:
                print("Entity not found")
        """
        payload = {'nickname': nickname}
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=f'anecdotario-user-org-get-{self.env}',
                Payload=json.dumps({'body': json.dumps(payload)})
            )
            
            result = json.loads(response['Payload'].read())
            if result['statusCode'] == 200:
                data = json.loads(result['body'])
                return data.get('entity') if data.get('found') else None
            return None
            
        except Exception:
            return None


# Example usage patterns
def example_nickname_checking():
    """Example patterns for nickname validation"""
    usage = CommonsServiceUsage('dev')
    
    # Pattern 1: Simple availability check
    if usage.is_nickname_available('john_doe', 'user'):
        print("✅ Nickname available - proceed with registration")
    else:
        print("❌ Nickname taken - show alternatives")
    
    # Pattern 2: Detailed validation with suggestions
    result = usage.check_nickname_availability('john_doe', 'user')
    if result['valid']:
        print(f"✅ '{result['normalized']}' is available")
    else:
        print("❌ Validation failed:")
        for error in result.get('errors', []):
            print(f"   • {error}")
        
        if result.get('hints'):
            print("💡 Suggestions:")
            for hint in result.get('hints', []):
                print(f"   • {hint}")
    
    # Pattern 3: Get validation rules for frontend
    rules = usage.get_validation_rules('user')
    if 'rules' in rules:
        r = rules['rules']
        print(f"📋 Validation Rules:")
        print(f"   • Length: {r['min_length']}-{r['max_length']} characters")
        print(f"   • Allowed: {r['allowed_characters']}")
        print(f"   • Reserved words: {len(r['reserved_words'])} blocked terms")


def example_entity_creation():
    """Example patterns for entity creation with validation"""
    usage = CommonsServiceUsage('dev')
    
    # Pattern 1: Complete user creation workflow
    def create_user_safely(nickname: str, full_name: str, email: str):
        result = usage.create_user_or_org(
            nickname=nickname,
            full_name=full_name,
            user_type='user',
            email=email,
            created_by='user-service'
        )
        
        if 'error' in result:
            if 'validation_errors' in result:
                return {
                    'success': False,
                    'reason': 'nickname_invalid',
                    'errors': result['validation_errors'],
                    'suggestions': result.get('suggestions', [])
                }
            else:
                return {
                    'success': False,
                    'reason': 'creation_failed', 
                    'error': result['error']
                }
        else:
            return {
                'success': True,
                'user': result,
                'nickname': result.get('nickname')
            }
    
    # Usage
    creation_result = create_user_safely('john_doe', 'John Doe', 'john@example.com')
    if creation_result['success']:
        print(f"✅ User created: {creation_result['nickname']}")
    else:
        print(f"❌ Failed: {creation_result['reason']}")


if __name__ == '__main__':
    print("Commons Service Usage Examples")
    print("=" * 40)
    example_nickname_checking()
    print()
    example_entity_creation()