"""Create a placeholder banner image for the Hive MCP Gateway."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_placeholder_banner(output_path="hive_banner.png", width=800, height=200):
    """
    Create a placeholder banner image with Hive branding colors.
    
    Args:
        output_path (str): Path to save the banner image
        width (int): Width of the banner
        height (int): Height of the banner
    """
    # Create a new image with Hive background color
    image = Image.new('RGB', (width, height), color='#2b2d31')  # Hive Night background
    draw = ImageDraw.Draw(image)
    
    # Draw a hexagon shape (Hive-like)
    hexagon_color = '#8c62ff'  # Hive primary accent color
    center_x, center_y = width // 2, height // 2
    size = min(width, height) // 4
    
    # Calculate hexagon points
    import math
    points = []
    for i in range(6):
        angle_deg = 60 * i - 30
        angle_rad = math.radians(angle_deg)
        x = center_x + size * math.cos(angle_rad)
        y = center_y + size * math.sin(angle_rad)
        points.append((x, y))
    
    # Draw hexagon
    draw.polygon(points, fill=hexagon_color)
    
    # Add text
    try:
        # Try to use a nice font
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    text = "HIVE MCP GATEWAY"
    # Get text dimensions
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Position text
    text_x = (width - text_width) // 2
    text_y = height - text_height - 20
    
    # Draw text with contrasting color
    draw.text((text_x, text_y), text, fill='#f2f3f5', font=font)
    
    # Save the image
    image.save(output_path)
    print(f"Created placeholder banner: {output_path}")

if __name__ == "__main__":
    create_placeholder_banner()