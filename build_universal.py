#!/usr/bin/env python3
"""Universal build system for Hive MCP Gateway using uv + PyInstaller."""

import argparse
import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_platform_manager():
    """Get the appropriate platform manager."""
    try:
        from src.hive_mcp_gateway.platforms import get_platform_manager
        return get_platform_manager()
    except ImportError as e:
        logger.error(f"Failed to import platform manager: {e}")
        return None


def check_dependencies() -> bool:
    """Check if required build dependencies are available."""
    logger.info("Checking build dependencies...")
    
    required_tools = ["uv", "python3"]
    missing_tools = []
    
    for tool in required_tools:
        if not shutil.which(tool):
            missing_tools.append(tool)
    
    if missing_tools:
        logger.error(f"Missing required tools: {', '.join(missing_tools)}")
        logger.info("Please install the missing tools and try again.")
        return False
    
    # Check if uv environment is set up
    try:
        result = subprocess.run(
            ["uv", "pip", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.warning("uv environment not properly set up, attempting to sync...")
            subprocess.run(["uv", "sync"], check=True)
    except subprocess.SubprocessError as e:
        logger.error(f"Failed to check uv environment: {e}")
        return False
    
    logger.info("✅ All dependencies are available")
    return True


def clean_build_directory():
    """Clean previous build artifacts."""
    logger.info("Cleaning build directory...")
    
    dirs_to_clean = ["build", "dist", "__pycache__"]
    
    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            logger.info(f"Removed {dir_path}")


def create_icons():
    """Create platform-specific icons if they don't exist."""
    logger.info("Checking for platform-specific icons...")
    
    icon_dir = Path("gui/assets")
    base_icon = icon_dir / "icon.png"
    
    if not base_icon.exists():
        logger.warning(f"Base icon not found at {base_icon}")
        return False
    
    platform_system = platform.system()
    
    # Create platform-specific icons if needed
    if platform_system == "Darwin":
        icns_icon = icon_dir / "icon.icns"
        if not icns_icon.exists():
            logger.info("Creating macOS icon...")
            try:
                # This would require additional tools like iconutil
                # For now, just log that it should be created
                logger.warning(f"Please create {icns_icon} from {base_icon}")
            except Exception as e:
                logger.warning(f"Could not create macOS icon: {e}")
    
    elif platform_system == "Windows":
        ico_icon = icon_dir / "icon.ico"
        if not ico_icon.exists():
            logger.info("Creating Windows icon...")
            try:
                # This would require additional tools like imagemagick
                logger.warning(f"Please create {ico_icon} from {base_icon}")
            except Exception as e:
                logger.warning(f"Could not create Windows icon: {e}")
    
    return True


def build_application(platform_manager, target_platform: Optional[str] = None) -> bool:
    """Build the application using the platform manager."""
    logger.info(f"Building application for {platform_manager.platform_info.platform.value}...")
    
    try:
        # Get build configuration
        build_config = platform_manager.get_build_configuration()
        
        # Check platform-specific requirements
        missing_tools = []
        for tool in build_config.required_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)
        
        if missing_tools:
            logger.error(f"Missing platform-specific tools: {', '.join(missing_tools)}")
            logger.info("Please install the missing tools and try again.")
            return False
        
        # Create output directory
        output_dir = Path("dist")
        output_dir.mkdir(exist_ok=True)
        
        # Build the application bundle
        success = platform_manager.create_application_bundle(
            source_dir=Path.cwd(),
            output_dir=output_dir
        )
        
        if not success:
            logger.error("Failed to create application bundle")
            return False
        
        logger.info("✅ Application bundle created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Build failed: {e}")
        return False


def create_installer(platform_manager) -> bool:
    """Create platform-specific installer."""
    logger.info("Creating installer...")
    
    try:
        output_dir = Path("dist")
        
        # Find the built application
        platform_system = platform.system()
        
        if platform_system == "Darwin":
            bundle_path = output_dir / "HiveMCPGateway.app"
        elif platform_system == "Windows":
            bundle_path = output_dir / "HiveMCPGateway.exe"
        elif platform_system == "Linux":
            bundle_path = output_dir / "hive-mcp-gateway"
        else:
            logger.error(f"Unsupported platform: {platform_system}")
            return False
        
        if not bundle_path.exists():
            logger.error(f"Application bundle not found at {bundle_path}")
            return False
        
        # Create installer
        success = platform_manager.create_installer(
            bundle_path=bundle_path,
            output_dir=output_dir
        )
        
        if success:
            logger.info("✅ Installer created successfully")
        else:
            logger.warning("Installer creation failed or not supported")
        
        return success
        
    except Exception as e:
        logger.error(f"Installer creation failed: {e}")
        return False


def validate_build(platform_manager) -> bool:
    """Validate the built application."""
    logger.info("Validating build...")
    
    try:
        # Check if the application was built
        output_dir = Path("dist")
        platform_system = platform.system()
        
        if platform_system == "Darwin":
            app_path = output_dir / "HiveMCPGateway.app"
            executable_path = app_path / "Contents" / "MacOS" / "HiveMCPGateway"
        elif platform_system == "Windows":
            app_path = output_dir / "HiveMCPGateway.exe"
            executable_path = app_path
        elif platform_system == "Linux":
            app_path = output_dir / "hive-mcp-gateway"
            executable_path = app_path
        else:
            logger.error(f"Unsupported platform: {platform_system}")
            return False
        
        if not app_path.exists():
            logger.error(f"Application not found at {app_path}")
            return False
        
        if executable_path.exists() and executable_path.is_file():
            # Check if executable is actually executable
            if not executable_path.stat().st_mode & 0o111:
                logger.warning(f"Executable {executable_path} is not executable")
                executable_path.chmod(0o755)
        
        logger.info("✅ Build validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Build validation failed: {e}")
        return False


def print_build_summary(platform_manager):
    """Print build summary and next steps."""
    logger.info("=" * 60)
    logger.info("BUILD SUMMARY")
    logger.info("=" * 60)
    
    platform_info = platform_manager.platform_info
    logger.info(f"Platform: {platform_info.platform.value}")
    logger.info(f"Architecture: {platform_info.architecture}")
    logger.info(f"Python Version: {platform_info.python_version.split()[0]}")
    
    output_dir = Path("dist")
    if output_dir.exists():
        files = list(output_dir.iterdir())
        logger.info(f"Output Directory: {output_dir.absolute()}")
        logger.info("Built Files:")
        for file in files:
            size = file.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"  - {file.name} ({size:.1f} MB)")
    
    logger.info("\nNext Steps:")
    logger.info("1. Test the built application")
    logger.info("2. Create code signatures (if applicable)")
    logger.info("3. Distribute to users")
    logger.info("=" * 60)


def main():
    """Main build script entry point."""
    parser = argparse.ArgumentParser(description="Universal build system for Hive MCP Gateway")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    parser.add_argument("--no-installer", action="store_true", help="Skip installer creation")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the build environment")
    parser.add_argument("--platform", choices=["macos", "windows", "linux"], help="Target platform (default: current)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🚀 Starting Hive MCP Gateway build process...")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Get platform manager
    platform_manager = get_platform_manager()
    if not platform_manager:
        logger.error("Failed to get platform manager")
        sys.exit(1)
    
    # Validate platform support
    is_supported, issues = platform_manager.validate_platform_support()
    if not is_supported:
        logger.error("Platform validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        sys.exit(1)
    
    if args.validate_only:
        logger.info("✅ Build environment validation passed")
        return
    
    # Clean build directory if requested
    if args.clean:
        clean_build_directory()
    
    # Create icons
    create_icons()
    
    # Build application
    if not build_application(platform_manager, args.platform):
        logger.error("❌ Build failed")
        sys.exit(1)
    
    # Validate build
    if not validate_build(platform_manager):
        logger.error("❌ Build validation failed")
        sys.exit(1)
    
    # Create installer (optional)
    if not args.no_installer:
        create_installer(platform_manager)
    
    # Print summary
    print_build_summary(platform_manager)
    
    logger.info("🎉 Build completed successfully!")


if __name__ == "__main__":
    main()