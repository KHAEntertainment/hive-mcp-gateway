#!/usr/bin/env python3

print("=== TEST IMPORT SCRIPT STARTING ===")

try:
    from src.hive_mcp_gateway.main import app
    print("=== IMPORT SUCCESSFUL ===")
    print(f"App: {app}")
    
    # Try to run the app directly with uvicorn
    import uvicorn
    print("=== STARTING UVICORN SERVER ===")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
    
except Exception as e:
    print(f"=== IMPORT OR EXECUTION FAILED ===")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("=== TEST IMPORT SCRIPT ENDING ===")
