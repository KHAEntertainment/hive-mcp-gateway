#!/usr/bin/env python3
"""Test script to verify GUI startup."""

import sys
import logging
from pathlib import Path

# Setup logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('startup_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_gui_startup():
    """Test if the GUI can start without errors."""
    try:
        logger.info("=== Starting GUI Startup Test ===")
        
        # Import the GUI application
        from gui.main_app import HiveMCPGUI
        logger.info("✅ Successfully imported HiveMCPGUI")
        
        # Create the application
        logger.info("Creating application instance...")
        app = HiveMCPGUI([])
        logger.info("✅ Application instance created")
        
        # Check system tray
        if hasattr(app, 'system_tray') and app.system_tray:
            logger.info(f"✅ System tray exists and is visible: {app.system_tray.isVisible()}")
            
            # Get icon info
            if app.system_tray.icon():
                logger.info("✅ System tray has an icon set")
            else:
                logger.warning("⚠️  System tray does not have an icon")
                
        else:
            logger.error("❌ System tray was not created")
            return False
        
        logger.info("✅ GUI startup test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ GUI startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_gui_startup()
    if success:
        print("✅ Startup test PASSED - GUI should work")
    else:
        print("❌ Startup test FAILED - GUI has issues")
        sys.exit(1)