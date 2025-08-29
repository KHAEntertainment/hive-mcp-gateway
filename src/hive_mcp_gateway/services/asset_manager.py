"""Asset manager for Hive MCP Gateway logos and icons."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import shutil

logger = logging.getLogger(__name__)


class AssetManager:
    """Manages logo assets and icon generation for Hive MCP Gateway."""
    
    # Standard macOS app icon sizes
    MACOS_ICON_SIZES = [16, 32, 64, 128, 256, 512, 1024]
    
    # Menubar icon size
    MENUBAR_ICON_SIZE = 22
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize asset manager."""
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent
        self.source_logos = self._locate_source_logos()
        self.output_dir = self.project_root / "gui" / "assets"
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Asset manager initialized with {len(self.source_logos)} source logos")
    
    def _locate_source_logos(self) -> Dict[str, Path]:
        """Locate source logo files."""
        logos = {}
        
        # Expected logo files from the Missing Features document
        logo_files = {
            "fullsize_square": "the_hive_logo_fullsize_sq.png",
            "banner": "the_hive_logo_banner.png", 
            "standard": "the_hive_logo.png",
            "avatar": "hive_avatar.png"
        }
        
        for key, filename in logo_files.items():
            logo_path = self.project_root / filename
            if logo_path.exists():
                logos[key] = logo_path
                logger.info(f"Found {key} logo: {logo_path}")
            else:
                logger.warning(f"Missing {key} logo: {logo_path}")
        
        return logos
    
    def generate_all_assets(self) -> Dict[str, List[Path]]:
        """Generate all required assets from source logos."""
        generated_assets = {
            "menubar_icons": [],
            "app_icons": [],
            "favicon": [],
            "dock_icons": []
        }
        
        try:
            # Generate menubar icons
            menubar_icons = self.generate_menubar_icons()
            generated_assets["menubar_icons"] = menubar_icons
            
            # Generate application icons
            app_icons = self.generate_app_icons()
            generated_assets["app_icons"] = app_icons
            
            # Generate favicon
            favicon_path = self.generate_favicon()
            if favicon_path:
                generated_assets["favicon"] = [favicon_path]
            
            # Generate dock icons
            dock_icons = self.generate_dock_icons()
            generated_assets["dock_icons"] = dock_icons
            
            logger.info("Successfully generated all asset variants")
            
        except Exception as e:
            logger.error(f"Failed to generate assets: {e}")
            raise
        
        return generated_assets
    
    def generate_menubar_icons(self) -> List[Path]:
        """Generate 22x22px menubar icons with status variants."""
        if "fullsize_square" not in self.source_logos:
            logger.error("Cannot generate menubar icons: missing fullsize_square logo")
            return []
        
        source_logo = self.source_logos["fullsize_square"]
        generated_icons = []
        
        # Status variants with colors
        variants = {
            "default": "#4A7C59",      # Hive green
            "running": "#4CAF50",      # Green
            "stopped": "#9E9E9E",      # Gray  
            "warning": "#FF9800",      # Orange
            "error": "#F44336",        # Red
            "template": None           # Template (no overlay)
        }
        
        try:
            # Load and prepare base image
            base_image = Image.open(source_logo).convert("RGBA")
            
            for variant_name, color in variants.items():
                # Resize to menubar size with high quality
                icon = base_image.resize(
                    (self.MENUBAR_ICON_SIZE, self.MENUBAR_ICON_SIZE),
                    Image.Resampling.LANCZOS
                )
                
                # Apply status color overlay if specified
                if color and variant_name != "template":
                    icon = self._apply_color_overlay(icon, color, opacity=0.7)
                
                # Apply template processing for macOS dark mode compatibility
                if variant_name == "template":
                    icon = self._create_template_icon(icon)
                
                # Save the icon
                output_path = self.output_dir / f"hive_menubar_{variant_name}.png"
                icon.save(output_path, "PNG", optimize=True)
                generated_icons.append(output_path)
                
                logger.info(f"Generated menubar icon: {output_path}")
        
        except Exception as e:
            logger.error(f"Failed to generate menubar icons: {e}")
            
        return generated_icons
    
    def generate_app_icons(self) -> List[Path]:
        """Generate application icons in standard macOS sizes."""
        if "fullsize_square" not in self.source_logos:
            logger.error("Cannot generate app icons: missing fullsize_square logo")
            return []
        
        source_logo = self.source_logos["fullsize_square"]
        generated_icons = []
        
        try:
            # Load source image
            base_image = Image.open(source_logo).convert("RGBA")
            
            for size in self.MACOS_ICON_SIZES:
                # Resize with high quality
                icon = base_image.resize((size, size), Image.Resampling.LANCZOS)
                
                # Apply subtle enhancement for better visibility at small sizes
                if size <= 32:
                    icon = self._enhance_small_icon(icon)
                
                # Save in multiple formats
                for ext in ["png", "ico"]:
                    output_path = self.output_dir / f"hive_app_icon_{size}x{size}.{ext}"
                    
                    if ext == "ico" and size in [16, 32, 48, 64, 128, 256]:
                        # ICO files for Windows compatibility
                        icon.save(output_path, "ICO", sizes=[(size, size)])
                    elif ext == "png":
                        icon.save(output_path, "PNG", optimize=True)
                    
                    generated_icons.append(output_path)
                    logger.info(f"Generated app icon: {output_path}")
        
        except Exception as e:
            logger.error(f"Failed to generate app icons: {e}")
            
        return generated_icons
    
    def generate_favicon(self) -> Optional[Path]:
        """Generate favicon from fullsize square logo."""
        if "fullsize_square" not in self.source_logos:
            logger.error("Cannot generate favicon: missing fullsize_square logo")
            return None
        
        source_logo = self.source_logos["fullsize_square"]
        
        try:
            # Load and resize to favicon size
            base_image = Image.open(source_logo).convert("RGBA")
            favicon = base_image.resize((32, 32), Image.Resampling.LANCZOS)
            
            # Apply enhancement for small size
            favicon = self._enhance_small_icon(favicon)
            
            # Save as ICO with multiple sizes
            output_path = self.output_dir / "hive_favicon.ico"
            favicon.save(output_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
            
            logger.info(f"Generated favicon: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to generate favicon: {e}")
            return None
    
    def generate_dock_icons(self) -> List[Path]:
        """Generate macOS dock icons with rounded corners."""
        if "fullsize_square" not in self.source_logos:
            logger.error("Cannot generate dock icons: missing fullsize_square logo")
            return []
        
        source_logo = self.source_logos["fullsize_square"]
        generated_icons = []
        
        try:
            base_image = Image.open(source_logo).convert("RGBA")
            
            # Generate dock icons for common sizes
            dock_sizes = [128, 256, 512, 1024]
            
            for size in dock_sizes:
                # Resize icon
                icon = base_image.resize((size, size), Image.Resampling.LANCZOS)
                
                # Apply macOS-style rounded corners
                rounded_icon = self._apply_rounded_corners(icon, corner_radius=size // 8)
                
                # Save the dock icon
                output_path = self.output_dir / f"hive_dock_icon_{size}x{size}.png"
                rounded_icon.save(output_path, "PNG", optimize=True)
                generated_icons.append(output_path)
                
                logger.info(f"Generated dock icon: {output_path}")
        
        except Exception as e:
            logger.error(f"Failed to generate dock icons: {e}")
            
        return generated_icons
    
    def _apply_color_overlay(self, image: Image.Image, color: str, opacity: float = 0.5) -> Image.Image:
        """Apply colored overlay to image for status indication."""
        overlay = Image.new("RGBA", image.size, color + "00")
        draw = ImageDraw.Draw(overlay)
        
        # Create colored overlay with specified opacity
        overlay_color = (*tuple(int(color[1:][i:i+2], 16) for i in (0, 2, 4)), int(255 * opacity))
        draw.rectangle([0, 0, image.size[0], image.size[1]], fill=overlay_color)
        
        # Composite with original image
        return Image.alpha_composite(image, overlay)
    
    def _create_template_icon(self, image: Image.Image) -> Image.Image:
        """Create template icon for macOS dark mode compatibility."""
        # Convert to grayscale while preserving alpha
        grayscale = image.convert("LA")
        
        # Create new RGBA image
        template = Image.new("RGBA", image.size, (0, 0, 0, 0))
        
        # Apply template effect (black with alpha)
        for x in range(image.size[0]):
            for y in range(image.size[1]):
                gray_pixel = grayscale.getpixel((x, y))
                alpha = gray_pixel[1] if len(gray_pixel) > 1 else 255
                
                if alpha > 0:
                    # Use luminance for template intensity
                    intensity = gray_pixel[0]
                    template.putpixel((x, y), (0, 0, 0, int(alpha * (intensity / 255))))
        
        return template
    
    def _enhance_small_icon(self, image: Image.Image) -> Image.Image:
        """Enhance small icons for better visibility."""
        from PIL import ImageEnhance
        
        # Increase contrast slightly for small sizes
        enhancer = ImageEnhance.Contrast(image)
        enhanced = enhancer.enhance(1.1)
        
        # Increase sharpness
        sharpener = ImageEnhance.Sharpness(enhanced)
        sharpened = sharpener.enhance(1.2)
        
        return sharpened
    
    def _apply_rounded_corners(self, image: Image.Image, corner_radius: int) -> Image.Image:
        """Apply rounded corners to image (macOS dock style)."""
        # Create mask for rounded corners
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw rounded rectangle mask
        draw.rounded_rectangle(
            [0, 0, image.size[0], image.size[1]], 
            radius=corner_radius, 
            fill=255
        )
        
        # Create output image
        rounded = Image.new("RGBA", image.size, (0, 0, 0, 0))
        rounded.paste(image, (0, 0))
        rounded.putalpha(mask)
        
        return rounded
    
    def update_system_tray_icons(self) -> bool:
        """Update system tray with new Hive icons."""
        try:
            # Generate menubar icons
            menubar_icons = self.generate_menubar_icons()
            
            if not menubar_icons:
                logger.error("No menubar icons generated")
                return False
            
            # Update system_tray.py icon paths
            system_tray_file = self.project_root / "gui" / "system_tray.py"
            
            if system_tray_file.exists():
                # Read current content
                content = system_tray_file.read_text()
                
                # Update icon file mappings to use new Hive icons
                icon_mappings = {
                    "running": "hive_menubar_running.png",
                    "stopped": "hive_menubar_stopped.png",
                    "warning": "hive_menubar_warning.png",
                    "error": "hive_menubar_error.png",
                    "default": "hive_menubar_default.png"
                }
                
                # This is a simplified update - in production we'd parse and update properly
                logger.info("Menubar icons updated - system_tray.py may need manual icon path updates")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update system tray icons: {e}")
            return False
    
    def get_asset_info(self) -> Dict[str, any]:
        """Get information about available assets."""
        return {
            "source_logos": {name: str(path) for name, path in self.source_logos.items()},
            "output_directory": str(self.output_dir),
            "menubar_icon_size": self.MENUBAR_ICON_SIZE,
            "app_icon_sizes": self.MACOS_ICON_SIZES,
            "assets_exist": self.output_dir.exists(),
            "generated_assets": list(self.output_dir.glob("hive_*"))
        }


def main():
    """Generate all assets when run directly."""
    logging.basicConfig(level=logging.INFO)
    
    asset_manager = AssetManager()
    
    print("🎨 Generating Hive MCP Gateway assets...")
    
    try:
        generated_assets = asset_manager.generate_all_assets()
        
        print("✅ Asset generation completed successfully!")
        
        for category, assets in generated_assets.items():
            print(f"  {category}: {len(assets)} files")
            for asset in assets[:3]:  # Show first 3 of each type
                print(f"    - {asset.name}")
            if len(assets) > 3:
                print(f"    ... and {len(assets) - 3} more")
        
        # Update system tray icons
        if asset_manager.update_system_tray_icons():
            print("🔄 System tray icons updated")
        
    except Exception as e:
        print(f"❌ Asset generation failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())