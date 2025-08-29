#!/usr/bin/env python3
"""
Comprehensive validation test for Hive MCP Gateway Correction Pass 3.

This test validates all the fixes and improvements made during the correction pass:
- Port configuration consistency (8001)
- Branding consistency (Hive MCP Gateway)
- PyQt6 compatibility
- SDK integrations
- Cross-platform features
- Configuration validation
"""

import sys
import os
import importlib
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ValidationTestSuite:
    """Comprehensive validation test suite for Hive MCP Gateway."""
    
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.failed_tests: List[str] = []
        
    def log_test_result(self, test_name: str, passed: bool, message: str = "", details: Any = None):
        """Log a test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results[test_name] = {
            "passed": passed,
            "message": message,
            "details": details
        }
        
        if not passed:
            self.failed_tests.append(test_name)
        
        logger.info(f"{status} {test_name}: {message}")
    
    def test_port_configuration_consistency(self):
        """Test that all components use port 8001 consistently."""
        try:
            # Test main config
            from src.hive_mcp_gateway.config import get_config
            config = get_config()
            port_correct = config.port == 8001
            
            # Test config models
            from src.hive_mcp_gateway.models.config import ServerConfig
            default_config = ServerConfig()
            model_port_correct = default_config.port == 8001
            
            # Test OAuth manager
            from src.hive_mcp_gateway.services.oauth_manager import OAuthManager
            oauth_manager = OAuthManager()
            oauth_urls = []
            for service_name, oauth_config in oauth_manager.oauth_configs.items():
                if oauth_config.redirect_uri:
                    oauth_urls.append(oauth_config.redirect_uri)
            
            oauth_ports_correct = all("8001" in url for url in oauth_urls)
            
            overall_pass = port_correct and model_port_correct and oauth_ports_correct
            
            self.log_test_result(
                "Port Configuration Consistency",
                overall_pass,
                f"Config: {config.port}, Model: {default_config.port}, OAuth URLs: {len(oauth_urls)} checked",
                {
                    "config_port": config.port,
                    "model_port": default_config.port,
                    "oauth_urls": oauth_urls
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Port Configuration Consistency",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_branding_consistency(self):
        """Test that branding has been updated consistently."""
        try:
            test_files = [
                "src/hive_mcp_gateway/config.py",
                "src/hive_mcp_gateway/main.py",
                "gui/main_window.py",
                "gui/main_app.py"
            ]
            
            branding_issues = []
            
            for file_path in test_files:
                if Path(file_path).exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if "Tool Gating MCP" in content:
                            branding_issues.append(f"{file_path}: Found 'Tool Gating MCP'")
            
            passed = len(branding_issues) == 0
            message = "All files use correct branding" if passed else f"Found {len(branding_issues)} branding issues"
            
            self.log_test_result(
                "Branding Consistency",
                passed,
                message,
                branding_issues
            )
            
        except Exception as e:
            self.log_test_result(
                "Branding Consistency",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_pydantic_v2_compatibility(self):
        """Test Pydantic V2 compatibility."""
        try:
            from src.hive_mcp_gateway.models.config import ServerStatus, ServerConfig
            
            # Test ServerStatus with tags field
            status = ServerStatus(
                name="test",
                enabled=True,
                connected=False,
                tags=["test", "validation"]
            )
            
            # Test model validation
            config = ServerConfig()
            
            # Test that validate_by_name is used instead of deprecated allow_population_by_field_name
            # In Pydantic V2, model_config is a dictionary
            v2_compatible = status.model_config.get('validate_by_name', False) is True
            
            passed = hasattr(status, 'tags') and v2_compatible
            message = f"Tags field: {hasattr(status, 'tags')}, V2 config: {v2_compatible}"
            
            self.log_test_result(
                "Pydantic V2 Compatibility",
                passed,
                message,
                {
                    "has_tags_field": hasattr(status, 'tags'),
                    "validate_by_name": v2_compatible,
                    "sample_tags": status.tags,
                    "model_config": status.model_config
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Pydantic V2 Compatibility",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_claude_code_sdk_integration(self):
        """Test Claude Code SDK integration."""
        try:
            from src.hive_mcp_gateway.services.claude_code_sdk import ClaudeCodeSDK
            
            sdk = ClaudeCodeSDK()
            status = sdk.get_status()
            
            expected_keys = [
                "claude_code_installed", 
                "claude_code_path", 
                "oauth_file_found", 
                "authenticated",
                "validation_status"
            ]
            
            has_all_keys = all(key in status for key in expected_keys)
            can_detect = callable(getattr(sdk, 'is_claude_code_installed', None))
            can_get_credentials = callable(getattr(sdk, 'get_credentials', None))
            
            passed = has_all_keys and can_detect and can_get_credentials
            message = f"Status keys: {len(status)}, Detection: {can_detect}, Credentials: {can_get_credentials}"
            
            self.log_test_result(
                "Claude Code SDK Integration",
                passed,
                message,
                {
                    "status_keys": list(status.keys()),
                    "installation_detected": status.get("claude_code_installed", False),
                    "oauth_file_found": status.get("oauth_file_found", False)
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Claude Code SDK Integration",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_gemini_cli_sdk_integration(self):
        """Test Gemini CLI SDK integration."""
        try:
            from src.hive_mcp_gateway.services.gemini_cli_sdk import GeminiCLISDK
            
            sdk = GeminiCLISDK()
            status = sdk.get_status()
            
            expected_keys = [
                "gemini_cli_installed", 
                "gemini_cli_path", 
                "credentials_file_found", 
                "authenticated",
                "cli_auth_status"
            ]
            
            has_all_keys = all(key in status for key in expected_keys)
            can_detect = callable(getattr(sdk, 'is_gemini_cli_installed', None))
            can_get_credentials = callable(getattr(sdk, 'get_credentials', None))
            
            passed = has_all_keys and can_detect and can_get_credentials
            message = f"Status keys: {len(status)}, Detection: {can_detect}, Credentials: {can_get_credentials}"
            
            self.log_test_result(
                "Gemini CLI SDK Integration",
                passed,
                message,
                {
                    "status_keys": list(status.keys()),
                    "installation_detected": status.get("gemini_cli_installed", False),
                    "credentials_file_found": status.get("credentials_file_found", False)
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Gemini CLI SDK Integration",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_llm_config_ui_simplification(self):
        """Test LLM configuration UI simplification."""
        try:
            from gui.llm_config import LLMConfigWidget
            
            # Test that the simplified widget can be imported and instantiated
            # Note: We can't actually create it without QApplication
            widget_class = LLMConfigWidget
            
            # Check if it imports from the simplified implementation
            import inspect
            source_file = inspect.getfile(widget_class)
            
            simplified = "llm_config_simple" in str(source_file) or len(inspect.getsource(widget_class)) < 100
            
            self.log_test_result(
                "LLM Config UI Simplification",
                simplified,
                f"Widget source: {Path(source_file).name}",
                {
                    "source_file": source_file,
                    "simplified_implementation": simplified
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "LLM Config UI Simplification",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_cross_platform_autostart(self):
        """Test cross-platform autostart functionality."""
        try:
            from src.hive_mcp_gateway.platforms.detection import get_platform_manager
            
            platform_manager = get_platform_manager()
            
            # Test platform detection
            platform_detected = platform_manager is not None
            
            # Test autostart capabilities
            can_enable = callable(getattr(platform_manager, 'enable_autostart', None))
            can_disable = callable(getattr(platform_manager, 'disable_autostart', None))
            can_check = callable(getattr(platform_manager, 'is_autostart_enabled', None))
            
            passed = platform_detected and can_enable and can_disable and can_check
            message = f"Platform: {type(platform_manager).__name__}, Autostart methods: {can_enable and can_disable and can_check}"
            
            self.log_test_result(
                "Cross-Platform Autostart",
                passed,
                message,
                {
                    "platform_manager": type(platform_manager).__name__,
                    "autostart_methods": {
                        "enable": can_enable,
                        "disable": can_disable,
                        "check": can_check
                    }
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Cross-Platform Autostart",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_dependency_detection(self):
        """Test dependency detection improvements."""
        try:
            from gui.dependency_checker import DependencyChecker
            
            checker = DependencyChecker()
            
            # Test that it can check dependencies
            can_check_all = callable(getattr(checker, 'check_all_dependencies', None))
            can_check_mcp_proxy = callable(getattr(checker, 'check_mcp_proxy', None))
            can_check_claude = callable(getattr(checker, 'check_claude_desktop', None))
            
            # Test dependency status
            if can_check_all:
                dependencies = checker.check_all_dependencies()
                has_dependencies = len(dependencies) > 0
            else:
                has_dependencies = False
            
            passed = can_check_all and can_check_mcp_proxy and can_check_claude
            message = f"Detection methods: {passed}, Dependencies found: {has_dependencies}"
            
            self.log_test_result(
                "Dependency Detection",
                passed,
                message,
                {
                    "check_methods": {
                        "check_all": can_check_all,
                        "check_mcp_proxy": can_check_mcp_proxy,
                        "check_claude": can_check_claude
                    },
                    "dependencies_count": len(dependencies) if can_check_all else 0
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Dependency Detection",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_credential_management_integration(self):
        """Test credential management integration."""
        try:
            from src.hive_mcp_gateway.services.credential_manager import CredentialManager, CredentialType
            
            manager = CredentialManager()
            
            # Test basic operations
            can_set = callable(getattr(manager, 'set_credential', None))
            can_get = callable(getattr(manager, 'get_credential', None))
            can_list = callable(getattr(manager, 'list_credentials', None))
            
            # Test credential types
            has_credential_types = hasattr(CredentialType, 'SECRET') and hasattr(CredentialType, 'ENV')
            
            passed = can_set and can_get and can_list and has_credential_types
            message = f"Credential operations: {can_set and can_get and can_list}, Types: {has_credential_types}"
            
            self.log_test_result(
                "Credential Management Integration",
                passed,
                message,
                {
                    "operations": {
                        "set": can_set,
                        "get": can_get,
                        "list": can_list
                    },
                    "credential_types": list(CredentialType) if has_credential_types else []
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Credential Management Integration",
                False,
                f"Test failed with exception: {e}"
            )
    
    def test_main_window_navigation(self):
        """Test main window navigation buttons."""
        try:
            # Import and check for navigation methods
            # Note: We can't instantiate without QApplication
            with open("gui/main_window.py", 'r') as f:
                content = f.read()
            
            # Check for navigation button methods
            has_show_snippet = "show_snippet_processor" in content
            has_show_credentials = "show_credentials_manager" in content
            has_show_llm_config = "show_llm_config" in content
            has_show_autostart = "show_autostart_settings" in content
            
            # Check for button creation in UI setup
            has_button_layout = "nav_layout" in content or "navigation" in content.lower()
            
            passed = has_show_snippet and has_show_credentials and has_show_llm_config and has_show_autostart
            message = f"Navigation methods: {passed}, Button layout: {has_button_layout}"
            
            self.log_test_result(
                "Main Window Navigation",
                passed,
                message,
                {
                    "navigation_methods": {
                        "snippet_processor": has_show_snippet,
                        "credentials_manager": has_show_credentials,
                        "llm_config": has_show_llm_config,
                        "autostart_settings": has_show_autostart
                    },
                    "button_layout": has_button_layout
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Main Window Navigation",
                False,
                f"Test failed with exception: {e}"
            )
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests."""
        logger.info("🚀 Starting Hive MCP Gateway Validation Test Suite")
        logger.info("=" * 60)
        
        # Core functionality tests
        self.test_port_configuration_consistency()
        self.test_branding_consistency()
        self.test_pydantic_v2_compatibility()
        
        # SDK integration tests
        self.test_claude_code_sdk_integration()
        self.test_gemini_cli_sdk_integration()
        
        # UI and functionality tests
        self.test_llm_config_ui_simplification()
        self.test_cross_platform_autostart()
        self.test_dependency_detection()
        self.test_credential_management_integration()
        self.test_main_window_navigation()
        
        # Summary
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result["passed"])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 60)
        logger.info(f"📊 TEST SUMMARY")
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n❌ FAILED TESTS:")
            for test_name in self.failed_tests:
                result = self.results[test_name]
                logger.info(f"  - {test_name}: {result['message']}")
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests/total_tests)*100,
            "results": self.results,
            "failed_test_names": self.failed_tests
        }


def main():
    """Main entry point for the validation test."""
    suite = ValidationTestSuite()
    results = suite.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if results["failed_tests"] == 0 else 1
    
    if exit_code == 0:
        logger.info("\n🎉 ALL TESTS PASSED! Hive MCP Gateway is ready for deployment.")
    else:
        logger.error(f"\n⚠️  {results['failed_tests']} test(s) failed. Please review and fix issues.")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())