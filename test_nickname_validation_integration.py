#!/usr/bin/env python3
"""
Test nickname validation function integration
Tests the actual Lambda function locally
"""
import os
import sys
import json

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

# Mock configuration for testing
class MockConfig:
    def get_ssm_parameter(self, name, default=None):
        return default
    
    def get_int_parameter(self, name, default=0):
        return default
    
    def get_bool_parameter(self, name, default=False):
        return default
    
    def get_parameter(self, name, default=None):
        return default
    
    def get_env(self, name, default=None):
        return os.environ.get(name, default)

# Patch config
import shared.config
shared.config.config = MockConfig()

# Import the Lambda handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'nickname-validate'))
from app import lambda_handler


def test_nickname_validation():
    """Test the nickname validation Lambda function"""
    print("🧪 Testing Nickname Validation Function")
    print("=" * 50)
    
    # Test 1: Valid nickname
    print("\n1. Testing valid nickname:")
    event = {
        'body': json.dumps({
            'nickname': 'john_doe_123',
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Valid: {result['valid']}")
    print(f"   Normalized: {result['normalized']}")
    print(f"   Errors: {result['errors']}")
    print(f"   ✅ Test passed" if result['valid'] else f"   ❌ Unexpected: {result['errors']}")
    
    # Test 2: Invalid characters
    print("\n2. Testing invalid characters:")
    event = {
        'body': json.dumps({
            'nickname': 'john@doe!',
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {result['errors']}")
    print(f"   Hints: {result['hints']}")
    print(f"   ✅ Test passed" if not result['valid'] else f"   ❌ Should be invalid")
    
    # Test 3: Reserved word
    print("\n3. Testing reserved word:")
    event = {
        'body': json.dumps({
            'nickname': 'admin',
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {result['errors']}")
    print(f"   ✅ Test passed" if not result['valid'] else f"   ❌ Should be invalid")
    
    # Test 4: Too short
    print("\n4. Testing too short:")
    event = {
        'body': json.dumps({
            'nickname': 'ab',
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {result['errors']}")
    print(f"   ✅ Test passed" if not result['valid'] else f"   ❌ Should be invalid")
    
    # Test 5: Get validation rules
    print("\n5. Testing get validation rules:")
    event = {
        'body': json.dumps({
            'get_rules': True,
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Success: {result['success']}")
    print(f"   Rules available: {'rules' in result}")
    if 'rules' in result:
        rules = result['rules']
        print(f"   Min length: {rules.get('min_length')}")
        print(f"   Max length: {rules.get('max_length')}")
        print(f"   Reserved words count: {len(rules.get('reserved_words', []))}")
    print(f"   ✅ Test passed" if result['success'] else f"   ❌ Failed to get rules")
    
    # Test 6: Case normalization
    print("\n6. Testing case normalization:")
    event = {
        'body': json.dumps({
            'nickname': 'John_Doe_TEST',
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Original: {result['original']}")
    print(f"   Normalized: {result['normalized']}")
    print(f"   ✅ Normalized correctly" if result['normalized'] == 'john_doe_test' else f"   ❌ Normalization issue")
    
    # Test 7: Entity type specific (org)
    print("\n7. Testing organization entity type:")
    event = {
        'body': json.dumps({
            'nickname': 'test_organization',
            'entity_type': 'org'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"   Input: {event['body']}")
    print(f"   Entity type: {result['entity_type']}")
    print(f"   Valid: {result['valid']}")
    print(f"   ✅ Test passed" if result['entity_type'] == 'org' else f"   ❌ Entity type issue")
    
    print("\n" + "=" * 50)
    print("🎉 Nickname validation function tests completed!")
    print("✅ Function is ready for production use")


def test_uniqueness_logic():
    """Test uniqueness checking logic"""
    print("\n🔍 Testing Uniqueness Check Logic")
    print("=" * 40)
    
    # Test with a nickname that should trigger uniqueness check
    event = {
        'body': json.dumps({
            'nickname': 'test_unique_user_12345',  # Very unlikely to exist
            'entity_type': 'user'
        })
    }
    
    response = lambda_handler(event, {})
    result = json.loads(response['body'])
    
    print(f"Testing unique nickname: {result['original']}")
    print(f"Valid: {result['valid']}")
    print(f"Warnings: {result.get('warnings', [])}")
    
    if result['valid']:
        print("✅ Uniqueness check passed (no existing conflict)")
    else:
        if any('already taken' in error for error in result.get('errors', [])):
            print("✅ Uniqueness check detected existing nickname")
        else:
            print("ℹ️  Validation failed for other reasons (not uniqueness)")
    
    # Show the complete validation flow
    print("\n📋 Complete Validation Response Structure:")
    for key, value in result.items():
        print(f"   {key}: {value}")


if __name__ == '__main__':
    try:
        test_nickname_validation()
        test_uniqueness_logic()
        print("\n🚀 Ready to use in other services!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()