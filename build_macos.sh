#!/bin/bash

# Build macOS app bundle for Hive MCP Gateway
# This script ensures the proper uv environment is used

set -e  # Exit on error

echo "🚀 Building macOS app bundle for Hive MCP Gateway"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Sync dependencies to ensure we have everything
echo "📦 Syncing dependencies with uv..."
uv sync

# Run the build script with uv
echo "🔨 Building app bundle..."
if [ "$1" = "--dmg" ]; then
    uv run python build/macos_bundle.py --dmg
else
    uv run python build/macos_bundle.py
fi

echo "✅ Build complete!"