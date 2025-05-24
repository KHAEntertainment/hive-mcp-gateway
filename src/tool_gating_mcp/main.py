# FastAPI application entry point
# Defines the main app instance and core routes

from fastapi import FastAPI
from pydantic import BaseModel

from .api.v1 import tools


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str


app = FastAPI(
    title="Tool Gating MCP",
    description="FastAPI application for tool gating MCP",
    version="0.1.0",
)

# Include API routers
app.include_router(tools.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Welcome to Tool Gating MCP"}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", message="Service is running")
