# Tool Gating MCP: Phase 2 Implementation Plan
# Complete macOS App with Advanced IDE Integration & OAuth Support

## Current Status Summary
### ✅ Completed:
- PyInstaller + uv build system working
- App bundle creates successfully (`dist/ToolGatingMCP.app`)
- Backend FastAPI architecture with semantic search
- Partial GUI components (missing `gui/main_window.py`)
- JSON snippet processor exists but not integrated
- Basic credential management framework

### 🎯 Primary Objectives:

## 1. Complete macOS Menubar App
**Missing Critical Files:**
- `gui/main_window.py` (import error prevents launch)
- Menubar icon integration and visibility
- JSON snippet processor UI integration

**Requirements:**
- LSUIElement=true compliance (menubar-only, no dock icon)
- 22x22px anti-aliased icons for macOS
- Port 8001 for non-interference with existing installations

## 2. IDE Auto-Detection & Configuration Injection
**Target IDEs:**
- Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)
- VS Code with Continue extension
- Cursor IDE
- Other popular MCP-compatible clients

**Features:**
- Detect installed IDEs automatically
- Show current MCP server configurations
- Offer to inject Tool Gating MCP configuration
- Backup existing configs before modification
- Selective or bulk server import with preview

**Backend Requirements:**
- New API endpoints for IDE detection
- Configuration file parsers/writers
- Backup and restore utilities
- Validation for different IDE config formats

## 3. Enhanced JSON Snippet Processing
**Current:** Basic snippet processor exists but not accessible
**Enhancements:**
- Direct menubar access: "Import JSON Snippet..."
- Support multiple formats (Claude Desktop, direct server, etc.)
- Real-time validation and preview
- Batch processing for multiple servers
- Integration with secure ENV storage

## 4. OAuth Authentication System
**Requirements:**
- **Authentication State Detection:** Monitor MCP connection failures for auth-related errors
- **OAuth Flow Integration:** Capture OAuth URLs, present to user via GUI notifications
- **Token Management:** Store OAuth tokens securely via keyring, auto-refresh when possible
- **GUI Integration:** System notifications, in-app browser/webview for OAuth flow
- **Error Pattern Recognition:** Detect OAuth vs API key requirements from error responses

**OAuth Indicators:**
```python
oauth_indicators = [
    "authorization_required", "oauth_token_expired", 
    "authentication_url", "login_required", 
    "unauthorized", "token_invalid"
]
```

## 5. Dual-Layer Credential Management
**Non-Sensitive Environment Variables:**
- Store in plain configuration files (REGION, TIMEOUT, DEBUG_MODE, API_VERSION)
- Easy GUI editing with simple key-value interface
- No keyring overhead

**Sensitive Secrets:**
- Store in keyring with encrypted storage (API_KEY, CLIENT_SECRET, OAUTH_TOKEN)
- GUI shows masked values with reveal option
- Automatic detection of sensitive patterns
- Pattern-based auto-categorization during import

**UI Requirements:**
- Tabbed interface: "Environment" vs "Secrets"
- Clear visual distinction between sensitive/non-sensitive
- Migration path from plain to secure storage
- User confirmation for borderline cases

## 6. Advanced API Configuration
**OpenAI Integration:**
- API key management through secure storage
- Custom endpoint URL override (OpenRouter support)
- Model selection and configuration
- Token usage tracking and budgets

**OAuth CLI Integration:**
- Detect Claude CLI OAuth tokens
- Detect Gemini CLI credentials
- Offer to reuse existing authenticated sessions
- Fallback to manual API key entry

## 7. System Notification & Monitoring
**Authentication Alerts:**
- System tray notifications for auth requirements
- In-app notification center
- Auth requirement alerts with direct OAuth URL access
- Token expiry warnings

**Connection Monitoring:**
- Real-time MCP server health checks
- Authentication status indicators
- Automatic retry with new credentials
- Error response parsing and user guidance

## Technical Architecture Requirements:

### New Backend Services:
1. **`services/ide_detector.py`** - Detect and manage IDE configurations
2. **`services/credential_manager.py`** - Dual-layer storage (ENV vs Secrets)
3. **`services/oauth_manager.py`** - OAuth flow coordination and token management
4. **`services/auth_detector.py`** - Monitor connections and detect auth requirements
5. **`services/notification_manager.py`** - System alerts and GUI notifications
6. **`services/llm_client_manager.py`** - External LLM API management

### New API Endpoints:
- `/api/ides/detect` - List detected IDEs and configurations
- `/api/ides/configure` - Inject/update IDE configurations
- `/api/auth/oauth/initiate` - Start OAuth flow
- `/api/auth/oauth/callback` - Handle OAuth callbacks
- `/api/auth/status/{server_id}` - Get authentication status
- `/api/environments/config` - Manage plain ENV variables
- `/api/environments/secrets` - Manage secrets via keyring
- `/api/notifications/` - System notification management
- `/api/llm/configure` - External LLM API configuration

### Enhanced Models:
- IDE configuration schemas
- OAuth flow state management
- Credential storage models with sensitivity classification
- Authentication status tracking
- Notification and alert schemas

### Frontend Requirements:
1. **Complete GUI Implementation:**
   - Fix missing `main_window.py`
   - Integrate snippet processor into menubar
   - Create comprehensive tabbed interface

2. **New UI Components:**
   - IDE detection and configuration manager
   - Dual-layer credential management interface
   - OAuth authentication flow handling
   - System notification center
   - API configuration panels
   - Import/export wizards with previews

### Security & Dependencies:
- `keyring` - Secure credential storage
- OAuth libraries for authentication flows
- WebView component for OAuth flows
- Pattern matching for sensitive data detection
- Secure token storage and automatic refresh

### Success Criteria:
1. ✅ Menubar app launches with visible icon
2. ✅ Auto-detects installed IDEs and shows configurations
3. ✅ Can import JSON snippets with full validation
4. ✅ Handles OAuth authentication flows automatically
5. ✅ Separates ENV variables from secrets with appropriate storage
6. ✅ Provides comprehensive credential and API management
7. ✅ Displays authentication status and handles failures gracefully
8. ✅ Successfully injects Tool Gating MCP config into detected IDEs
9. ✅ Creates distributable DMG with all dependencies included
10. ✅ Maintains port 8001 isolation and migration utilities

### Distribution Strategy:
**DMG Installation Benefits:**
- Self-contained with all Python dependencies
- No separate Python/uv installation required
- Automatic code signing for security
- Standard macOS installation experience
- Dependency verification and setup wizards included
- OAuth callback URL registration handling

## Implementation Priority:

### Phase 2A - Core GUI Completion
1. Create missing `gui/main_window.py`
2. Fix menubar icon visibility
3. Integrate JSON snippet processor into UI
4. Complete basic app functionality

### Phase 2B - Credential Management
1. Implement dual-layer credential storage
2. Add keyring integration for sensitive data
3. Create credential management UI
4. Pattern-based sensitive data detection

### Phase 2C - IDE Integration
1. Build IDE detection system
2. Implement configuration injection
3. Add backup/restore capabilities
4. Create import/export wizards

### Phase 2D - OAuth & Authentication
1. Implement OAuth flow handling
2. Add authentication state monitoring
3. Create notification system
4. Build OAuth callback handling

### Phase 2E - Advanced Features
1. External LLM API integration
2. Advanced monitoring and alerting
3. Migration utilities
4. DMG packaging improvements

This comprehensive implementation will create a professional-grade MCP management system that handles the complete lifecycle from detection through secure deployment, with modern OAuth support and intelligent credential management.