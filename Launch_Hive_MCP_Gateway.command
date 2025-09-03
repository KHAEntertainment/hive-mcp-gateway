#!/bin/bash

# Hive MCP Gateway Desktop Launcher
# Double-click this file to launch or relaunch the application

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Project directory (assuming .command file is in project root)
PROJECT_DIR="$SCRIPT_DIR"

# App name for process identification
APP_NAME="hive-mcp-gateway"
PYTHON_SCRIPT="run_gui.py"
VENV_DIR="$PROJECT_DIR/.venv"

echo "🚀 Hive MCP Gateway Launcher"
echo "=================================="

# Function to check if app is running
check_running() {
    pgrep -f "$PYTHON_SCRIPT" > /dev/null
}

# Function to kill existing instances
kill_existing() {
    echo "🔄 Detecting existing instances..."
    
    # Find and kill Python processes running our GUI
    PIDS=$(pgrep -f "$PYTHON_SCRIPT")
    
    if [ ! -z "$PIDS" ]; then
        echo "🛑 Found running instance(s). Terminating..."
        for PID in $PIDS; do
            echo "   Killing process $PID"
            kill -TERM "$PID" 2>/dev/null
        done
        
        # Wait a moment for graceful shutdown
        sleep 2
        
        # Force kill if still running
        REMAINING_PIDS=$(pgrep -f "$PYTHON_SCRIPT")
        if [ ! -z "$REMAINING_PIDS" ]; then
            echo "   Force killing remaining processes..."
            for PID in $REMAINING_PIDS; do
                kill -KILL "$PID" 2>/dev/null
            done
        fi
        
        echo "✅ Previous instances terminated"
    else
        echo "ℹ️  No existing instances found"
    fi
}

# Function to setup virtual environment
setup_venv() {
    echo "🐍 Setting up Python environment..."
    
    # Check if virtual environment exists
    if [ -d "$VENV_DIR" ]; then
        echo "✅ Found virtual environment: $VENV_DIR"
        
        # Activate virtual environment
        source "$VENV_DIR/bin/activate"
        echo "🔌 Virtual environment activated"
        
        # Verify activation worked
        if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
            echo "✅ Virtual environment confirmed active"
            echo "🐍 Using Python: $(which python)"
        else
            echo "⚠️  Virtual environment activation may have failed"
            echo "🐍 Using Python: $(which python3)"
        fi
    else
        echo "⚠️  No virtual environment found at $VENV_DIR"
        echo "🐍 Using system Python: $(which python3)"
        
        if ! command -v python3 &> /dev/null; then
            echo "❌ Error: Python 3 not found"
            echo "   Please install Python 3.12+ to run Hive MCP Gateway"
            exit 1
        fi
    fi
}

# Function to check dependencies
check_dependencies() {
    echo "📦 Checking dependencies..."
    
    # Test import of key dependencies
    python -c "import fastapi, PyQt6" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Core dependencies available"
    else
        echo "⚠️  Some dependencies may be missing"
        echo "📥 You may need to run: pip install -e ."
    fi
}

# Function to launch the app
launch_app() {
    echo "🚀 Launching Hive MCP Gateway..."
    echo "📁 Project directory: $PROJECT_DIR"
    
    # Change to project directory
    cd "$PROJECT_DIR" || {
        echo "❌ Error: Could not change to project directory: $PROJECT_DIR"
        echo "   Make sure this .command file is in the project root"
        exit 1
    }
    
    # Check if Python script exists
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        echo "❌ Error: $PYTHON_SCRIPT not found in $PROJECT_DIR"
        echo "   Make sure this .command file is in the correct location"
        exit 1
    fi
    
    # Setup virtual environment
    setup_venv
    
    # Check dependencies
    check_dependencies
    
    # Set up environment
    export PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/src:$PYTHONPATH"
    echo "📦 Python path configured"
    echo ""
    echo "Starting application..."
    echo "==============================================="
    
    # Launch the application using the activated Python
    python "$PYTHON_SCRIPT"
    
    # Check exit status
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo "✅ Hive MCP Gateway exited normally"
    else
        echo ""
        echo "❌ Hive MCP Gateway exited with error code: $EXIT_CODE"
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   1. Ensure all dependencies are installed: pip install -e ."
        echo "   2. Check that Python 3.12+ is installed"
        echo "   3. Verify the virtual environment is properly set up"
    fi
}

# Main execution
echo "🔍 Checking for existing instances..."

# Always kill existing instances for clean restart
kill_existing

echo ""
echo "🎯 Starting fresh instance..."
launch_app

echo ""
echo "👋 Launcher finished. You can close this terminal window."
echo ""

# Keep terminal open briefly so user can see the result
sleep 3