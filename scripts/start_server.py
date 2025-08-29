#!/usr/bin/env python3
"""Start the server directly"""

import uvicorn
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    print("Starting Tool Gating MCP server...")
    uvicorn.run(
        "hive_mcp_gateway.main:app",
        host="127.0.0.1",
        port=8001,
        reload=False,
        log_level="info"
    )