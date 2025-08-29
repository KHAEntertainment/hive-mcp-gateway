#!/usr/bin/env python3
"""Generate menubar icons for Hive MCP Gateway."""

import os
from pathlib import Path

def create_svg_icon():
    """Create SVG icon for Hive MCP Gateway representing a network gateway/hive concept."""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .icon-path { 
        fill: #000000; 
        stroke: none; 
      }
      .icon-outline { 
        fill: none; 
        stroke: #000000; 
        stroke-width: 1.5; 
        stroke-linecap: round; 
        stroke-linejoin: round; 
      }
    </style>
  </defs>
  
  <!-- Central hub (gateway) -->
  <circle cx="11" cy="11" r="3" class="icon-path"/>
  
  <!-- Network nodes (hive concept) -->
  <circle cx="5" cy="5" r="1.5" class="icon-path"/>
  <circle cx="17" cy="5" r="1.5" class="icon-path"/>
  <circle cx="5" cy="17" r="1.5" class="icon-path"/>
  <circle cx="17" cy="17" r="1.5" class="icon-path"/>
  
  <!-- Connection lines (showing gateway function) -->
  <line x1="6.5" y1="6.5" x2="8.5" y2="8.5" class="icon-outline"/>
  <line x1="15.5" y1="6.5" x2="13.5" y2="8.5" class="icon-outline"/>
  <line x1="6.5" y1="15.5" x2="8.5" y2="13.5" class="icon-outline"/>
  <line x1="15.5" y1="15.5" x2="13.5" y2="13.5" class="icon-outline"/>
</svg>'''
    return svg_content

def create_template_icon():
    """Create a template (outline) version for dark mode compatibility."""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .template-outline { 
        fill: none; 
        stroke: #000000; 
        stroke-width: 1.8; 
        stroke-linecap: round; 
        stroke-linejoin: round; 
      }
      .template-fill { 
        fill: #000000; 
        stroke: none; 
      }
    </style>
  </defs>
  
  <!-- Central hub (gateway) - outlined for template -->
  <circle cx="11" cy="11" r="3" class="template-outline"/>
  
  <!-- Network nodes (hive concept) - filled for contrast -->
  <circle cx="5" cy="5" r="1.2" class="template-fill"/>
  <circle cx="17" cy="5" r="1.2" class="template-fill"/>
  <circle cx="5" cy="17" r="1.2" class="template-fill"/>
  <circle cx="17" cy="17" r="1.2" class="template-fill"/>
  
  <!-- Connection lines -->
  <line x1="6.2" y1="6.2" x2="8.2" y2="8.2" class="template-outline"/>
  <line x1="15.8" y1="6.2" x2="13.8" y2="8.2" class="template-outline"/>
  <line x1="6.2" y1="15.8" x2="8.2" y2="13.8" class="template-outline"/>
  <line x1="15.8" y1="15.8" x2="13.8" y2="13.8" class="template-outline"/>
</svg>'''
    return svg_content

def main():
    """Generate the menubar icons."""
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # Create main icon
    icon_path = assets_dir / "menubar_icon.svg"
    with open(icon_path, 'w') as f:
        f.write(create_svg_icon())
    print(f"Created main icon: {icon_path}")
    
    # Create template icon for dark mode
    template_path = assets_dir / "menubar_icon_template.svg"
    with open(template_path, 'w') as f:
        f.write(create_template_icon())
    print(f"Created template icon: {template_path}")
    
    # Create status icons
    status_icons = {
        "running": "#4CAF50",  # Green
        "stopped": "#F44336",  # Red  
        "warning": "#FF9800",  # Orange
        "error": "#E91E63"     # Pink
    }
    
    for status, color in status_icons.items():
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .status-path {{ 
        fill: {color}; 
        stroke: none; 
      }}
      .status-outline {{ 
        fill: none; 
        stroke: {color}; 
        stroke-width: 1.5; 
        stroke-linecap: round; 
        stroke-linejoin: round; 
      }}
    </style>
  </defs>
  
  <!-- Central hub with status color -->
  <circle cx="11" cy="11" r="3" class="status-path"/>
  
  <!-- Network nodes -->
  <circle cx="5" cy="5" r="1.2" class="status-path" opacity="0.7"/>
  <circle cx="17" cy="5" r="1.2" class="status-path" opacity="0.7"/>
  <circle cx="5" cy="17" r="1.2" class="status-path" opacity="0.7"/>
  <circle cx="17" cy="17" r="1.2" class="status-path" opacity="0.7"/>
  
  <!-- Connection lines -->
  <line x1="6.2" y1="6.2" x2="8.2" y2="8.2" class="status-outline"/>
  <line x1="15.8" y1="6.2" x2="13.8" y2="8.2" class="status-outline"/>
  <line x1="6.2" y1="15.8" x2="8.2" y2="13.8" class="status-outline"/>
  <line x1="15.8" y1="15.8" x2="13.8" y2="13.8" class="status-outline"/>
</svg>'''
        
        status_path = assets_dir / f"menubar_icon_{status}.svg"
        with open(status_path, 'w') as f:
            f.write(svg_content)
        print(f"Created {status} icon: {status_path}")
    
    print("\nAll menubar icons created successfully!")
    print("Icons are designed for 22x22px at standard resolution (44x44px for Retina)")

if __name__ == "__main__":
    main()