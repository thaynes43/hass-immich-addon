"""
Utilities for media file conversion and processing.
"""
import logging
import os
from typing import List
import ffmpeg
from PIL import Image
import pillow_heif

logger = logging.getLogger(__name__)

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

# Supported image and video formats
SUPPORTED_IMAGE_FORMATS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
SUPPORTED_VIDEO_FORMATS = ('.mov', '.mp4')
HEIC_FORMATS = ('.heic', '.heif')

def convert_heic_to_jpg(input_path: str, output_dir: str) -> str:
    """
    Convert a HEIC image file to JPG format.
    
    Args:
        input_path: Path to the input HEIC file
        output_dir: Directory to save the converted JPG
        
    Returns:
        Path to the converted JPG file
        
    Raises:
        OSError: If file operations fail
        Image.UnidentifiedImageError: If image format is not supported
    """
    try:
        # Generate output path with jpg extension
        filename = os.path.splitext(os.path.basename(input_path))[0] + '.jpg'
        output_path = os.path.join(output_dir, filename)
        
        # Open and convert the image
        with Image.open(input_path) as img:
            # Convert to RGB (in case of RGBA)
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as JPEG
            img.save(output_path, 'JPEG', quality=95)
            
        logger.info(f"Converted {input_path} to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to convert {input_path} to JPG: {e}")
        raise

def convert_heic_video_to_mp4(input_path: str, output_dir: str) -> str:
    """
    Convert a HEIC video file to MP4 format using ffmpeg.
    
    Args:
        input_path: Path to the input HEIC video file
        output_dir: Directory to save the converted MP4
        
    Returns:
        Path to the converted MP4 file
        
    Raises:
        ffmpeg.Error: If conversion fails
    """
    try:
        # Generate output path with mp4 extension
        filename = os.path.splitext(os.path.basename(input_path))[0] + '.mp4'
        output_path = os.path.join(output_dir, filename)
        
        # Convert using ffmpeg
        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(stream, output_path)
        ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
        
        logger.info(f"Converted {input_path} to {output_path}")
        return output_path
        
    except ffmpeg.Error as e:
        logger.error(f"Failed to convert {input_path} to MP4: {e.stderr.decode()}")
        raise

def process_media_file(input_path: str, output_dir: str) -> str:
    """
    Process a media file, converting if necessary based on its type.
    
    Args:
        input_path: Path to the input media file
        output_dir: Directory to save the processed file
        
    Returns:
        Path to the processed file
        
    Raises:
        ValueError: If file type is not supported
    """
    # Get file extension (lowercase)
    ext = os.path.splitext(input_path)[1].lower()
    
    if ext in HEIC_FORMATS:
        try:
            # Try image conversion first
            return convert_heic_to_jpg(input_path, output_dir)
        except Image.UnidentifiedImageError:
            # If it fails as an image, try video conversion
            return convert_heic_video_to_mp4(input_path, output_dir)
    elif ext in SUPPORTED_IMAGE_FORMATS or ext in SUPPORTED_VIDEO_FORMATS:
        # Already in supported format, just return the path
        return input_path
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def process_media_files(input_files: List[str], output_dir: str) -> List[str]:
    """
    Process multiple media files, converting them if necessary.
    
    Args:
        input_files: List of paths to input media files
        output_dir: Directory to save the processed files
        
    Returns:
        List of paths to the processed files
    """
    processed_files = []
    for input_file in input_files:
        try:
            processed_path = process_media_file(input_file, output_dir)
            processed_files.append(processed_path)
        except Exception as e:
            logger.error(f"Failed to process {input_file}: {e}")
            # Continue processing other files even if one fails
            continue
    
    return processed_files 