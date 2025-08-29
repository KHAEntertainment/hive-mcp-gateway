"""IDE integration validation tests for Hive MCP Gateway."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from hive_mcp_gateway.services.ide_detector import IDEDetector, IDEType, IDEInfo
from hive_mcp_gateway.services.config_injector import ConfigInjector, InjectionResult


class TestIDEDetection:
    """Test IDE detection functionality."""
    
    @pytest.fixture
    def temp_home_dir(self):
        """Create temporary home directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock macOS Library structure
            library_dir = temp_path / "Library"
            library_dir.mkdir()
            
            # Claude Desktop
            claude_dir = library_dir / "Application Support" / "Claude"
            claude_dir.mkdir(parents=True)
            claude_config = {
                "mcpServers": {
                    "existing_server": {
                        "command": "node",
                        "args": ["/path/to/server.js"]
                    }
                }
            }
            (claude_dir / "claude_desktop_config.json").write_text(json.dumps(claude_config, indent=2))
            
            # VS Code
            vscode_dir = library_dir / "Application Support" / "Code" / "User"
            vscode_dir.mkdir(parents=True)
            vscode_config = {
                "continue": {
                    "mcpServers": {
                        "vscode_server": {
                            "command": "python",
                            "args": ["-m", "server"]
                        }
                    }
                }
            }
            (vscode_dir / "settings.json").write_text(json.dumps(vscode_config, indent=2))
            
            # Cursor
            cursor_dir = library_dir / "Application Support" / "Cursor" / "User"
            cursor_dir.mkdir(parents=True)
            cursor_config = {"continue": {"mcpServers": {}}}
            (cursor_dir / "settings.json").write_text(json.dumps(cursor_config, indent=2))
            
            yield temp_path
    
    @pytest.fixture
    def ide_detector(self, temp_home_dir):
        """Create IDE detector with mocked paths."""
        detector = IDEDetector()
        
        # Mock path detection methods
        library_dir = temp_home_dir / "Library" / "Application Support"
        detector._get_claude_config_path = lambda: library_dir / "Claude" / "claude_desktop_config.json"
        detector._get_vscode_config_path = lambda: library_dir / "Code" / "User" / "settings.json"
        detector._get_cursor_config_path = lambda: library_dir / "Cursor" / "User" / "settings.json"
        
        return detector
    
    def test_claude_desktop_detection(self, ide_detector):
        """Test Claude Desktop detection and config parsing."""
        claude_info = ide_detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        
        assert claude_info is not None
        assert claude_info.ide_type == IDEType.CLAUDE_DESKTOP
        assert claude_info.is_installed == True
        assert claude_info.config_exists == True
        assert "existing_server" in claude_info.mcp_servers
        assert claude_info.mcp_servers["existing_server"]["command"] == "node"
    
    def test_vscode_detection(self, ide_detector):
        """Test VS Code detection and config parsing."""
        vscode_info = ide_detector.get_ide_info(IDEType.VS_CODE)
        
        assert vscode_info is not None
        assert vscode_info.ide_type == IDEType.VS_CODE
        assert vscode_info.config_exists == True
        assert "vscode_server" in vscode_info.mcp_servers
    
    def test_cursor_detection(self, ide_detector):
        """Test Cursor detection and config parsing."""
        cursor_info = ide_detector.get_ide_info(IDEType.CURSOR)
        
        assert cursor_info is not None
        assert cursor_info.ide_type == IDEType.CURSOR
        assert cursor_info.config_exists == True
        assert len(cursor_info.mcp_servers) == 0  # Empty MCP servers
    
    def test_all_ides_detection(self, ide_detector):
        """Test detection of all IDEs at once."""
        all_ides = ide_detector.detect_all_ides()
        
        # Should find at least Claude, VS Code, and Cursor
        ide_types = [ide.ide_type for ide in all_ides]
        assert IDEType.CLAUDE_DESKTOP in ide_types
        assert IDEType.VS_CODE in ide_types
        assert IDEType.CURSOR in ide_types
        
        # All should be marked as installed in our test setup
        assert all(ide.is_installed for ide in all_ides)
    
    def test_config_validation(self, ide_detector):
        """Test IDE configuration validation."""
        claude_info = ide_detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        
        can_access, message = ide_detector.validate_config_access(claude_info)
        assert can_access == True
        assert "accessible" in message.lower()
    
    def test_version_detection(self, ide_detector):
        """Test IDE version detection where possible."""
        # Note: Version detection would typically read app bundles or version files
        # In this test, we just verify the structure exists
        claude_info = ide_detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        
        # Version might be None in test environment, but should not crash
        assert claude_info.version is None or isinstance(claude_info.version, str)


class TestConfigurationInjection:
    """Test configuration injection functionality."""
    
    @pytest.fixture
    def temp_ide_setup(self):
        """Create temporary IDE setup with configs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Claude config
            claude_dir = temp_path / "claude"
            claude_dir.mkdir()
            claude_config = {
                "mcpServers": {
                    "existing_server": {
                        "command": "node",
                        "args": ["/path/to/existing.js"],
                        "env": {"TEST": "value"}
                    }
                }
            }
            claude_config_path = claude_dir / "claude_desktop_config.json"
            claude_config_path.write_text(json.dumps(claude_config, indent=2))
            
            # Create backup directory
            backup_dir = temp_path / "backups"
            backup_dir.mkdir()
            
            yield {
                "claude_config": claude_config_path,
                "backup_dir": backup_dir,
                "temp_path": temp_path
            }
    
    @pytest.fixture
    def config_injector(self, temp_ide_setup):
        """Create config injector with temporary backup directory."""
        return ConfigInjector(temp_ide_setup["backup_dir"])
    
    @pytest.fixture
    def mock_claude_ide(self, temp_ide_setup):
        """Create mock Claude IDE info."""
        return IDEInfo(
            name="Claude Desktop",
            ide_type=IDEType.CLAUDE_DESKTOP,
            config_path=temp_ide_setup["claude_config"],
            is_installed=True,
            config_exists=True,
            mcp_servers={
                "existing_server": {
                    "command": "node",
                    "args": ["/path/to/existing.js"],
                    "env": {"TEST": "value"}
                }
            },
            version="1.0.0",
            backup_available=False
        )
    
    def test_hive_config_injection(self, config_injector, mock_claude_ide):
        """Test injecting Hive MCP Gateway configuration."""
        # Perform injection
        operation = config_injector.inject_hive_config(mock_claude_ide)
        
        # Verify success
        assert operation.result == InjectionResult.SUCCESS
        assert operation.backup_path is not None
        assert operation.backup_path.exists()
        
        # Verify configuration was added
        with open(mock_claude_ide.config_path, 'r') as f:
            updated_config = json.load(f)
        
        assert "hive-mcp-gateway" in updated_config["mcpServers"]
        hive_config = updated_config["mcpServers"]["hive-mcp-gateway"]
        assert hive_config["command"] == "mcp-proxy"
        assert "http://localhost:8001/mcp" in hive_config["args"]
        
        # Verify existing server was preserved
        assert "existing_server" in updated_config["mcpServers"]
    
    def test_config_injection_with_conflict(self, config_injector, mock_claude_ide):
        """Test injection with existing Hive configuration."""
        # First injection
        operation1 = config_injector.inject_hive_config(mock_claude_ide)
        assert operation1.result == InjectionResult.SUCCESS
        
        # Second injection without force should fail
        operation2 = config_injector.inject_hive_config(mock_claude_ide, force=False)
        assert operation2.result == InjectionResult.CONFLICT
        
        # Second injection with force should succeed
        operation3 = config_injector.inject_hive_config(mock_claude_ide, force=True)
        assert operation3.result == InjectionResult.SUCCESS
    
    def test_config_removal(self, config_injector, mock_claude_ide):
        """Test removing Hive configuration."""
        # First inject
        inject_operation = config_injector.inject_hive_config(mock_claude_ide)
        assert inject_operation.result == InjectionResult.SUCCESS
        
        # Then remove
        remove_operation = config_injector.remove_hive_config(mock_claude_ide)
        assert remove_operation.result == InjectionResult.SUCCESS
        
        # Verify removal
        with open(mock_claude_ide.config_path, 'r') as f:
            final_config = json.load(f)
        
        assert "hive-mcp-gateway" not in final_config["mcpServers"]
        assert "existing_server" in final_config["mcpServers"]  # Should preserve others
    
    def test_backup_creation(self, config_injector, mock_claude_ide):
        """Test backup file creation during injection."""
        operation = config_injector.inject_hive_config(mock_claude_ide)
        
        assert operation.backup_path is not None
        assert operation.backup_path.exists()
        assert operation.backup_path.suffix == ".json"
        assert "claude" in operation.backup_path.name.lower()
        
        # Verify backup content matches original
        with open(operation.backup_path, 'r') as f:
            backup_config = json.load(f)
        
        assert "existing_server" in backup_config["mcpServers"]
        assert "hive-mcp-gateway" not in backup_config["mcpServers"]
    
    def test_backup_restore(self, config_injector, mock_claude_ide):
        """Test restoring from backup."""
        # Create backup and inject
        operation = config_injector.inject_hive_config(mock_claude_ide)
        backup_path = operation.backup_path
        
        # Restore from backup
        restore_success = config_injector.restore_from_backup(mock_claude_ide, backup_path)
        assert restore_success == True
        
        # Verify restoration
        with open(mock_claude_ide.config_path, 'r') as f:
            restored_config = json.load(f)
        
        assert "hive-mcp-gateway" not in restored_config["mcpServers"]
        assert "existing_server" in restored_config["mcpServers"]
    
    def test_backup_cleanup(self, config_injector, mock_claude_ide):
        """Test backup cleanup functionality."""
        # Create multiple backups
        backup_paths = []
        for i in range(5):
            operation = config_injector.inject_hive_config(mock_claude_ide, force=True)
            backup_paths.append(operation.backup_path)
        
        # Verify all backups exist
        assert all(path.exists() for path in backup_paths)
        
        # Cleanup keeping only 3
        deleted_count = config_injector.cleanup_old_backups(keep_count=3)
        assert deleted_count == 2
        
        # Verify only 3 remain
        remaining_backups = list(config_injector.backup_dir.glob("*_config_*.json"))
        assert len(remaining_backups) == 3
    
    def test_injection_summary(self, config_injector, mock_claude_ide):
        """Test injection summary generation."""
        summary = config_injector.get_injection_summary(mock_claude_ide)
        
        assert summary["ide_name"] == "Claude Desktop"
        assert summary["ide_type"] == "claude_desktop"
        assert summary["config_exists"] == True
        assert "existing_server" in summary["current_servers"]
        assert summary["conflicts"] == []  # No conflicts initially
        
        # After injection, should show conflict
        config_injector.inject_hive_config(mock_claude_ide)
        summary_after = config_injector.get_injection_summary(mock_claude_ide)
        assert "hive-mcp-gateway" in summary_after["conflicts"]
    
    def test_injection_validation(self, config_injector, mock_claude_ide):
        """Test injection validation checks."""
        can_inject, issues = config_injector.validate_injection(mock_claude_ide)
        
        assert can_inject == True
        assert len(issues) == 0
        
        # Test with non-existent IDE
        invalid_ide = IDEInfo(
            name="Invalid IDE",
            ide_type=IDEType.CLAUDE_DESKTOP,
            config_path=Path("/nonexistent/path/config.json"),
            is_installed=False,
            config_exists=False,
            mcp_servers={},
            version=None,
            backup_available=False
        )
        
        can_inject_invalid, issues_invalid = config_injector.validate_injection(invalid_ide)
        assert can_inject_invalid == False
        assert len(issues_invalid) > 0


class TestCrossIDECompatibility:
    """Test compatibility across different IDEs."""
    
    @pytest.fixture
    def multi_ide_setup(self):
        """Create setup with multiple IDE configurations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Claude Desktop config
            claude_config = {"mcpServers": {}}
            claude_path = temp_path / "claude_config.json"
            claude_path.write_text(json.dumps(claude_config))
            
            # VS Code config  
            vscode_config = {"continue": {"mcpServers": {}}}
            vscode_path = temp_path / "vscode_settings.json"
            vscode_path.write_text(json.dumps(vscode_config))
            
            # Cursor config
            cursor_config = {"continue": {"mcpServers": {}}}
            cursor_path = temp_path / "cursor_settings.json"
            cursor_path.write_text(json.dumps(cursor_config))
            
            yield {
                "claude": claude_path,
                "vscode": vscode_path,
                "cursor": cursor_path,
                "backup_dir": temp_path / "backups"
            }
    
    def test_cross_ide_injection(self, multi_ide_setup):
        """Test injecting Hive config across different IDEs."""
        config_injector = ConfigInjector(multi_ide_setup["backup_dir"])
        
        # Create IDE info objects
        ides = [
            IDEInfo("Claude Desktop", IDEType.CLAUDE_DESKTOP, multi_ide_setup["claude"], True, True, {}, None, False),
            IDEInfo("VS Code", IDEType.VS_CODE, multi_ide_setup["vscode"], True, True, {}, None, False),
            IDEInfo("Cursor", IDEType.CURSOR, multi_ide_setup["cursor"], True, True, {}, None, False)
        ]
        
        # Inject into all IDEs
        results = []
        for ide in ides:
            operation = config_injector.inject_hive_config(ide)
            results.append(operation)
        
        # Verify all succeeded
        assert all(op.result == InjectionResult.SUCCESS for op in results)
        
        # Verify each IDE has the correct configuration format
        # Claude Desktop
        with open(multi_ide_setup["claude"], 'r') as f:
            claude_config = json.load(f)
        assert "hive-mcp-gateway" in claude_config["mcpServers"]
        
        # VS Code
        with open(multi_ide_setup["vscode"], 'r') as f:
            vscode_config = json.load(f)
        assert "hive-mcp-gateway" in vscode_config["continue"]["mcpServers"]
        
        # Cursor
        with open(multi_ide_setup["cursor"], 'r') as f:
            cursor_config = json.load(f)
        assert "hive-mcp-gateway" in cursor_config["continue"]["mcpServers"]
    
    def test_ide_specific_config_formats(self, multi_ide_setup):
        """Test that each IDE gets the appropriate config format."""
        config_injector = ConfigInjector(multi_ide_setup["backup_dir"])
        
        # Test Claude Desktop (direct mcpServers)
        claude_ide = IDEInfo("Claude Desktop", IDEType.CLAUDE_DESKTOP, multi_ide_setup["claude"], True, True, {}, None, False)
        claude_op = config_injector.inject_hive_config(claude_ide)
        
        with open(multi_ide_setup["claude"], 'r') as f:
            claude_config = json.load(f)
        
        hive_config = claude_config["mcpServers"]["hive-mcp-gateway"]
        assert hive_config["command"] == "mcp-proxy"
        assert "http://localhost:8001/mcp" in hive_config["args"]
        
        # Test VS Code (nested under continue)
        vscode_ide = IDEInfo("VS Code", IDEType.VS_CODE, multi_ide_setup["vscode"], True, True, {}, None, False)
        vscode_op = config_injector.inject_hive_config(vscode_ide)
        
        with open(multi_ide_setup["vscode"], 'r') as f:
            vscode_config = json.load(f)
        
        hive_config = vscode_config["continue"]["mcpServers"]["hive-mcp-gateway"]
        assert hive_config["command"] == "mcp-proxy"


class TestIDEIntegrationEndToEnd:
    """Test complete IDE integration scenarios."""
    
    @pytest.fixture
    def full_integration_setup(self):
        """Create full integration test setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create realistic IDE structure
            app_support = temp_path / "Library" / "Application Support"
            
            # Claude with existing servers
            claude_dir = app_support / "Claude"
            claude_dir.mkdir(parents=True)
            claude_config = {
                "mcpServers": {
                    "filesystem": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
                    },
                    "git": {
                        "command": "python",
                        "args": ["-m", "mcp_git"]
                    }
                }
            }
            (claude_dir / "claude_desktop_config.json").write_text(json.dumps(claude_config, indent=2))
            
            yield {
                "app_support": app_support,
                "claude_config": claude_dir / "claude_desktop_config.json"
            }
    
    def test_complete_integration_workflow(self, full_integration_setup):
        """Test complete IDE integration workflow."""
        # 1. Detect IDEs
        detector = IDEDetector()
        detector._get_claude_config_path = lambda: full_integration_setup["claude_config"]
        
        claude_info = detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        assert claude_info.config_exists == True
        assert len(claude_info.mcp_servers) == 2  # filesystem and git
        
        # 2. Validate injection capability
        injector = ConfigInjector()
        can_inject, issues = injector.validate_injection(claude_info)
        assert can_inject == True
        assert len(issues) == 0
        
        # 3. Get injection summary
        summary = injector.get_injection_summary(claude_info)
        assert summary["current_servers"] == ["filesystem", "git"]
        assert summary["conflicts"] == []
        
        # 4. Inject Hive configuration
        operation = injector.inject_hive_config(claude_info)
        assert operation.result == InjectionResult.SUCCESS
        
        # 5. Verify injection preserved existing servers
        updated_info = detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        assert len(updated_info.mcp_servers) == 3  # original 2 + hive
        assert "hive-mcp-gateway" in updated_info.mcp_servers
        assert "filesystem" in updated_info.mcp_servers
        assert "git" in updated_info.mcp_servers
        
        # 6. Test removal
        remove_operation = injector.remove_hive_config(claude_info)
        assert remove_operation.result == InjectionResult.SUCCESS
        
        # 7. Verify clean removal
        final_info = detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        assert len(final_info.mcp_servers) == 2  # back to original
        assert "hive-mcp-gateway" not in final_info.mcp_servers
        assert "filesystem" in final_info.mcp_servers
        assert "git" in final_info.mcp_servers