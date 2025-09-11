"""
Image processing utilities using Pillow
Handles resizing, optimization, and format conversion for photos
"""
import io
from typing import Dict, Tuple, Any, Optional
from PIL import Image, ImageOps, ImageFilter, ExifTags
from ..constants import ImageConstants
from ..logger import logger
from ..config import config


class ImageProcessor:
    """
    Image processing service using Pillow with Instagram-style square cropping
    """
    
    def __init__(self):
        self.max_size = config.max_image_size
        self.allowed_formats = ['JPEG', 'PNG', 'WEBP']
        self.output_format = 'JPEG'
        self.output_quality = ImageConstants.STANDARD_QUALITY
    
    def process_image(self, image_data: bytes, versions: Dict[str, Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        Process image into multiple versions with square cropping
        
        Args:
            image_data: Raw image bytes
            versions: Dictionary of version_name -> (width, height) tuples
                     Default: thumbnail (150x150), standard (320x320), high_res (800x800)
        
        Returns:
            Dictionary containing processed image data for each version
        """
        if versions is None:
            versions = {
                'thumbnail': ImageConstants.THUMBNAIL_SIZE,
                'standard': ImageConstants.STANDARD_SIZE,
                'high_res': ImageConstants.HIGH_RES_SIZE
            }
        
        try:
            # Load and validate image
            original_image = self._load_and_validate_image(image_data)
            
            # Get original image info
            original_size = original_image.size
            original_format = original_image.format
            original_mode = original_image.mode
            
            logger.info("Image processing started", 
                       original_size=original_size, 
                       original_format=original_format,
                       original_mode=original_mode,
                       versions=list(versions.keys()))
            
            results = {
                'original_info': {
                    'size': original_size,
                    'format': original_format,
                    'mode': original_mode,
                    'file_size': len(image_data)
                },
                'versions': {},
                'processing_stats': {}
            }
            
            # Process each version
            for version_name, target_size in versions.items():
                try:
                    processed_data, stats = self._process_version(original_image, target_size)
                    
                    results['versions'][version_name] = processed_data
                    results['processing_stats'][version_name] = stats
                    
                    logger.debug(f"Version {version_name} processed successfully", 
                                version=version_name, 
                                target_size=target_size,
                                output_size=stats['output_size'])
                
                except Exception as e:
                    logger.error(f"Failed to process version {version_name}", 
                               error=e, 
                               version=version_name,
                               target_size=target_size)
                    # Continue processing other versions
                    continue
            
            if not results['versions']:
                raise ValueError("No image versions could be processed")
            
            logger.info("Image processing completed", 
                       versions_created=len(results['versions']),
                       total_reduction=self._calculate_total_reduction(results))
            
            return results
        
        except Exception as e:
            logger.error("Image processing failed", error=e)
            raise ValueError(f"Image processing failed: {str(e)}")
    
    def _load_and_validate_image(self, image_data: bytes) -> Image.Image:
        """
        Load image from bytes and perform validation
        
        Args:
            image_data: Raw image bytes
        
        Returns:
            PIL Image object
        
        Raises:
            ValueError: If image is invalid or unsupported
        """
        if len(image_data) > self.max_size:
            raise ValueError(f"Image too large: {len(image_data)} bytes (max: {self.max_size})")
        
        try:
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            raise ValueError(f"Invalid image data: {str(e)}")
        
        # Validate format
        if image.format not in self.allowed_formats:
            logger.warning("Unsupported image format, converting", 
                          original_format=image.format,
                          supported_formats=self.allowed_formats)
        
        # Auto-rotate based on EXIF orientation
        image = self._auto_rotate_image(image)
        
        # Convert to RGB if needed (for JPEG output)
        if image.mode in ('RGBA', 'P', 'L', 'LA'):
            # Handle transparency by adding white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image
    
    def _auto_rotate_image(self, image: Image.Image) -> Image.Image:
        """
        Auto-rotate image based on EXIF orientation data
        
        Args:
            image: PIL Image object
        
        Returns:
            Rotated image
        """
        try:
            # Get EXIF data
            exif = image._getexif()
            if exif is not None:
                # Find orientation tag
                orientation_key = None
                for tag, value in ExifTags.TAGS.items():
                    if value == 'Orientation':
                        orientation_key = tag
                        break
                
                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    
                    # Apply rotation based on orientation
                    if orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)
                    
                    logger.debug("Image auto-rotated based on EXIF", orientation=orientation)
        
        except (AttributeError, KeyError, TypeError):
            # No EXIF data or orientation info
            pass
        
        return image
    
    def _process_version(self, image: Image.Image, target_size: Tuple[int, int]) -> Tuple[bytes, Dict[str, Any]]:
        """
        Process single image version with square cropping and optimization
        
        Args:
            image: Original PIL Image
            target_size: Target (width, height) tuple
        
        Returns:
            Tuple of (processed_image_bytes, processing_stats)
        """
        target_width, target_height = target_size
        
        # Create square crop (Instagram-style)
        processed_image = self._create_square_crop(image, target_width)
        
        # Apply optimization
        processed_image = self._optimize_image(processed_image)
        
        # Convert to bytes
        output_buffer = io.BytesIO()
        processed_image.save(
            output_buffer, 
            format=self.output_format, 
            quality=self.output_quality,
            optimize=True
        )
        
        processed_bytes = output_buffer.getvalue()
        
        # Calculate statistics
        stats = {
            'input_size': image.size,
            'output_size': processed_image.size,
            'target_size': target_size,
            'file_size': len(processed_bytes),
            'compression_ratio': len(processed_bytes) / (image.size[0] * image.size[1] * 3),  # Rough estimate
            'format': self.output_format,
            'quality': self.output_quality
        }
        
        return processed_bytes, stats
    
    def _create_square_crop(self, image: Image.Image, target_size: int) -> Image.Image:
        """
        Create square crop with center focus (Instagram-style)
        
        Args:
            image: PIL Image object
            target_size: Target square size (width = height)
        
        Returns:
            Square cropped and resized image
        """
        width, height = image.size
        
        # Determine crop area for square (center crop)
        if width > height:
            # Landscape: crop width to match height
            left = (width - height) // 2
            top = 0
            right = left + height
            bottom = height
        else:
            # Portrait or square: crop height to match width
            left = 0
            top = (height - width) // 2
            right = width
            bottom = top + width
        
        # Crop to square
        square_image = image.crop((left, top, right, bottom))
        
        # Resize to target size with high-quality resampling
        resized_image = square_image.resize(
            (target_size, target_size), 
            Image.Resampling.LANCZOS
        )
        
        return resized_image
    
    def _optimize_image(self, image: Image.Image) -> Image.Image:
        """
        Apply optimization techniques to reduce file size while maintaining quality
        
        Args:
            image: PIL Image object
        
        Returns:
            Optimized image
        """
        # Apply slight sharpening for small images (thumbnails)
        if image.size[0] <= 150:
            image = image.filter(ImageFilter.UnsharpMask(radius=0.5, percent=50, threshold=0))
        
        return image
    
    def _calculate_total_reduction(self, results: Dict[str, Any]) -> str:
        """
        Calculate total size reduction across all versions
        
        Args:
            results: Processing results dictionary
        
        Returns:
            Size reduction percentage as string
        """
        original_size = results['original_info']['file_size']
        total_processed_size = sum(
            stats['file_size'] for stats in results['processing_stats'].values()
        )
        
        if original_size == 0:
            return "0.0%"
        
        # Calculate reduction (note: total might be larger for multiple versions)
        if total_processed_size < original_size:
            reduction = (1 - total_processed_size / original_size) * 100
            return f"{reduction:.1f}%"
        else:
            increase = (total_processed_size / original_size - 1) * 100
            return f"-{increase:.1f}%"  # Negative indicates size increase
    
    def validate_image_data(self, image_data: bytes) -> Dict[str, Any]:
        """
        Validate image data without processing
        
        Args:
            image_data: Raw image bytes
        
        Returns:
            Validation result with image info
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            return {
                'valid': True,
                'format': image.format,
                'size': image.size,
                'mode': image.mode,
                'file_size': len(image_data),
                'within_size_limit': len(image_data) <= self.max_size
            }
        
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'file_size': len(image_data),
                'within_size_limit': len(image_data) <= self.max_size
            }


# Global image processor instance
image_processor = ImageProcessor()


def process_image(image_data: bytes, versions: Dict[str, Tuple[int, int]] = None) -> Dict[str, Any]:
    """
    Process image data into multiple versions
    
    Args:
        image_data: Raw image bytes
        versions: Optional version specifications
    
    Returns:
        Processing results
    """
    return image_processor.process_image(image_data, versions)


def validate_image(image_data: bytes) -> Dict[str, Any]:
    """
    Validate image data
    
    Args:
        image_data: Raw image bytes
    
    Returns:
        Validation results
    """
    return image_processor.validate_image_data(image_data)