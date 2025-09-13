"""
Photo Upload Lambda Function - Request/Response Format Demonstration (Standalone)
================================================================================

This standalone demonstration shows the exact request and response formats for the
photo-upload Lambda function with actual contract structures and dummy data.

No external dependencies required - uses mock contracts to show exact structure.
"""
import json
import base64
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Literal
from PIL import Image
import io


# Mock contract classes to demonstrate exact structure
@dataclass
class PhotoUploadRequest:
    """Mock PhotoUploadRequest contract from anecdotario-commons==1.0.6"""
    image: str
    entity_type: Literal["user", "org", "campaign"]
    entity_id: str
    photo_type: Literal["profile", "logo", "banner", "gallery", "thumbnail"]
    uploaded_by: Optional[str] = None
    upload_source: Optional[Literal["user-service", "org-service", "campaign-service", "api", "admin"]] = None


@dataclass
class PhotoUploadResponse:
    """Mock PhotoUploadResponse contract from anecdotario-commons==1.0.6"""
    success: bool
    photo_id: str
    entity_type: str
    entity_id: str
    photo_type: str
    thumbnail_url: Optional[str] = None
    standard_url: Optional[str] = None
    high_res_url: Optional[str] = None
    versions: Optional[Dict[str, Dict[str, Any]]] = None
    processing_time: Optional[float] = None
    size_reduction: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


def create_minimal_test_image(format='JPEG', color='red') -> str:
    """
    Create a minimal 1x1 pixel test image in base64 format

    Args:
        format: 'JPEG' or 'PNG'
        color: Color for the pixel

    Returns:
        Base64 encoded image with data URL prefix
    """
    # Create minimal 1x1 pixel image
    img = Image.new('RGB', (1, 1), color=color)
    img_buffer = io.BytesIO()
    img.save(img_buffer, format=format, quality=85)
    img_buffer.seek(0)

    # Convert to base64 with data URL prefix
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    mime_type = f'image/{format.lower()}'
    return f'data:{mime_type};base64,{img_base64}'


def demonstrate_request_formats():
    """Demonstrate all request format variations"""
    print("PHOTO UPLOAD REQUEST FORMATS")
    print("=" * 60)

    # Create dummy base64 image (1x1 red pixel)
    test_image = create_minimal_test_image()

    print("1. COMPLETE REQUEST (All fields)")
    print("-" * 30)
    complete_request = PhotoUploadRequest(
        image=test_image,
        entity_type="user",
        entity_id="john_doe_123",
        photo_type="profile",
        uploaded_by="user-456789",
        upload_source="user-service"
    )

    request_dict = asdict(complete_request)
    # Truncate image for display
    display_dict = request_dict.copy()
    display_dict['image'] = f"{test_image[:50]}...[{len(test_image)} chars total]"

    print("JSON Structure:")
    print(json.dumps(display_dict, indent=2))

    print("\n2. MINIMAL REQUEST (Required fields only)")
    print("-" * 40)
    minimal_request = PhotoUploadRequest(
        image=test_image,
        entity_type="org",
        entity_id="acme_corp",
        photo_type="logo"
    )

    minimal_dict = asdict(minimal_request)
    minimal_dict['image'] = f"{test_image[:50]}...[{len(test_image)} chars total]"
    print("JSON Structure:")
    print(json.dumps(minimal_dict, indent=2))

    print("\n3. API GATEWAY FORMAT (wrapped in body)")
    print("-" * 40)
    api_gateway_event = {
        "httpMethod": "POST",
        "path": "/photo-upload",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer jwt-token-here"
        },
        "body": json.dumps({
            "image": test_image,
            "entity_type": "user",
            "entity_id": "alice_smith",
            "photo_type": "profile",
            "uploaded_by": "user-789123",
            "upload_source": "user-service"
        }),
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "abcdef123",
            "stage": "dev"
        }
    }

    # Display with truncated image
    display_api = api_gateway_event.copy()
    body_data = json.loads(display_api['body'])
    body_data['image'] = f"{test_image[:50]}...[{len(test_image)} chars total]"
    display_api['body'] = json.dumps(body_data)

    print("JSON Structure:")
    print(json.dumps(display_api, indent=2))

    print("\n4. DIRECT LAMBDA INVOCATION FORMAT")
    print("-" * 40)
    direct_event = {
        "image": test_image,
        "entity_type": "campaign",
        "entity_id": "summer_2024",
        "photo_type": "banner",
        "uploaded_by": "campaign-admin-456",
        "upload_source": "campaign-service"
    }

    display_direct = direct_event.copy()
    display_direct['image'] = f"{test_image[:50]}...[{len(test_image)} chars total]"
    print("JSON Structure:")
    print(json.dumps(display_direct, indent=2))

    print(f"\nIMAGE DATA STRUCTURE:")
    print(f"- Format: data:[mime-type];base64,[base64-data]")
    print(f"- Example JPEG: data:image/jpeg;base64,/9j/4AAQSkZJRg...")
    print(f"- Example PNG: data:image/png;base64,iVBORw0KGgoAAAA...")
    print(f"- Test image size: {len(test_image)} characters")
    print(f"- Actual image bytes: {len(base64.b64decode(test_image.split(',')[1]))} bytes")


def demonstrate_response_formats():
    """Demonstrate all response format variations"""
    print("\n\nPHOTO UPLOAD RESPONSE FORMATS")
    print("=" * 60)

    print("1. SUCCESS RESPONSE")
    print("-" * 20)

    success_response = PhotoUploadResponse(
        success=True,
        photo_id="user_john_doe_123_profile_1697123456",
        entity_type="user",
        entity_id="john_doe_123",
        photo_type="profile",
        thumbnail_url="https://anecdotario-photos-dev.s3.amazonaws.com/user/john_doe_123/profile/thumbnail_20241012_abc123.jpg",
        standard_url="https://presigned-url.s3.amazonaws.com/user/john_doe_123/profile/standard_20241012_abc123.jpg?expires=1697729856",
        high_res_url="https://presigned-url.s3.amazonaws.com/user/john_doe_123/profile/high_res_20241012_abc123.jpg?expires=1697729856",
        versions={
            "thumbnail": {"size": 2048, "dimensions": "150x150"},
            "standard": {"size": 8192, "dimensions": "320x320"},
            "high_res": {"size": 32768, "dimensions": "800x800"}
        },
        processing_time=1.234,
        size_reduction="85.2% (from 221184 to 32768 bytes)",
        message="Photo uploaded successfully in 1.234s"
    )

    print("JSON Structure:")
    print(json.dumps(success_response.to_dict(), indent=2))

    print("\n2. VALIDATION ERROR RESPONSE")
    print("-" * 30)

    validation_error_response = PhotoUploadResponse(
        success=False,
        photo_id="",
        entity_type="user",
        entity_id="",
        photo_type="profile",
        message="Validation error: Missing required field: image"
    )

    print("JSON Structure:")
    print(json.dumps(validation_error_response.to_dict(), indent=2))

    print("\n3. PROCESSING ERROR RESPONSE")
    print("-" * 30)

    processing_error_response = PhotoUploadResponse(
        success=False,
        photo_id="",
        entity_type="user",
        entity_id="test_user",
        photo_type="profile",
        message="Photo upload failed: Error processing image: cannot identify image file"
    )

    print("JSON Structure:")
    print(json.dumps(processing_error_response.to_dict(), indent=2))

    print("\n4. S3 UPLOAD ERROR RESPONSE")
    print("-" * 30)

    s3_error_response = PhotoUploadResponse(
        success=False,
        photo_id="",
        entity_type="org",
        entity_id="test_org",
        photo_type="logo",
        message="Photo upload failed: Error uploading thumbnail to S3: Access Denied"
    )

    print("JSON Structure:")
    print(json.dumps(s3_error_response.to_dict(), indent=2))


def demonstrate_valid_enum_values():
    """Demonstrate all valid enum values"""
    print("\n\nVALID ENUM VALUES")
    print("=" * 60)

    print("entity_type (Literal):")
    entity_types = ["user", "org", "campaign"]
    for i, entity_type in enumerate(entity_types, 1):
        print(f"  {i}. '{entity_type}'")

    print("\nphoto_type (Literal):")
    photo_types = ["profile", "logo", "banner", "gallery", "thumbnail"]
    for i, photo_type in enumerate(photo_types, 1):
        print(f"  {i}. '{photo_type}'")

    print("\nupload_source (Literal, optional):")
    upload_sources = ["user-service", "org-service", "campaign-service", "api", "admin"]
    for i, source in enumerate(upload_sources, 1):
        print(f"  {i}. '{source}'")

    print("\nCOMBINATION EXAMPLES:")
    print("-" * 20)
    combinations = [
        ("user", "profile", "User profile picture"),
        ("user", "gallery", "User gallery image"),
        ("org", "logo", "Organization logo"),
        ("org", "banner", "Organization banner"),
        ("campaign", "banner", "Campaign banner image"),
        ("campaign", "gallery", "Campaign gallery image")
    ]

    for entity, photo, description in combinations:
        print(f"  {entity} + {photo}: {description}")


def demonstrate_s3_structure():
    """Demonstrate S3 key structure and URL patterns"""
    print("\n\nS3 STRUCTURE AND URL PATTERNS")
    print("=" * 60)

    print("S3 KEY PATTERN:")
    print("{entity_type}/{entity_id}/{photo_type}/{version}_{timestamp}_{unique_id}.jpg")

    print("\nEXAMPLES:")
    print("-" * 10)
    examples = [
        {
            "entity_type": "user",
            "entity_id": "john_doe_123",
            "photo_type": "profile",
            "versions": ["thumbnail", "standard", "high_res"]
        },
        {
            "entity_type": "org",
            "entity_id": "acme_corp",
            "photo_type": "logo",
            "versions": ["thumbnail", "standard", "high_res"]
        },
        {
            "entity_type": "campaign",
            "entity_id": "summer_2024",
            "photo_type": "banner",
            "versions": ["thumbnail", "standard", "high_res"]
        }
    ]

    for example in examples:
        print(f"\n{example['entity_type'].upper()} {example['photo_type'].upper()}:")
        for version in example['versions']:
            key = f"{example['entity_type']}/{example['entity_id']}/{example['photo_type']}/{version}_20241012_abc123.jpg"
            print(f"  {version}: {key}")

    print("\nURL ACCESS PATTERNS:")
    print("-" * 20)
    print("Thumbnail (Public):")
    print("  https://bucket-name.s3.amazonaws.com/user/john_doe/profile/thumbnail_20241012_abc123.jpg")
    print("\nStandard (Presigned, 7-day expiry):")
    print("  https://bucket-name.s3.amazonaws.com/user/john_doe/profile/standard_20241012_abc123.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...")
    print("\nHigh-res (Presigned, 7-day expiry):")
    print("  https://bucket-name.s3.amazonaws.com/user/john_doe/profile/high_res_20241012_abc123.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...")

    print("\nVERSION SPECIFICATIONS:")
    print("-" * 22)
    print("thumbnail: 150x150px, JPEG quality 85%, public access")
    print("standard:  320x320px, JPEG quality 90%, presigned URL")
    print("high_res:  800x800px, JPEG quality 95%, presigned URL")


def demonstrate_environment_variables():
    """Demonstrate required environment variables"""
    print("\n\nREQUIRED ENVIRONMENT VARIABLES")
    print("=" * 60)

    env_vars = [
        {
            "name": "PHOTO_BUCKET_NAME",
            "required": True,
            "example": "anecdotario-photos-dev",
            "description": "S3 bucket for storing photos"
        },
        {
            "name": "AWS_DEFAULT_REGION",
            "required": False,
            "example": "us-east-1",
            "description": "AWS region (defaults to us-east-1)"
        }
    ]

    for var in env_vars:
        status = "REQUIRED" if var["required"] else "OPTIONAL"
        print(f"{var['name']} ({status}):")
        print(f"  Description: {var['description']}")
        print(f"  Example: {var['example']}")
        print()


if __name__ == "__main__":
    print("PHOTO UPLOAD LAMBDA FUNCTION - REQUEST/RESPONSE DEMONSTRATION")
    print("=" * 80)

    demonstrate_request_formats()
    demonstrate_response_formats()
    demonstrate_valid_enum_values()
    demonstrate_s3_structure()
    demonstrate_environment_variables()

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("\nKey Points:")
    print("- Function expects base64 encoded images with data URL prefix")
    print("- Supports user, org, and campaign entities")
    print("- Creates 3 versions: thumbnail (public), standard & high-res (presigned)")
    print("- Uses PhotoUploadRequest/PhotoUploadResponse contracts from anecdotario-commons")
    print("- Handles both API Gateway and direct Lambda invocation formats")
    print("- Returns detailed processing metrics and error messages")
    print("=" * 80)