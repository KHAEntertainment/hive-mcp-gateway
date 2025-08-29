#!/usr/bin/env python3
"""Launcher script for Hive MCP Gateway GUI application."""

import sys
import os
import logging
from pathlib import Path

# Setup logging to see debug output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Add the src directory to the path for backend imports
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Now we can import and run the GUI
if __name__ == "__main__":
    try:
        # Import the main GUI class
        from gui.main_app import HiveMCPGUI
        
        print("Starting Hive MCP Gateway GUI...")
        # Create and run the application
        app = HiveMCPGUI()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting Hive MCP Gateway GUI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)