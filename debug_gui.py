#!/usr/bin/env python3
"""Debug script to test GUI startup and identify issues."""

import sys
import logging
import traceback
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_gui.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_imports():
    """Test all critical imports."""
    logger.info("=== Testing Imports ===")
    
    # Add project paths
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))
    
    try:
        logger.info("Testing PyQt6 import...")
        from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
        logger.info("✅ PyQt6 import successful")
    except Exception as e:
        logger.error(f"❌ PyQt6 import failed: {e}")
        return False
    
    try:
        logger.info("Testing system tray availability...")
        app = QApplication([])
        available = QSystemTrayIcon.isSystemTrayAvailable()
        logger.info(f"✅ System tray available: {available}")
        app.quit()
    except Exception as e:
        logger.error(f"❌ System tray test failed: {e}")
        return False
    
    try:
        logger.info("Testing GUI imports...")
        from gui.main_app import HiveMCPGUI
        logger.info("✅ HiveMCPGUI import successful")
    except Exception as e:
        logger.error(f"❌ HiveMCPGUI import failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_gui_startup():
    """Test GUI application startup."""
    logger.info("=== Testing GUI Startup ===")
    
    try:
        from gui.main_app import HiveMCPGUI
        
        logger.info("Creating HiveMCPGUI instance...")
        app = HiveMCPGUI([])
        
        logger.info("✅ GUI application created successfully")
        
        # Check system tray
        if hasattr(app, 'system_tray') and app.system_tray:
            logger.info(f"✅ System tray created: {app.system_tray.isVisible()}")
        else:
            logger.error("❌ System tray not created")
        
        # Don't actually run the event loop for testing
        logger.info("GUI startup test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ GUI startup failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Main debug function."""
    logger.info("Starting Hive MCP Gateway Debug Session")
    
    # Test imports first
    if not test_imports():
        logger.error("Import tests failed - cannot proceed")
        return False
    
    # Test GUI startup
    if not test_gui_startup():
        logger.error("GUI startup tests failed")
        return False
    
    logger.info("All tests passed! GUI should be working.")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)