"""Utility script to resize icons and images for the Hive MCP Gateway."""

import os
from PIL import Image
import logging

logger = logging.getLogger(__name__)

def resize_image(input_path, output_path, size):
    """
    Resize an image to the specified size.
    
    Args:
        input_path (str): Path to the input image
        output_path (str): Path to save the resized image
        size (tuple): Target size as (width, height)
    """
    try:
        with Image.open(input_path) as img:
            # Resize the image
            resized_img = img.resize(size, Image.Resampling.LANCZOS)
            
            # Save the resized image
            resized_img.save(output_path)
            
            logger.info(f"Resized {input_path} to {size} and saved as {output_path}")
            return True
    except Exception as e:
        logger.error(f"Error resizing image {input_path}: {e}")
        return False

def create_multiple_sizes(input_path, output_prefix, sizes):
    """
    Create multiple sizes of an image.
    
    Args:
        input_path (str): Path to the input image
        output_prefix (str): Prefix for output files (e.g., 'hive_app_icon')
        sizes (list): List of tuples with (width, height) for each size
    """
    results = []
    
    for size in sizes:
        width, height = size
        output_path = f"{output_prefix}_{width}x{height}.png"
        success = resize_image(input_path, output_path, size)
        results.append((size, success))
    
    return results

def convert_to_ico(input_path, output_path, sizes):
    """
    Convert a PNG image to ICO format with multiple sizes.
    
    Args:
        input_path (str): Path to the input PNG image
        output_path (str): Path to save the ICO file
        sizes (list): List of tuples with (width, height) for each size
    """
    try:
        images = []
        with Image.open(input_path) as base_img:
            for size in sizes:
                resized_img = base_img.resize(size, Image.Resampling.LANCZOS)
                images.append(resized_img)
            
            # Save as ICO with multiple sizes
            if images:
                images[0].save(output_path, format='ICO', sizes=sizes)
                logger.info(f"Created ICO file {output_path} with sizes {sizes}")
                return True
    except Exception as e:
        logger.error(f"Error converting to ICO {output_path}: {e}")
        return False

# Example usage:
if __name__ == "__main__":
    # Example of creating application icons in various sizes
    app_icon_sizes = [
        (16, 16),
        (32, 32),
        (64, 64),
        (128, 128),
        (256, 256),
        (512, 512),
        (1024, 1024)
    ]
    
    # Example of creating ICO file with multiple sizes
    ico_sizes = [
        (16, 16),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256)
    ]
    
    # This would be called with actual paths when new icons are provided
    # create_multiple_sizes("path/to/source/icon.png", "hive_app_icon", app_icon_sizes)
    # convert_to_ico("path/to/source/icon_256x256.png", "hive_app_icon.ico", ico_sizes)
    
    print("Icon resizer utility ready for use.")