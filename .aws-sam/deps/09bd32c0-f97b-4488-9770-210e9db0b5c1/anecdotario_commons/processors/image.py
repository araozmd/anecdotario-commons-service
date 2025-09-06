"""
Image processing utilities for the photo service
Handles resizing, optimization, and format conversion
"""
import io
from PIL import Image
from PIL.ExifTags import TAGS
from typing import Dict, Tuple
from ..config import config


class ImageProcessor:
    """
    Image processor with Instagram-style multi-version creation
    """
    
    def __init__(self):
        # Load configuration
        self.thumbnail_size = config.get_int_parameter('thumbnail-size', 150)
        self.standard_size = config.get_int_parameter('standard-size', 320)
        self.high_res_size = config.get_int_parameter('high-res-size', 800)
        
        self.thumbnail_quality = config.get_int_parameter('thumbnail-quality', 80)
        self.standard_quality = config.get_int_parameter('standard-quality', 85)
        self.high_res_quality = config.get_int_parameter('high-res-quality', 90)
        
        self.jpeg_quality = config.get_int_parameter('image-jpeg-quality', 85)
        self.enable_webp = config.get_bool_parameter('enable-webp-support', True)
    
    def create_image_versions(self, image_data: bytes) -> Dict[str, bytes]:
        """
        Create multiple versions of an image (Instagram-style)
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dict with version names as keys and processed image bytes as values
            
        Raises:
            ValueError: If image processing fails
        """
        versions = {}
        
        try:
            # Open and process the original image
            image = Image.open(io.BytesIO(image_data))
            
            # Strip EXIF data for privacy and size reduction
            image = self._strip_exif(image)
            
            # Convert to RGB if necessary
            image = self._normalize_format(image)
            
            # Create versions
            version_configs = [
                ('thumbnail', self.thumbnail_size, self.thumbnail_quality),
                ('standard', self.standard_size, self.standard_quality),
                ('high_res', self.high_res_size, self.high_res_quality)
            ]
            
            for version_name, size, quality in version_configs:
                # Create a copy for this version
                version_image = image.copy()
                
                # Process image (crop to square and resize)
                version_image = self._process_to_square(version_image, size)
                
                # Save to bytes
                processed_bytes = self._save_image(version_image, quality)
                versions[version_name] = processed_bytes
            
            return versions
            
        except Exception as e:
            raise ValueError(f"Failed to process image: {str(e)}")
    
    def _strip_exif(self, image: Image.Image) -> Image.Image:
        """
        Strip EXIF data for privacy and size reduction
        
        Args:
            image: PIL Image object
            
        Returns:
            Image without EXIF data
        """
        if hasattr(image, '_getexif') and image._getexif():
            data = list(image.getdata())
            image_without_exif = Image.new(image.mode, image.size)
            image_without_exif.putdata(data)
            return image_without_exif
        return image
    
    def _normalize_format(self, image: Image.Image) -> Image.Image:
        """
        Convert image to RGB format for consistent processing
        
        Args:
            image: PIL Image object
            
        Returns:
            RGB Image object
        """
        if image.mode in ('RGBA', 'LA'):
            # Handle transparency by adding white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'RGBA':
                background.paste(image, mask=image.split()[-1])
            else:  # LA mode
                background.paste(image)
            return background
        elif image.mode not in ('RGB', 'L'):
            return image.convert('RGB')
        return image
    
    def _process_to_square(self, image: Image.Image, target_size: int) -> Image.Image:
        """
        Process image to square aspect ratio (Instagram-style)
        Crops from center if needed, then resizes
        
        Args:
            image: PIL Image object
            target_size: Target size for width and height
            
        Returns:
            Processed square image
        """
        width, height = image.size
        min_dimension = min(width, height)
        
        # Crop to square from center
        left = (width - min_dimension) // 2
        top = (height - min_dimension) // 2
        right = left + min_dimension
        bottom = top + min_dimension
        
        square_image = image.crop((left, top, right, bottom))
        
        # Resize to target size using high-quality resampling
        return square_image.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    def _save_image(self, image: Image.Image, quality: int) -> bytes:
        """
        Save image to bytes with optimization
        
        Args:
            image: PIL Image object
            quality: JPEG quality (1-100)
            
        Returns:
            Optimized image bytes
        """
        output_buffer = io.BytesIO()
        
        # Save as JPEG with optimization
        image.save(
            output_buffer,
            format='JPEG',
            quality=quality,
            optimize=True,
            progressive=True
        )
        
        return output_buffer.getvalue()
    
    def validate_image(self, image_data: bytes) -> Tuple[bool, str]:
        """
        Validate image data and format
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Check format
            if image.format.lower() not in ('jpeg', 'jpg', 'png', 'gif'):
                return False, f"Unsupported format: {image.format}"
            
            # Check dimensions
            width, height = image.size
            if width < 50 or height < 50:
                return False, "Image too small (minimum 50x50 pixels)"
            
            if width > 5000 or height > 5000:
                return False, "Image too large (maximum 5000x5000 pixels)"
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid image: {str(e)}"
    
    def get_image_info(self, image_data: bytes) -> Dict:
        """
        Get image information and metadata
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dict with image information
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            info = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'width': image.size[0],
                'height': image.size[1],
                'has_transparency': image.mode in ('RGBA', 'LA') or 'transparency' in image.info
            }
            
            # Extract EXIF data if present
            if hasattr(image, '_getexif') and image._getexif():
                exif_data = {}
                exif = image._getexif()
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = value
                info['exif'] = exif_data
            
            return info
            
        except Exception as e:
            return {'error': str(e)}


# Global image processor instance
image_processor = ImageProcessor()