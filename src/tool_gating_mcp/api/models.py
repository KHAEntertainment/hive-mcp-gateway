# API request/response models
# Pydantic models for API endpoint data validation

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolDiscoveryRequest(BaseModel):
    """Request model for tool discovery endpoint."""

    query: str = Field(
        ..., min_length=1, description="Natural language query for tool discovery"
    )
    context: str | None = Field(
        None, description="Additional context from conversation"
    )
    tags: list[str] | None = Field(None, description="Filter by specific tags")
    limit: int | None = Field(10, ge=1, le=50, description="Maximum tools to return")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class ToolMatchResponse(BaseModel):
    """Tool match in discovery response."""

    tool_id: str
    name: str
    description: str
    score: float = Field(..., ge=0, le=1)
    matched_tags: list[str]
    estimated_tokens: int


class ToolDiscoveryResponse(BaseModel):
    """Response model for tool discovery endpoint."""

    tools: list[ToolMatchResponse]
    query_id: str
    timestamp: datetime


class ToolProvisionRequest(BaseModel):
    """Request model for tool provisioning endpoint."""

    tool_ids: list[str] | None = Field(
        None, description="Specific tools to provision"
    )
    max_tools: int | None = Field(None, description="Maximum number of tools")
    context_tokens: int | None = Field(None, description="Available token budget")


class MCPToolDefinition(BaseModel):
    """MCP tool definition in response."""

    name: str
    description: str
    parameters: dict[str, Any]
    token_count: int


class ToolProvisionResponse(BaseModel):
    """Response model for tool provisioning endpoint."""

    tools: list[MCPToolDefinition]
    metadata: dict[str, Any]


class ToolExecutionRequest(BaseModel):
    """Request model for tool execution proxy."""

    parameters: dict[str, Any] = Field(..., description="Tool execution parameters")


class ToolExecutionResponse(BaseModel):
    """Response model for tool execution proxy."""

    result: Any
    execution_time: float | None = None
    error: str | None = None
