#!/bin/bash
"""
Hive MCP Gateway Build Wrapper
Simple script to build Hive MCP Gateway for macOS
"""

set -e  # Exit on any error

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Default values
TARGET="dmg"
CONFIG="release"
CLEAN=false
VERIFY=true

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Hive MCP Gateway Build Script

Usage: $0 [OPTIONS]

OPTIONS:
    -t, --target TARGET        Build target (app_bundle, dmg, standalone_dmg, docker, all) [default: dmg]
    -c, --config CONFIG        Build configuration (debug, release, distribution) [default: release]
    -i, --identity IDENTITY    Code signing identity for macOS builds
    -n, --notarize            Enable notarization (requires Apple ID credentials)
    --apple-id ID             Apple ID for notarization
    --app-password PASSWORD   App-specific password for notarization  
    --team-id ID              Team ID for notarization
    --clean                   Clean build before starting
    --no-verify               Skip build verification
    --standalone              Create standalone DMG with embedded Python
    -h, --help                Show this help message

EXAMPLES:
    # Build a standard DMG
    $0

    # Build and code sign DMG
    $0 --identity "Developer ID Application: Your Name (TEAMID)"

    # Build standalone DMG with embedded Python
    $0 --standalone

    # Build everything (app bundle, DMG, Docker)
    $0 --target all --clean

    # Build for distribution with notarization
    $0 --config distribution --identity "Your Identity" --notarize \\
       --apple-id "your@email.com" --app-password "xxxx-xxxx-xxxx-xxxx" --team-id "TEAMID"

EOF
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if we're on macOS
    if [[ "$(uname)" != "Darwin" ]]; then
        print_error "This script requires macOS for building .app bundles and DMGs"
        exit 1
    fi
    
    # Check for required tools
    local missing_tools=()
    
    if ! command -v uv &> /dev/null; then
        missing_tools+=("uv")
    fi
    
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi
    
    # Check for macOS development tools (for DMG builds)
    if [[ "$TARGET" == "dmg" ]] || [[ "$TARGET" == "standalone_dmg" ]] || [[ "$TARGET" == "all" ]]; then
        if ! command -v hdiutil &> /dev/null; then
            missing_tools+=("hdiutil")
        fi
        
        if ! command -v codesign &> /dev/null; then
            missing_tools+=("codesign")
        fi
    fi
    
    # Check for Docker (if building Docker images)
    if [[ "$TARGET" == "docker" ]] || [[ "$TARGET" == "all" ]]; then
        if ! command -v docker &> /dev/null; then
            missing_tools+=("docker")
        fi
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_error "Please install the missing tools and try again"
        exit 1
    fi
    
    print_status "Prerequisites check passed"
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--target)
                TARGET="$2"
                shift 2
                ;;
            -c|--config)
                CONFIG="$2"
                shift 2
                ;;
            -i|--identity)
                CODESIGN_IDENTITY="$2"
                shift 2
                ;;
            -n|--notarize)
                NOTARIZE=true
                shift
                ;;
            --apple-id)
                APPLE_ID="$2"
                shift 2
                ;;
            --app-password)
                APP_PASSWORD="$2"
                shift 2
                ;;
            --team-id)
                TEAM_ID="$2"
                shift 2
                ;;
            --clean)
                CLEAN=true
                shift
                ;;
            --no-verify)
                VERIFY=false
                shift
                ;;
            --standalone)
                TARGET="standalone_dmg"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Build the project
build_project() {
    print_status "Starting Hive MCP Gateway build..."
    print_status "Target: $TARGET, Configuration: $CONFIG"
    
    # Get script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    # Prepare build command
    local build_cmd=(
        "uv" "run" "python3" "$SCRIPT_DIR/build.py"
        "--target" "$TARGET"
        "--config" "$CONFIG"
        "--project-root" "$PROJECT_ROOT"
    )
    
    # Add optional arguments
    if [[ "$CLEAN" == "true" ]]; then
        build_cmd+=("--clean")
    fi
    
    if [[ "$VERIFY" == "false" ]]; then
        build_cmd+=("--no-verify")
    fi
    
    if [[ -n "$CODESIGN_IDENTITY" ]]; then
        build_cmd+=("--codesign-identity" "$CODESIGN_IDENTITY")
    fi
    
    if [[ "$NOTARIZE" == "true" ]]; then
        build_cmd+=("--notarize")
        
        if [[ -n "$APPLE_ID" ]]; then
            build_cmd+=("--apple-id" "$APPLE_ID")
        fi
        
        if [[ -n "$APP_PASSWORD" ]]; then
            build_cmd+=("--app-password" "$APP_PASSWORD")
        fi
        
        if [[ -n "$TEAM_ID" ]]; then
            build_cmd+=("--team-id" "$TEAM_ID")
        fi
    fi
    
    # Execute build
    print_status "Executing build command..."
    print_status "Command: ${build_cmd[*]}"
    
    if "${build_cmd[@]}"; then
        print_status "Build completed successfully!"
        
        # Show build artifacts
        if [[ -d "$PROJECT_ROOT/dist" ]]; then
            print_status "Build artifacts:"
            ls -la "$PROJECT_ROOT/dist"
        fi
    else
        print_error "Build failed!"
        exit 1
    fi
}

# Validate notarization settings
validate_notarization() {
    if [[ "$NOTARIZE" == "true" ]]; then
        if [[ -z "$APPLE_ID" ]] || [[ -z "$APP_PASSWORD" ]] || [[ -z "$TEAM_ID" ]]; then
            print_error "Notarization requires --apple-id, --app-password, and --team-id"
            exit 1
        fi
        
        if [[ -z "$CODESIGN_IDENTITY" ]]; then
            print_error "Notarization requires code signing (--identity)"
            exit 1
        fi
    fi
}

# Main execution
main() {
    print_status "Hive MCP Gateway Build Script"
    print_status "============================="
    
    # Parse arguments
    parse_arguments "$@"
    
    # Validate settings
    validate_notarization
    
    # Check prerequisites
    check_prerequisites
    
    # Build the project
    build_project
    
    print_status "All done! 🎉"
}

# Execute main function with all arguments
main "$@"