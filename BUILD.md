# Building Hive MCP Gateway for macOS

This document explains how to build Hive MCP Gateway as a native macOS application bundle.

## Prerequisites

- macOS (tested on macOS 15.6)
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- PyQt6 (automatically installed with uv)

## Quick Start

The easiest way to build the app is using the provided shell script:

```bash
# Build app bundle only
./build_macos.sh

# Build app bundle and create DMG installer
./build_macos.sh --dmg
```

## Manual Build

If you prefer to run the build manually:

```bash
# Install PyInstaller to dev dependencies (first time only)
uv add --group dev "pyinstaller>=6.0.0"

# Sync dependencies
uv sync

# Build the app bundle
uv run python build/macos_bundle.py

# Or build with DMG
uv run python build/macos_bundle.py --dmg
```

## Build Options

The build script supports several options:

- `--dmg`: Also create a DMG installer for distribution
- `--add-deps`: Add PyInstaller to project dependencies

## Output

After a successful build, you'll find:

- **App Bundle**: `dist/HiveMCPGateway.app` - The macOS application bundle
- **DMG Installer** (if --dmg was used): `dist/HiveMCPGateway-Installer.dmg`

## App Bundle Features

The created app bundle has the following characteristics:

- **Menubar-only app**: Uses `LSUIElement=true` to run only in the menubar (no dock icon)
- **Native macOS**: Properly signed and structured as a macOS app bundle
- **Self-contained**: Includes all Python dependencies and the Hive MCP Gateway server
- **Port 8001**: Configured to run on port 8001 (vs 8000 for development) to allow side-by-side operation

## Troubleshooting

### PyInstaller Not Found

If you see "ModuleNotFoundError: No module named 'PyInstaller'", the build script will automatically install it:

```bash
uv run python build/macos_bundle.py --add-deps
```

### Virtual Environment Issues

Make sure you're running in the correct uv environment:

```bash
uv sync
# Then run build commands
```

### Missing Icon

The build will work without an icon but will show a warning. To add a custom icon:

1. Create `gui/assets/icon.icns`
2. The build script will automatically include it

### DMG Creation Issues

DMG creation requires the `create-dmg` tool:

```bash
brew install create-dmg
```

## Development vs Production

- **Development**: Use `uv run python src/tool_gating_mcp/main.py` (port 8000)
- **Production**: Use the app bundle (port 8001)

This allows both versions to run simultaneously for testing and migration.

## Code Signing

For distribution outside of personal use, you'll need to code sign the app bundle with an Apple Developer ID. The build script includes placeholder configuration for this.

## File Structure

The build process creates:

```
dist/
├── HiveMCPGateway.app/          # macOS app bundle
│   ├── Contents/
│   │   ├── Info.plist          # App metadata (LSUIElement=true)
│   │   ├── MacOS/              # Executable
│   │   ├── Resources/          # Python code and dependencies
│   │   └── Frameworks/         # PyQt6 and other frameworks
└── HiveMCPGateway-Installer.dmg # DMG installer (if created)
```