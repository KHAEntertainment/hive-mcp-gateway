#!/usr/bin/env python3
import re

def fix_main_window():
    with open('gui/main_window.py', 'r') as f:
        content = f.read()
    
    # Fix setContentsMargins calls to use 4 arguments
    # Line 35: layout.setContentsMargins(15, 15) -> layout.setContentsMargins(15, 15, 15, 15)
    content = re.sub(
        r'(\s+layout\.setContentsMargins\(15, 15)\)(\s+# Fixed: 4 arguments)',
        r'\1, 15, 15)\2',
        content
    )
    
    # Line 41: notifications_layout.setContentsMargins(15, 15, 15) -> notifications_layout.setContentsMargins(15, 15, 15, 15)
    content = re.sub(
        r'(\s+notifications_layout\.setContentsMargins\(15, 15, 15)\)(\s+# Fixed: 4 arguments)',
        r'\1, 15)\2',
        content
    )
    
    # Line 80: status_layout.setContentsMargins(10, 10) -> status_layout.setContentsMargins(10, 10, 10, 10)
    content = re.sub(
        r'(\s+status_layout\.setContentsMargins\(10, 10)\)(\s+# Fixed: 4 arguments)',
        r'\1, 10, 10)\2',
        content
    )
    
    # Line 117: deps_layout.setContentsMargins(10, 10) -> deps_layout.setContentsMargins(10, 10, 10, 10)
    content = re.sub(
        r'(\s+deps_layout\.setContentsMargins\(10, 10)\)(\s+# Fixed: 4 arguments)',
        r'\1, 10, 10)\2',
        content
    )
    
    # Fix extra semicolon
    content = re.sub(
        r'logger\.error\(f"Error loading stylesheet: \{e\}"\);',
        r'logger.error(f"Error loading stylesheet: {e}")',
        content
    )
    
    # Remove duplicate port configuration loading
    # Remove the call in setup_connections method
    content = re.sub(
        r'\s+# Load port configuration\n\s+self\.status_widget\.load_port_configuration\(self\.config_manager\)\s+# Corrected: Pass config_manager\n',
        '\n',
        content
    )
    
    # Remove the empty save_port_configuration method from StatusWidget
    content = re.sub(
        r'\s+def save_port_configuration\(self\):\n\s+"""Placeholder method\. Actual saving is handled by the main window\."""\n\s+pass\n',
        '',
        content
    )
    
    with open('gui/main_window.py', 'w') as f:
        f.write(content)
    
    print("Fixed all setContentsMargins calls, syntax errors, and port configuration issues")

if __name__ == "__main__":
    fix_main_window()

