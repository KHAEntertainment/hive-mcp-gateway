#!/usr/bin/env python3
"""Minimal test launcher for GUI debugging."""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_basic_pyqt():
    """Test basic PyQt6 functionality."""
    try:
        from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QIcon
        
        logger.info("✅ PyQt6 imports successful")
        
        # Create basic app
        app = QApplication([])
        logger.info("✅ QApplication created")
        
        # Check system tray
        if QSystemTrayIcon.isSystemTrayAvailable():
            logger.info("✅ System tray is available")
            
            # Create simple tray icon
            tray = QSystemTrayIcon(app)
            menu = QMenu()
            menu.addAction("Test Action")
            tray.setContextMenu(menu)
            
            # Try to show it
            tray.show()
            logger.info(f"✅ System tray created and shown: {tray.isVisible()}")
            
            # Use a timer to quit after a few seconds
            timer = QTimer()
            timer.timeout.connect(app.quit)
            timer.start(3000)  # 3 seconds
            
            logger.info("Starting event loop for 3 seconds...")
            app.exec()
            
        else:
            logger.error("❌ System tray not available")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic PyQt6 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting minimal GUI test...")
    success = test_basic_pyqt()
    
    if success:
        logger.info("✅ Basic GUI test passed!")
    else:
        logger.error("❌ Basic GUI test failed!")
        sys.exit(1)#!/usr/bin/env python3
"""Minimal test launcher for GUI debugging."""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_basic_pyqt():
    """Test basic PyQt6 functionality."""
    try:
        from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QIcon
        
        logger.info("✅ PyQt6 imports successful")
        
        # Create basic app
        app = QApplication([])
        logger.info("✅ QApplication created")
        
        # Check system tray
        if QSystemTrayIcon.isSystemTrayAvailable():
            logger.info("✅ System tray is available")
            
            # Create simple tray icon
            tray = QSystemTrayIcon(app)
            menu = QMenu()
            menu.addAction("Test Action")
            tray.setContextMenu(menu)
            
            # Try to show it
            tray.show()
            logger.info(f"✅ System tray created and shown: {tray.isVisible()}")
            
            # Use a timer to quit after a few seconds
            timer = QTimer()
            timer.timeout.connect(app.quit)
            timer.start(3000)  # 3 seconds
            
            logger.info("Starting event loop for 3 seconds...")
            app.exec()
            
        else:
            logger.error("❌ System tray not available")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic PyQt6 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting minimal GUI test...")
    success = test_basic_pyqt()
    
    if success:
        logger.info("✅ Basic GUI test passed!")
    else:
        logger.error("❌ Basic GUI test failed!")
        sys.exit(1)