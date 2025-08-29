"""IDE detection service for auto-detecting installed IDEs and their configurations."""

import json
import logging
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IDEType(Enum):
    """Supported IDE types."""
    CLAUDE_DESKTOP = "claude_desktop"
    CLAUDE_CODE = "claude_code"
    VS_CODE = "vscode"
    CURSOR = "cursor"
    VS_CODE_INSIDERS = "vscode_insiders"
    GEMINI_CLI = "gemini_cli"
    QWEN_CODE = "qwen_code"
    CODEIUM = "codeium"
    ZEPHYR = "zephyr"
    SUBLIME_TEXT = "sublime_text"
    JETBRAINS_PYCHARM = "pycharm"
    JETBRAINS_WEBSTORM = "webstorm"
    JETBRAINS_IDEA = "intellij_idea"
    NEOVIM = "neovim"
    VIM = "vim"
    ATOM = "atom"


@dataclass
class IDEInfo:
    """Information about a detected IDE."""
    ide_type: IDEType
    name: str
    version: Optional[str]
    executable_path: Path
    config_path: Path
    is_installed: bool
    config_exists: bool
    mcp_servers: Dict[str, Any]
    backup_available: bool = False


class IDEDetector:
    """Detects installed IDEs and their MCP configurations."""
    
    def __init__(self):
        """Initialize the IDE detector."""
        self.system = platform.system()
        self.home_dir = Path.home()
        
        # IDE detection patterns by platform
        self.ide_patterns = self._get_ide_patterns()
    
    def _get_ide_patterns(self) -> Dict[IDEType, Dict[str, Any]]:
        """Get IDE detection patterns for the current platform."""
        if self.system == "Darwin":  # macOS
            return {
                IDEType.CLAUDE_DESKTOP: {
                    "name": "Claude Desktop",
                    "executable_paths": [
                        "/Applications/Claude.app",
                        self.home_dir / "Applications/Claude.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Claude/claude_desktop_config.json"
                },
                IDEType.CLAUDE_CODE: {
                    "name": "Claude Code",
                    "executable_paths": [
                        "/Applications/Claude Code.app",
                        self.home_dir / "Applications/Claude Code.app",
                        "/usr/local/bin/claude-code",
                        self.home_dir / ".local/bin/claude-code"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Claude Code/config.json",
                    "oauth_supported": True
                },
                IDEType.GEMINI_CLI: {
                    "name": "Gemini CLI",
                    "executable_paths": [
                        "/usr/local/bin/gemini",
                        "/opt/homebrew/bin/gemini",
                        self.home_dir / ".local/bin/gemini",
                        "/Applications/Gemini CLI.app"
                    ],
                    "config_path": self.home_dir / ".config/gemini/config.yaml",
                    "oauth_supported": True
                },
                IDEType.QWEN_CODE: {
                    "name": "Qwen Code",
                    "executable_paths": [
                        "/Applications/Qwen Code.app",
                        self.home_dir / "Applications/Qwen Code.app",
                        "/usr/local/bin/qwen-code"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Qwen Code/settings.json"
                },
                IDEType.VS_CODE: {
                    "name": "Visual Studio Code",
                    "executable_paths": [
                        "/Applications/Visual Studio Code.app",
                        self.home_dir / "Applications/Visual Studio Code.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Code/User/settings.json"
                },
                IDEType.VS_CODE_INSIDERS: {
                    "name": "Visual Studio Code - Insiders",
                    "executable_paths": [
                        "/Applications/Visual Studio Code - Insiders.app",
                        self.home_dir / "Applications/Visual Studio Code - Insiders.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Code - Insiders/User/settings.json"
                },
                IDEType.CURSOR: {
                    "name": "Cursor",
                    "executable_paths": [
                        "/Applications/Cursor.app",
                        self.home_dir / "Applications/Cursor.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Cursor/User/settings.json"
                },
                IDEType.CODEIUM: {
                    "name": "Codeium",
                    "executable_paths": [
                        "/Applications/Codeium.app",
                        self.home_dir / "Applications/Codeium.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Codeium/settings.json"
                },
                IDEType.SUBLIME_TEXT: {
                    "name": "Sublime Text",
                    "executable_paths": [
                        "/Applications/Sublime Text.app",
                        self.home_dir / "Applications/Sublime Text.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/Sublime Text/Packages/User/Preferences.sublime-settings"
                },
                IDEType.JETBRAINS_PYCHARM: {
                    "name": "PyCharm",
                    "executable_paths": [
                        "/Applications/PyCharm.app",
                        "/Applications/PyCharm CE.app",
                        self.home_dir / "Applications/PyCharm.app",
                        self.home_dir / "Applications/PyCharm CE.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/JetBrains/PyCharm*/options/ide.general.xml"
                },
                IDEType.JETBRAINS_WEBSTORM: {
                    "name": "WebStorm",
                    "executable_paths": [
                        "/Applications/WebStorm.app",
                        self.home_dir / "Applications/WebStorm.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/JetBrains/WebStorm*/options/ide.general.xml"
                },
                IDEType.JETBRAINS_IDEA: {
                    "name": "IntelliJ IDEA",
                    "executable_paths": [
                        "/Applications/IntelliJ IDEA.app",
                        "/Applications/IntelliJ IDEA CE.app",
                        self.home_dir / "Applications/IntelliJ IDEA.app",
                        self.home_dir / "Applications/IntelliJ IDEA CE.app"
                    ],
                    "config_path": self.home_dir / "Library/Application Support/JetBrains/IntelliJIdea*/options/ide.general.xml"
                },
                IDEType.NEOVIM: {
                    "name": "Neovim",
                    "executable_paths": [
                        "/usr/local/bin/nvim",
                        "/opt/homebrew/bin/nvim",
                        "/usr/bin/nvim"
                    ],
                    "config_path": self.home_dir / ".config/nvim/init.lua"
                },
                IDEType.VIM: {
                    "name": "Vim",
                    "executable_paths": [
                        "/usr/bin/vim",
                        "/usr/local/bin/vim",
                        "/opt/homebrew/bin/vim"
                    ],
                    "config_path": self.home_dir / ".vimrc"
                }
            }
        elif self.system == "Windows":
            return {
                IDEType.CLAUDE_DESKTOP: {
                    "name": "Claude Desktop",
                    "executable_paths": [
                        Path("C:/Program Files/Claude/Claude.exe"),
                        self.home_dir / "AppData/Local/Programs/Claude/Claude.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Claude/claude_desktop_config.json"
                },
                IDEType.CLAUDE_CODE: {
                    "name": "Claude Code",
                    "executable_paths": [
                        Path("C:/Program Files/Claude Code/claude-code.exe"),
                        self.home_dir / "AppData/Local/Programs/Claude Code/claude-code.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Claude Code/config.json",
                    "oauth_supported": True
                },
                IDEType.GEMINI_CLI: {
                    "name": "Gemini CLI",
                    "executable_paths": [
                        Path("C:/Program Files/Gemini CLI/gemini.exe"),
                        self.home_dir / "AppData/Local/Programs/Gemini CLI/gemini.exe",
                        self.home_dir / "AppData/Local/bin/gemini.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Gemini/config.yaml",
                    "oauth_supported": True
                },
                IDEType.QWEN_CODE: {
                    "name": "Qwen Code",
                    "executable_paths": [
                        Path("C:/Program Files/Qwen Code/qwen-code.exe"),
                        self.home_dir / "AppData/Local/Programs/Qwen Code/qwen-code.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Qwen Code/settings.json"
                },
                IDEType.VS_CODE: {
                    "name": "Visual Studio Code",
                    "executable_paths": [
                        Path("C:/Program Files/Microsoft VS Code/Code.exe"),
                        Path("C:/Program Files (x86)/Microsoft VS Code/Code.exe"),
                        self.home_dir / "AppData/Local/Programs/Microsoft VS Code/Code.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Code/User/settings.json"
                },
                IDEType.VS_CODE_INSIDERS: {
                    "name": "Visual Studio Code - Insiders",
                    "executable_paths": [
                        Path("C:/Program Files/Microsoft VS Code Insiders/Code - Insiders.exe"),
                        self.home_dir / "AppData/Local/Programs/Microsoft VS Code Insiders/Code - Insiders.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Code - Insiders/User/settings.json"
                },
                IDEType.CURSOR: {
                    "name": "Cursor",
                    "executable_paths": [
                        Path("C:/Program Files/Cursor/Cursor.exe"),
                        self.home_dir / "AppData/Local/Programs/Cursor/Cursor.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Cursor/User/settings.json"
                },
                IDEType.SUBLIME_TEXT: {
                    "name": "Sublime Text",
                    "executable_paths": [
                        Path("C:/Program Files/Sublime Text/sublime_text.exe"),
                        Path("C:/Program Files (x86)/Sublime Text/sublime_text.exe")
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/Sublime Text/Packages/User/Preferences.sublime-settings"
                },
                IDEType.JETBRAINS_PYCHARM: {
                    "name": "PyCharm",
                    "executable_paths": [
                        Path("C:/Program Files/JetBrains/PyCharm Community Edition*/bin/pycharm64.exe"),
                        Path("C:/Program Files/JetBrains/PyCharm*/bin/pycharm64.exe")
                    ],
                    "config_path": self.home_dir / "AppData/Roaming/JetBrains/PyCharm*/options/ide.general.xml"
                },
                IDEType.NEOVIM: {
                    "name": "Neovim",
                    "executable_paths": [
                        Path("C:/Program Files/Neovim/bin/nvim.exe"),
                        self.home_dir / "AppData/Local/nvim/nvim.exe"
                    ],
                    "config_path": self.home_dir / "AppData/Local/nvim/init.lua"
                }
            }
        else:  # Linux
            return {
                IDEType.CLAUDE_DESKTOP: {
                    "name": "Claude Desktop",
                    "executable_paths": [
                        Path("/usr/bin/claude"),
                        Path("/usr/local/bin/claude"),
                        self.home_dir / ".local/bin/claude"
                    ],
                    "config_path": self.home_dir / ".config/Claude/claude_desktop_config.json"
                },
                IDEType.CLAUDE_CODE: {
                    "name": "Claude Code",
                    "executable_paths": [
                        Path("/usr/bin/claude-code"),
                        Path("/usr/local/bin/claude-code"),
                        self.home_dir / ".local/bin/claude-code",
                        Path("/snap/bin/claude-code")
                    ],
                    "config_path": self.home_dir / ".config/claude-code/config.json",
                    "oauth_supported": True
                },
                IDEType.GEMINI_CLI: {
                    "name": "Gemini CLI",
                    "executable_paths": [
                        Path("/usr/bin/gemini"),
                        Path("/usr/local/bin/gemini"),
                        self.home_dir / ".local/bin/gemini",
                        Path("/snap/bin/gemini")
                    ],
                    "config_path": self.home_dir / ".config/gemini/config.yaml",
                    "oauth_supported": True
                },
                IDEType.QWEN_CODE: {
                    "name": "Qwen Code",
                    "executable_paths": [
                        Path("/usr/bin/qwen-code"),
                        Path("/usr/local/bin/qwen-code"),
                        self.home_dir / ".local/bin/qwen-code",
                        Path("/snap/bin/qwen-code")
                    ],
                    "config_path": self.home_dir / ".config/qwen-code/settings.json"
                },
                IDEType.VS_CODE: {
                    "name": "Visual Studio Code",
                    "executable_paths": [
                        Path("/usr/bin/code"),
                        Path("/usr/local/bin/code"),
                        Path("/snap/bin/code")
                    ],
                    "config_path": self.home_dir / ".config/Code/User/settings.json"
                },
                IDEType.VS_CODE_INSIDERS: {
                    "name": "Visual Studio Code - Insiders",
                    "executable_paths": [
                        Path("/usr/bin/code-insiders"),
                        Path("/usr/local/bin/code-insiders")
                    ],
                    "config_path": self.home_dir / ".config/Code - Insiders/User/settings.json"
                },
                IDEType.CURSOR: {
                    "name": "Cursor",
                    "executable_paths": [
                        Path("/usr/bin/cursor"),
                        Path("/usr/local/bin/cursor"),
                        self.home_dir / ".local/bin/cursor",
                        Path("/snap/bin/cursor")
                    ],
                    "config_path": self.home_dir / ".config/Cursor/User/settings.json"
                },
                IDEType.SUBLIME_TEXT: {
                    "name": "Sublime Text",
                    "executable_paths": [
                        Path("/usr/bin/subl"),
                        Path("/usr/local/bin/subl"),
                        Path("/snap/bin/subl")
                    ],
                    "config_path": self.home_dir / ".config/sublime-text/Packages/User/Preferences.sublime-settings"
                },
                IDEType.JETBRAINS_PYCHARM: {
                    "name": "PyCharm",
                    "executable_paths": [
                        Path("/usr/bin/pycharm"),
                        Path("/usr/local/bin/pycharm"),
                        self.home_dir / ".local/bin/pycharm",
                        Path("/snap/bin/pycharm-community")
                    ],
                    "config_path": self.home_dir / ".config/JetBrains/PyCharm*/options/ide.general.xml"
                },
                IDEType.NEOVIM: {
                    "name": "Neovim",
                    "executable_paths": [
                        Path("/usr/bin/nvim"),
                        Path("/usr/local/bin/nvim"),
                        self.home_dir / ".local/bin/nvim",
                        Path("/snap/bin/nvim")
                    ],
                    "config_path": self.home_dir / ".config/nvim/init.lua"
                },
                IDEType.VIM: {
                    "name": "Vim",
                    "executable_paths": [
                        Path("/usr/bin/vim"),
                        Path("/usr/local/bin/vim")
                    ],
                    "config_path": self.home_dir / ".vimrc"
                }
            }
    
    def detect_all_ides(self) -> List[IDEInfo]:
        """Detect all installed IDEs."""
        detected_ides = []
        
        for ide_type in IDEType:
            ide_info = self.detect_ide(ide_type)
            if ide_info:
                detected_ides.append(ide_info)
        
        return detected_ides
    
    def detect_ide(self, ide_type: IDEType) -> Optional[IDEInfo]:
        """Detect a specific IDE."""
        if ide_type not in self.ide_patterns:
            logger.warning(f"No detection pattern for IDE type: {ide_type}")
            return None
        
        pattern = self.ide_patterns[ide_type]
        
        # Find executable
        executable_path = None
        for path in pattern["executable_paths"]:
            if Path(path).exists():
                executable_path = Path(path)
                break
        
        if not executable_path:
            logger.debug(f"IDE {ide_type.value} not found")
            return None
        
        # Get version
        version = self._get_ide_version(ide_type, executable_path)
        
        # Check config
        config_path = Path(pattern["config_path"])
        config_exists = config_path.exists()
        
        # Load MCP servers if config exists
        mcp_servers = {}
        if config_exists:
            mcp_servers = self._load_mcp_servers(ide_type, config_path)
        
        # Check for backups
        backup_available = self._has_backup(config_path)
        
        return IDEInfo(
            ide_type=ide_type,
            name=pattern["name"],
            version=version,
            executable_path=executable_path,
            config_path=config_path,
            is_installed=True,
            config_exists=config_exists,
            mcp_servers=mcp_servers,
            backup_available=backup_available
        )
    
    def _get_ide_version(self, ide_type: IDEType, executable_path: Path) -> Optional[str]:
        """Get IDE version."""
        try:
            if ide_type == IDEType.CLAUDE_DESKTOP:
                return self._get_claude_version(executable_path)
            elif ide_type == IDEType.CLAUDE_CODE:
                return self._get_claude_code_version(executable_path)
            elif ide_type == IDEType.GEMINI_CLI:
                return self._get_gemini_cli_version(executable_path)
            elif ide_type == IDEType.QWEN_CODE:
                return self._get_qwen_code_version(executable_path)
            elif ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS]:
                return self._get_vscode_version(executable_path)
            elif ide_type == IDEType.CURSOR:
                return self._get_cursor_version(executable_path)
            elif ide_type == IDEType.SUBLIME_TEXT:
                return self._get_sublime_version(executable_path)
            elif ide_type in [IDEType.JETBRAINS_PYCHARM, IDEType.JETBRAINS_WEBSTORM, IDEType.JETBRAINS_IDEA]:
                return self._get_jetbrains_version(executable_path)
            elif ide_type == IDEType.NEOVIM:
                return self._get_neovim_version(executable_path)
            elif ide_type == IDEType.VIM:
                return self._get_vim_version(executable_path)
            else:
                return self._get_generic_version(executable_path)
        except Exception as e:
            logger.warning(f"Failed to get version for {ide_type.value}: {e}")
        
        return None
    
    def _get_claude_version(self, executable_path: Path) -> Optional[str]:
        """Get Claude Desktop version."""
        if self.system == "Darwin":
            # Try to read from Info.plist
            info_plist = executable_path / "Contents/Info.plist"
            if info_plist.exists():
                try:
                    import plistlib
                    with open(info_plist, 'rb') as f:
                        plist = plistlib.load(f)
                    return plist.get('CFBundleShortVersionString')
                except Exception as e:
                    logger.debug(f"Failed to read Claude plist: {e}")
        
        return "Unknown"
    
    def _get_claude_code_version(self, executable_path: Path) -> Optional[str]:
        """Get Claude Code version."""
        try:
            import subprocess
            result = subprocess.run(
                [str(executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
                
        except Exception as e:
            logger.debug(f"Failed to get Claude Code version: {e}")
        
        return "Unknown"
    
    def _get_gemini_cli_version(self, executable_path: Path) -> Optional[str]:
        """Get Gemini CLI version."""
        try:
            import subprocess
            result = subprocess.run(
                [str(executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
                
        except Exception as e:
            logger.debug(f"Failed to get Gemini CLI version: {e}")
        
        return "Unknown"
    
    def _get_qwen_code_version(self, executable_path: Path) -> Optional[str]:
        """Get Qwen Code version."""
        try:
            import subprocess
            result = subprocess.run(
                [str(executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
                
        except Exception as e:
            logger.debug(f"Failed to get Qwen Code version: {e}")
        
        return "Unknown"
    
    def _get_sublime_version(self, executable_path: Path) -> Optional[str]:
        """Get Sublime Text version."""
        try:
            import subprocess
            result = subprocess.run(
                [str(executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
                
        except Exception as e:
            logger.debug(f"Failed to get Sublime Text version: {e}")
        
        return "Unknown"
    
    def _get_jetbrains_version(self, executable_path: Path) -> Optional[str]:
        """Get JetBrains IDE version."""
        try:
            # For JetBrains IDEs, try to read from build.txt or product-info.json
            if self.system == "Darwin":
                build_file = executable_path / "Contents/Resources/build.txt"
                if build_file.exists():
                    return build_file.read_text().strip()
                    
                product_info = executable_path / "Contents/Resources/product-info.json"
                if product_info.exists():
                    import json
                    with open(product_info, 'r') as f:
                        info = json.load(f)
                    return info.get('version', 'Unknown')
                    
        except Exception as e:
            logger.debug(f"Failed to get JetBrains version: {e}")
        
        return "Unknown"
    
    def _get_neovim_version(self, executable_path: Path) -> Optional[str]:
        """Get Neovim version."""
        try:
            import subprocess
            result = subprocess.run(
                [str(executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    return lines[0].replace('NVIM ', '')
                
        except Exception as e:
            logger.debug(f"Failed to get Neovim version: {e}")
        
        return "Unknown"
    
    def _get_vim_version(self, executable_path: Path) -> Optional[str]:
        """Get Vim version."""
        try:
            import subprocess
            result = subprocess.run(
                [str(executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    # Extract version from first line like "VIM - Vi IMproved 8.2"
                    first_line = lines[0]
                    if 'VIM' in first_line:
                        parts = first_line.split()
                        for i, part in enumerate(parts):
                            if part.replace('.', '').isdigit():
                                return part
                
        except Exception as e:
            logger.debug(f"Failed to get Vim version: {e}")
        
        return "Unknown"
    
    def _get_generic_version(self, executable_path: Path) -> Optional[str]:
        """Get version for generic executables."""
        try:
            import subprocess
            
            # Try common version flags
            for flag in ["--version", "-v", "-V", "version"]:
                try:
                    result = subprocess.run(
                        [str(executable_path), flag],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip().split('\n')[0]
                        
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Failed to get generic version: {e}")
        
        return "Unknown"
    
    def _get_vscode_version(self, executable_path: Path) -> Optional[str]:
        """Get VS Code version."""
        try:
            import subprocess
            
            if self.system == "Darwin":
                # On macOS, use the binary inside the app bundle
                binary_path = executable_path / "Contents/Resources/app/bin/code"
                if not binary_path.exists():
                    binary_path = executable_path / "Contents/MacOS/Electron"
            else:
                binary_path = executable_path
            
            result = subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\\n')
                return lines[0] if lines else None
                
        except Exception as e:
            logger.debug(f"Failed to get VS Code version: {e}")
        
        return "Unknown"
    
    def _get_cursor_version(self, executable_path: Path) -> Optional[str]:
        """Get Cursor version."""
        try:
            import subprocess
            
            if self.system == "Darwin":
                binary_path = executable_path / "Contents/MacOS/Cursor"
            else:
                binary_path = executable_path
            
            result = subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\\n')
                return lines[0] if lines else None
                
        except Exception as e:
            logger.debug(f"Failed to get Cursor version: {e}")
        
        return "Unknown"
    
    def _load_mcp_servers(self, ide_type: IDEType, config_path: Path) -> Dict[str, Any]:
        """Load MCP servers from IDE config."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if ide_type == IDEType.CLAUDE_DESKTOP:
                return config.get('mcpServers', {})
            elif ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS, IDEType.CURSOR]:
                # VS Code/Cursor may have MCP settings in extensions or continue configuration
                continue_config = config.get('continue', {})
                return continue_config.get('mcpServers', {})
            
        except Exception as e:
            logger.error(f"Failed to load MCP servers from {config_path}: {e}")
        
        return {}
    
    def _has_backup(self, config_path: Path) -> bool:
        """Check if backup exists for the config file."""
        backup_path = config_path.with_suffix(f'{config_path.suffix}.hive-backup')
        return backup_path.exists()
    
    def get_claude_desktop_info(self) -> Optional[IDEInfo]:
        """Get Claude Desktop information specifically."""
        return self.detect_ide(IDEType.CLAUDE_DESKTOP)
    
    def get_vscode_variants(self) -> List[IDEInfo]:
        """Get all VS Code variants (regular and insiders)."""
        variants = []
        
        for ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS]:
            ide_info = self.detect_ide(ide_type)
            if ide_info:
                variants.append(ide_info)
        
        return variants
    
    def get_cursor_info(self) -> Optional[IDEInfo]:
        """Get Cursor IDE information specifically."""
        return self.detect_ide(IDEType.CURSOR)
    
    def get_oauth_supported_ides(self) -> List[IDEInfo]:
        """Get all IDEs that support OAuth authentication."""
        oauth_ides = []
        
        # Check Claude Code
        claude_code = self.detect_ide(IDEType.CLAUDE_CODE)
        if claude_code:
            oauth_ides.append(claude_code)
            
        # Check Gemini CLI
        gemini_cli = self.detect_ide(IDEType.GEMINI_CLI)
        if gemini_cli:
            oauth_ides.append(gemini_cli)
            
        return oauth_ides
    
    def get_claude_family_ides(self) -> List[IDEInfo]:
        """Get all Claude-family IDEs (Desktop and Code)."""
        claude_ides = []
        
        for ide_type in [IDEType.CLAUDE_DESKTOP, IDEType.CLAUDE_CODE]:
            ide_info = self.detect_ide(ide_type)
            if ide_info:
                claude_ides.append(ide_info)
                
        return claude_ides
    
    def get_mainstream_code_editors(self) -> List[IDEInfo]:
        """Get all mainstream code editors and IDEs."""
        editors = []
        
        mainstream_types = [
            IDEType.VS_CODE,
            IDEType.VS_CODE_INSIDERS,
            IDEType.CURSOR,
            IDEType.SUBLIME_TEXT,
            IDEType.JETBRAINS_PYCHARM,
            IDEType.JETBRAINS_WEBSTORM,
            IDEType.JETBRAINS_IDEA,
            IDEType.NEOVIM,
            IDEType.VIM
        ]
        
        for ide_type in mainstream_types:
            ide_info = self.detect_ide(ide_type)
            if ide_info:
                editors.append(ide_info)
                
        return editors
    
    def get_ai_enhanced_ides(self) -> List[IDEInfo]:
        """Get all AI-enhanced IDEs and tools."""
        ai_ides = []
        
        ai_types = [
            IDEType.CLAUDE_DESKTOP,
            IDEType.CLAUDE_CODE,
            IDEType.GEMINI_CLI,
            IDEType.QWEN_CODE,
            IDEType.CURSOR,
            IDEType.CODEIUM
        ]
        
        for ide_type in ai_types:
            ide_info = self.detect_ide(ide_type)
            if ide_info:
                ai_ides.append(ide_info)
                
        return ai_ides
    
    def supports_oauth(self, ide_type: IDEType) -> bool:
        """Check if an IDE type supports OAuth authentication."""
        if ide_type not in self.ide_patterns:
            return False
            
        pattern = self.ide_patterns[ide_type]
        return pattern.get('oauth_supported', False)
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of IDE detection results."""
        all_ides = self.detect_all_ides()
        
        summary = {
            'total_detected': len(all_ides),
            'oauth_supported': len(self.get_oauth_supported_ides()),
            'claude_family': len(self.get_claude_family_ides()),
            'mainstream_editors': len(self.get_mainstream_code_editors()),
            'ai_enhanced': len(self.get_ai_enhanced_ides()),
            'by_category': {
                'ai_assistants': [],
                'code_editors': [],
                'terminal_editors': [],
                'jetbrains_ides': []
            },
            'detected_ides': []
        }
        
        # Categorize detected IDEs
        for ide in all_ides:
            ide_dict = {
                'type': ide.ide_type.value,
                'name': ide.name,
                'version': ide.version,
                'path': str(ide.executable_path),
                'config_path': str(ide.config_path),
                'config_exists': ide.config_exists,
                'oauth_supported': self.supports_oauth(ide.ide_type)
            }
            
            summary['detected_ides'].append(ide_dict)
            
            # Categorize
            if ide.ide_type in [IDEType.CLAUDE_DESKTOP, IDEType.CLAUDE_CODE, IDEType.GEMINI_CLI, IDEType.QWEN_CODE]:
                summary['by_category']['ai_assistants'].append(ide_dict)
            elif ide.ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS, IDEType.CURSOR, IDEType.SUBLIME_TEXT]:
                summary['by_category']['code_editors'].append(ide_dict)
            elif ide.ide_type in [IDEType.VIM, IDEType.NEOVIM]:
                summary['by_category']['terminal_editors'].append(ide_dict)
            elif 'JETBRAINS' in ide.ide_type.value.upper():
                summary['by_category']['jetbrains_ides'].append(ide_dict)
                
        return summary
    
    def validate_config_access(self, ide_info: IDEInfo) -> Tuple[bool, str]:
        """
        Validate that we can read and write to the IDE config.
        
        Returns:
            Tuple of (can_access, message)
        """
        config_path = ide_info.config_path
        
        # Check if config directory exists
        config_dir = config_path.parent
        if not config_dir.exists():
            return False, f"Config directory does not exist: {config_dir}"
        
        # Check if we can write to the config directory
        if not config_dir.is_dir():
            return False, f"Config path is not a directory: {config_dir}"
        
        try:
            # Test write access by creating a temporary file
            test_file = config_dir / ".hive_test_access"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            return False, f"Cannot write to config directory: {e}"
        
        # If config exists, check if we can read it
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except Exception as e:
                return False, f"Cannot read existing config file: {e}"
        
        return True, "Config access validated"
    
    def get_recommended_config(self, ide_info: IDEInfo) -> Dict[str, Any]:
        """
        Get recommended Hive MCP Gateway configuration for the IDE.
        
        Args:
            ide_info: IDE information
            
        Returns:
            Dictionary with recommended MCP server configuration
        """
        if ide_info.ide_type == IDEType.CLAUDE_DESKTOP:
            return {
                "hive-mcp-gateway": {
                    "command": "/Users/YOUR_USERNAME/.local/bin/mcp-proxy",
                    "args": ["http://localhost:8001/mcp"],
                    "env": {}
                }
            }
        elif ide_info.ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS, IDEType.CURSOR]:
            return {
                "continue": {
                    "mcpServers": {
                        "hive-mcp-gateway": {
                            "command": "/Users/YOUR_USERNAME/.local/bin/mcp-proxy",
                            "args": ["http://localhost:8001/mcp"],
                            "env": {}
                        }
                    }
                }
            }
        
        return {}
    
    def get_migration_summary(self, ide_info: IDEInfo) -> Dict[str, Any]:
        """
        Get a summary of what would be migrated/changed.
        
        Args:
            ide_info: IDE information
            
        Returns:
            Dictionary with migration summary
        """
        current_servers = ide_info.mcp_servers
        recommended_config = self.get_recommended_config(ide_info)
        
        # Extract the server part
        if ide_info.ide_type == IDEType.CLAUDE_DESKTOP:
            recommended_servers = recommended_config
        else:
            recommended_servers = recommended_config.get("continue", {}).get("mcpServers", {})
        
        summary = {
            "current_server_count": len(current_servers),
            "current_servers": list(current_servers.keys()),
            "will_add": list(recommended_servers.keys()),
            "conflicts": [],
            "backup_needed": ide_info.config_exists,
            "config_exists": ide_info.config_exists
        }
        
        # Check for conflicts
        for server_name in recommended_servers:
            if server_name in current_servers:
                summary["conflicts"].append(server_name)
        
        return summary