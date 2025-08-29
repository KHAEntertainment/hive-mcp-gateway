"""API endpoints for IDE detection and configuration management."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from ..services.ide_detector import IDEDetector, IDEInfo, IDEType
from ..services.config_injector import ConfigInjector, InjectionOperation, InjectionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ide", tags=["IDE Management"])


# Pydantic models for API
class IDEInfoResponse(BaseModel):
    """IDE information response model."""
    ide_type: str
    name: str
    version: Optional[str]
    executable_path: str
    config_path: str
    is_installed: bool
    config_exists: bool
    mcp_servers: Dict[str, Any]
    backup_available: bool
    
    @classmethod
    def from_ide_info(cls, ide_info: IDEInfo) -> "IDEInfoResponse":
        """Create response from IDEInfo object."""
        return cls(
            ide_type=ide_info.ide_type.value,
            name=ide_info.name,
            version=ide_info.version,
            executable_path=str(ide_info.executable_path),
            config_path=str(ide_info.config_path),
            is_installed=ide_info.is_installed,
            config_exists=ide_info.config_exists,
            mcp_servers=ide_info.mcp_servers,
            backup_available=ide_info.backup_available
        )


class InjectionRequest(BaseModel):
    """Request model for configuration injection."""
    ide_type: str = Field(..., description="IDE type to configure")
    server_name: str = Field(default="hive-mcp-gateway", description="Server name")
    force: bool = Field(default=False, description="Force overwrite existing config")


class InjectionResponse(BaseModel):
    """Response model for configuration injection."""
    success: bool
    result: str
    message: Optional[str]
    backup_path: Optional[str]
    timestamp: str
    
    @classmethod
    def from_injection_operation(cls, operation: InjectionOperation) -> "InjectionResponse":
        """Create response from InjectionOperation."""
        return cls(
            success=operation.result == InjectionResult.SUCCESS,
            result=operation.result.value if operation.result else "unknown",
            message=operation.error_message,
            backup_path=str(operation.backup_path) if operation.backup_path else None,
            timestamp=operation.timestamp.isoformat() if operation.timestamp else ""
        )


class ValidationResponse(BaseModel):
    """Response model for validation."""
    can_proceed: bool
    issues: List[str]


class MigrationSummaryResponse(BaseModel):
    """Response model for migration summary."""
    current_server_count: int
    current_servers: List[str]
    will_add: List[str]
    conflicts: List[str]
    backup_needed: bool
    config_exists: bool


# Global instances
detector = IDEDetector()
injector = ConfigInjector()


@router.get("/detect", response_model=List[IDEInfoResponse])
async def detect_ides():
    """Detect all installed IDEs."""
    try:
        detected_ides = detector.detect_all_ides()
        return [IDEInfoResponse.from_ide_info(ide) for ide in detected_ides]
    except Exception as e:
        logger.error(f"IDE detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"IDE detection failed: {str(e)}")


@router.get("/detect/{ide_type}", response_model=Optional[IDEInfoResponse])
async def detect_specific_ide(ide_type: str):
    """Detect a specific IDE."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")
        
        ide_info = detector.detect_ide(ide_enum)
        return IDEInfoResponse.from_ide_info(ide_info) if ide_info else None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"IDE detection failed for {ide_type}: {e}")
        raise HTTPException(status_code=500, detail=f"IDE detection failed: {str(e)}")


@router.get("/claude-desktop", response_model=Optional[IDEInfoResponse])
async def get_claude_desktop_info():
    """Get Claude Desktop specific information."""
    try:
        ide_info = detector.get_claude_desktop_info()
        return IDEInfoResponse.from_ide_info(ide_info) if ide_info else None
    except Exception as e:
        logger.error(f"Claude Desktop detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Claude Desktop detection failed: {str(e)}")


@router.get("/vscode-variants", response_model=List[IDEInfoResponse])
async def get_vscode_variants():
    """Get all VS Code variants (regular and insiders)."""
    try:
        variants = detector.get_vscode_variants()
        return [IDEInfoResponse.from_ide_info(ide) for ide in variants]
    except Exception as e:
        logger.error(f"VS Code detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"VS Code detection failed: {str(e)}")


@router.get("/cursor", response_model=Optional[IDEInfoResponse])
async def get_cursor_info():
    """Get Cursor IDE information."""
    try:
        ide_info = detector.get_cursor_info()
        return IDEInfoResponse.from_ide_info(ide_info) if ide_info else None
    except Exception as e:
        logger.error(f"Cursor detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cursor detection failed: {str(e)}")


@router.post("/inject", response_model=InjectionResponse)
async def inject_hive_config(request: InjectionRequest):
    """Inject Hive MCP Gateway configuration into an IDE."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(request.ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {request.ide_type}")
        
        # Detect IDE
        ide_info = detector.detect_ide(ide_enum)
        if not ide_info:
            raise HTTPException(status_code=404, detail=f"IDE not found: {request.ide_type}")
        
        if not ide_info.is_installed:
            raise HTTPException(status_code=400, detail=f"IDE not installed: {ide_info.name}")
        
        # Perform injection
        operation = injector.inject_hive_config(
            ide_info,
            server_name=request.server_name,
            force=request.force
        )
        
        return InjectionResponse.from_injection_operation(operation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Configuration injection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration injection failed: {str(e)}")


@router.post("/remove", response_model=InjectionResponse)
async def remove_hive_config(request: InjectionRequest):
    """Remove Hive MCP Gateway configuration from an IDE."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(request.ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {request.ide_type}")
        
        # Detect IDE
        ide_info = detector.detect_ide(ide_enum)
        if not ide_info:
            raise HTTPException(status_code=404, detail=f"IDE not found: {request.ide_type}")
        
        # Perform removal
        operation = injector.remove_hive_config(
            ide_info,
            server_name=request.server_name
        )
        
        return InjectionResponse.from_injection_operation(operation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Configuration removal failed: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration removal failed: {str(e)}")


@router.get("/validate/{ide_type}", response_model=ValidationResponse)
async def validate_ide_access(ide_type: str):
    """Validate that we can access and modify an IDE's configuration."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")
        
        # Detect IDE
        ide_info = detector.detect_ide(ide_enum)
        if not ide_info:
            raise HTTPException(status_code=404, detail=f"IDE not found: {ide_type}")
        
        # Validate access
        can_access, access_msg = detector.validate_config_access(ide_info)
        can_inject, inject_issues = injector.validate_injection(ide_info)
        
        issues = []
        if not can_access:
            issues.append(access_msg)
        
        if not can_inject:
            issues.extend(inject_issues)
        
        return ValidationResponse(
            can_proceed=can_access and can_inject,
            issues=issues
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"IDE validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"IDE validation failed: {str(e)}")


@router.get("/summary/{ide_type}", response_model=MigrationSummaryResponse)
async def get_migration_summary(ide_type: str):
    """Get a summary of what would be migrated/changed."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")
        
        # Detect IDE
        ide_info = detector.detect_ide(ide_enum)
        if not ide_info:
            raise HTTPException(status_code=404, detail=f"IDE not found: {ide_type}")
        
        # Get migration summary
        summary = detector.get_migration_summary(ide_info)
        
        return MigrationSummaryResponse(**summary)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Migration summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Migration summary failed: {str(e)}")


@router.get("/injection-summary/{ide_type}")
async def get_injection_summary(ide_type: str):
    """Get a summary of what would be injected."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")
        
        # Detect IDE
        ide_info = detector.detect_ide(ide_enum)
        if not ide_info:
            raise HTTPException(status_code=404, detail=f"IDE not found: {ide_type}")
        
        # Get injection summary
        summary = injector.get_injection_summary(ide_info)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Injection summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Injection summary failed: {str(e)}")


@router.get("/backups")
async def list_backups(ide_type: Optional[str] = None):
    """List available configuration backups."""
    try:
        ide_enum = None
        if ide_type:
            try:
                ide_enum = IDEType(ide_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")
        
        backups = injector.list_backups(ide_enum)
        
        return {
            "backups": [
                {
                    "path": str(backup),
                    "name": backup.name,
                    "size": backup.stat().st_size,
                    "modified": backup.stat().st_mtime
                }
                for backup in backups
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup listing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup listing failed: {str(e)}")


@router.post("/restore-backup")
async def restore_backup(ide_type: str, backup_path: str):
    """Restore configuration from a specific backup."""
    try:
        # Parse IDE type
        try:
            ide_enum = IDEType(ide_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")
        
        # Detect IDE
        ide_info = detector.detect_ide(ide_enum)
        if not ide_info:
            raise HTTPException(status_code=404, detail=f"IDE not found: {ide_type}")
        
        # Validate backup path
        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_path}")
        
        # Restore backup
        success = injector.restore_from_backup(ide_info, backup_file)
        
        if success:
            return {"success": True, "message": f"Backup restored successfully from {backup_path}"}
        else:
            raise HTTPException(status_code=500, detail="Backup restoration failed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup restoration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup restoration failed: {str(e)}")


@router.post("/cleanup-backups")
async def cleanup_old_backups(keep_count: int = 10):
    """Clean up old backup files."""
    try:
        if keep_count < 1:
            raise HTTPException(status_code=400, detail="keep_count must be at least 1")
        
        deleted_count = injector.cleanup_old_backups(keep_count)
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} old backup files"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup cleanup failed: {str(e)}")


@router.get("/operation-history")
async def get_operation_history():
    """Get the history of injection operations."""
    try:
        operations = injector.operation_history
        
        return {
            "operations": [
                {
                    "ide_name": op.ide_info.name,
                    "ide_type": op.ide_info.ide_type.value,
                    "operation_type": op.operation_type,
                    "server_name": op.server_name,
                    "result": op.result.value if op.result else None,
                    "error_message": op.error_message,
                    "backup_path": str(op.backup_path) if op.backup_path else None,
                    "timestamp": op.timestamp.isoformat() if op.timestamp else None
                }
                for op in operations
            ]
        }
        
    except Exception as e:
        logger.error(f"Operation history retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Operation history retrieval failed: {str(e)}")


# Health check for IDE services
@router.get("/health")
async def ide_health_check():
    """Health check for IDE detection and injection services."""
    try:
        # Test detector
        detector_ok = True
        detector_message = "IDE detector working"
        
        try:
            # Quick detection test
            detector.detect_all_ides()
        except Exception as e:
            detector_ok = False
            detector_message = f"IDE detector error: {str(e)}"
        
        # Test injector
        injector_ok = True
        injector_message = "Config injector working"
        
        try:
            # Check backup directory access
            backup_dir = injector.backup_dir
            if not backup_dir.exists() or not backup_dir.is_dir():
                injector_ok = False
                injector_message = "Backup directory not accessible"
        except Exception as e:
            injector_ok = False
            injector_message = f"Config injector error: {str(e)}"
        
        overall_status = detector_ok and injector_ok
        
        return {
            "status": "healthy" if overall_status else "degraded",
            "services": {
                "ide_detector": {
                    "status": "ok" if detector_ok else "error",
                    "message": detector_message
                },
                "config_injector": {
                    "status": "ok" if injector_ok else "error",
                    "message": injector_message
                }
            }
        }
        
    except Exception as e:
        logger.error(f"IDE health check failed: {e}")
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}"
        }