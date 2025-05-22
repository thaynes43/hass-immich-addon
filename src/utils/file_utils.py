"""
Utility functions for file I/O operations.
"""
import logging
import os
import zipfile
from typing import List

logger = logging.getLogger(__name__)

def cleanup_directory(directory: str, file_types: List[str] = None) -> None:
    """
    Delete all files of specified types in a directory.
    
    Args:
        directory: Path to the directory to clean
        file_types: List of file extensions to delete (e.g., ['.jpg', '.mp4']). 
                   If None, deletes all files.
        
    Raises:
        OSError: If directory cannot be accessed or files cannot be deleted
    """
    if not os.path.exists(directory):
        logger.warning(f"Directory {directory} does not exist")
        return
        
    try:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue
                
            # If file_types is specified, only delete matching extensions
            if file_types is not None:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in file_types:
                    continue
                    
            cleanup_file(filepath)
            
        logger.info(f"Successfully cleaned directory: {directory}")
        
    except OSError as e:
        logger.error(f"Failed to clean directory {directory}: {e}")
        raise

def save_binary_data(data: bytes, filepath: str) -> str:
    """
    Save binary data to a file.
    
    Args:
        data: Binary data to save
        filepath: Path where the file should be saved
        
    Returns:
        Path to the saved file
        
    Raises:
        OSError: If file cannot be written
    """
    try:
        with open(filepath, 'wb') as f:
            f.write(data)
        logger.info(f"Successfully saved data to {filepath}")
        return filepath
    except OSError as e:
        logger.error(f"Failed to save file to {filepath}: {e}")
        raise

def extract_zip(zip_path: str, extract_dir: str) -> List[str]:
    """
    Extract a ZIP file to the specified directory.
    
    Args:
        zip_path: Path to the ZIP file
        extract_dir: Directory where files should be extracted
        
    Returns:
        List of paths to extracted files
        
    Raises:
        zipfile.BadZipFile: If ZIP file is invalid
        OSError: If extraction fails
    """
    extracted_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get list of files before extraction
            file_list = zip_ref.namelist()
            
            # Extract all files
            zip_ref.extractall(extract_dir)
            
            # Build list of extracted file paths
            for filename in file_list:
                extracted_path = os.path.join(extract_dir, filename)
                if os.path.isfile(extracted_path):  # Only include files, not directories
                    extracted_files.append(extracted_path)
                    
        logger.info(f"Successfully extracted {len(extracted_files)} files to {extract_dir}")
        return extracted_files
        
    except (zipfile.BadZipFile, OSError) as e:
        logger.error(f"Failed to extract ZIP file {zip_path}: {e}")
        raise

def cleanup_file(filepath: str) -> None:
    """
    Delete a file if it exists.
    
    Args:
        filepath: Path to the file to delete
        
    Raises:
        OSError: If file cannot be deleted
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Successfully deleted {filepath}")
    except OSError as e:
        logger.error(f"Failed to delete file {filepath}: {e}")
        raise 