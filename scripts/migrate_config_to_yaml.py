#!/usr/bin/env python3
"""Migration script to convert old JSON configuration to new YAML format with enhanced features."""

import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any

def load_json_config(json_path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)

def convert_config_to_yaml_format(json_config: Dict[str, Any]) -> Dict[str, Any]:
    """Convert JSON configuration to YAML format with enhanced features."""
    # Create new configuration structure
    yaml_config = {
        "toolGating": json_config.get("toolGating", {}),
        "backendMcpServers": {}
    }
    
    # Add new toolGating settings if they don't exist
    if "toolGating" in yaml_config:
        tool_gating = yaml_config["toolGating"]
        if "healthCheckInterval" not in tool_gating:
            tool_gating["healthCheckInterval"] = 30
        if "connectionTimeout" not in tool_gating:
            tool_gating["connectionTimeout"] = 10
    
    # Convert backend servers
    backend_servers = json_config.get("backendMcpServers", {})
    for server_name, server_config in backend_servers.items():
        # Create enhanced server configuration
        enhanced_config = server_config.copy()
        
        # Add authentication configuration if not present
        if "authentication" not in enhanced_config:
            enhanced_config["authentication"] = {
                "type": "none"
            }
        
        # Add health check configuration if not present
        if "healthCheck" not in enhanced_config:
            enhanced_config["healthCheck"] = {
                "enabled": True,
                "interval": 60
            }
        
        # Add metadata configuration if not present
        if "metadata" not in enhanced_config:
            enhanced_config["metadata"] = {
                "category": "unknown",
                "version": "unknown",
                "tags": []
            }
        
        # Add default options if not present
        if "options" not in enhanced_config:
            enhanced_config["options"] = {
                "timeout": 30,
                "retryCount": 3,
                "batchSize": 1
            }
        
        yaml_config["backendMcpServers"][server_name] = enhanced_config
    
    return yaml_config

def save_yaml_config(yaml_config: Dict[str, Any], yaml_path: Path) -> None:
    """Save configuration to YAML file."""
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_config, f, default_flow_style=False, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Migrate Tool Gating MCP configuration from JSON to YAML format")
    parser.add_argument("input", help="Path to input JSON configuration file")
    parser.add_argument("output", help="Path to output YAML configuration file")
    parser.add_argument("--backup", action="store_true", help="Create backup of original JSON file")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Validate input file
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist")
        return 1
    
    if input_path.suffix.lower() != '.json':
        print(f"Error: Input file {input_path} is not a JSON file")
        return 1
    
    # Load JSON configuration
    print(f"Loading configuration from {input_path}")
    json_config = load_json_config(input_path)
    
    # Convert to YAML format
    print("Converting configuration to YAML format with enhanced features")
    yaml_config = convert_config_to_yaml_format(json_config)
    
    # Create backup if requested
    if args.backup:
        backup_path = input_path.with_suffix('.backup.json')
        print(f"Creating backup of original configuration to {backup_path}")
        with open(backup_path, 'w') as f:
            json.dump(json_config, f, indent=2)
    
    # Save YAML configuration
    print(f"Saving enhanced configuration to {output_path}")
    save_yaml_config(yaml_config, output_path)
    
    print("Migration completed successfully!")
    print(f"Original JSON config: {input_path}")
    print(f"New YAML config: {output_path}")
    
    if args.backup:
        print(f"Backup of original config: {backup_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())