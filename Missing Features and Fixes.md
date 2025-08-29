# Hive MCP Gateway - Missing Features and Implementation Plan

## Problems and Notes:

Main Window: Shows mcp-proxy not detected. - I have this installed, and if I didn't it should be trying to automatically install the dependency or guide me through it. Despite it saying it's not installed, it lets me start the service.

It's saying Claude Desktop is not detected, but I have Claude Desktop installed and it's even open right now. It should also detect Claude-Code, Gemini CLI, Qwen Code, etc and other major IDEs and agentic coding apps that are mainstream.

It's still saying "Tool Gating MCP" instead of Hive MCP Gateway in the GUI

Import JSON Snippet window from the menubar dropdown is exactly what I envisioned. If I click "Configuration" first though and then click "Add Server" from there, it's a completely different GUI window that's much clunkier to use, and redundant. Make the "MCP Snippet Processing" window that launches direct from the menubar the only unified one. **THIS is the one to keep**

The ENV and Secrets control system I described I see no mention to at all. Did it get skipped?
The ability to set your OpenAI API Key, Choose to use Claude Code or Gemini CLI's OAuth authentication for the internal LLM, or change the URL/Provider/Model to say, Openrouter, is also missing completely.

From the application main window, you should have buttons to get to the configuration screen and the "Add MCP Server" window that I just mentioned, instead of having to go back to the menubar for those when you already have the "main" window open.

Aside from Hive labeling, we need to use the hive Logo and Icons.

Should I start a new quest to tackle these, or tack them onto the existing quest? What's the better practice here? If I start a new quest for organization will it lack some of the context from the last one?

---

## 🎯 Implementation Plan


### **Current State & Goal**
- **Current State**: Working GUI application with menubar icon, basic functionality established
- **Goal**: Transform into fully-featured Hive MCP Gateway with proper branding, IDE detection, credential management, and unified UI

### **Assets Provided**

#### **Logos**
- `the_hive_logo_fullsize_sq.png` (for favicon generation)
- `the_hive_logo_banner.png` (horizontal layout)
- `the_hive_logo.png` (square with text)

#### **IDE Detection & OAuth Integration**
- **Claude Code**: 
  - Documentation: https://context7.com/anthropics/claude-code-sdk-python/llms.txt
  - Repository: `/Users/bbrenner/Documents/Scripting Projects/hive-sources/claude-code`
- **Gemini CLI**: 
  - Documentation: https://context7.com/google-gemini/gemini-cli/llms.txt
  - Repository: `/Users/bbrenner/Documents/Scripting Projects/hive-sources/gemini-cli`

#### **IDE Detection Only**
- **Cursor**: https://context7.com/websites/cursor_en/llms.txt
- **Qwen Code**: https://context7.com/qwenlm/qwen-code/llms.txt
- **VS Code**: https://context7.com/microsoft/vscode/llms.txt
- **Claude Desktop**: Standard MCP detection

---

## 🔧 Implementation Tasks

### **1. Branding & Asset Integration**
- [ ] Update all "Tool Gating MCP" → "Hive MCP Gateway" throughout codebase
- [ ] Implement Python-based logo resizing for optimal dimensions:
  - [ ] Menubar icons: 22x22px with anti-aliasing
  - [ ] Application icons: Standard macOS sizes (16, 32, 64, 128, 256, 512, 1024px)
  - [ ] Favicon generation from `the_hive_logo_fullsize_sq.png`
- [ ] Integrate "MCP Gateway" text with logo variants as needed

### **2. UI Unification & Navigation**
- [ ] **Primary Interface**: Keep existing JSON snippet processor as the unified MCP server addition method
- [ ] **Remove Redundancy**: Eliminate/redirect the clunky configuration editor "Add Server" dialog
- [ ] **Main Window Enhancement**: Add navigation buttons for Configuration and "Add MCP Server" (snippet processor)
- [ ] **Consistent Access**: Ensure all features accessible from both menubar and main window

### **3. Advanced IDE Detection & Configuration Injection**
- [ ] **Detection Logic**: Scan for installed IDEs using provided documentation/repos
- [ ] **Configuration Paths**: Auto-locate IDE config files
- [ ] **Backup System**: Create backups before config injection
- [ ] **Selective Import**: Allow user choice of which servers to inject
- [ ] **Status Display**: Show detected IDEs in main window with configuration status

### **4. OAuth Credential Management System**
- [ ] **Claude Code Integration**: Extract and implement OAuth flow from provided repo
- [ ] **Gemini CLI Integration**: Extract and implement OAuth flow from provided repo
- [ ] **Secure Storage**: Use Python keyring for OAuth tokens and API keys
- [ ] **GUI Integration**: OAuth dialogs, status indicators, re-authentication support
- [ ] **Auto-Detection**: Detect when MCP servers require OAuth and prompt user

### **5. ENV/Secrets Management**
- [ ] **Dual-Layer System**:
  - [ ] Sensitive data (API keys, tokens) → keyring
  - [ ] Non-sensitive data (REGION, TIMEOUT) → plain config files
- [ ] **Pattern Detection**: Auto-identify sensitive values during import
- [ ] **Masked Display**: Hide sensitive values in GUI with reveal option
- [ ] **Management Interface**: Add/remove/replace credentials easily

### **6. External LLM API Configuration**
- [ ] **OpenAI API Key**: Secure storage and configuration
- [ ] **Provider Selection**: Support for OpenRouter and other services
- [ ] **Endpoint Override**: Custom URL configuration
- [ ] **Model Selection**: Dropdown for available models per provider

### **7. Enhanced Dependency Detection**
- [ ] **Fix Current Issues**: Properly detect installed mcp-proxy and Claude Desktop
- [ ] **Comprehensive Detection**: All mentioned IDEs and tools
- [ ] **Auto-Installation Guidance**: When possible, guide through installation
- [ ] **Fallback Options**: Alternative methods when detection fails

---

## 📝 Technical Requirements

- **Package Manager**: Use `uv` for all dependencies
- **Port Configuration**: 8001 (non-interference with existing installations)
- **macOS Integration**: LSUIElement=true, proper app bundle structure
- **Security**: All credential operations via keyring
- **Code Quality**: Follow existing patterns and error handling

---

## 🎁 Deliverables

1. ✅ Fully branded Hive MCP Gateway application
2. ✅ Unified, intuitive UI with proper navigation
3. ✅ Comprehensive IDE detection and configuration injection
4. ✅ OAuth authentication system for Claude Code and Gemini CLI
5. ✅ Complete ENV/secrets management system
6. ✅ External LLM API configuration interface
7. ✅ Enhanced dependency detection with guidance
8. ✅ Proper asset integration with Python-resized logos/icons