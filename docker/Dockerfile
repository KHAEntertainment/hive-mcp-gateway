# Multi-stage Dockerfile for Hive MCP Gateway
# Intended for headless/server use. For GUI, use the native app.

FROM python:3.12-slim-bookworm as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    nodejs \
    npm \
    procps \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create app user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Install global Node.js MCP servers (pin via build-args)
ARG PUPPETEER_MCP_VERSION=@modelcontextprotocol/server-puppeteer@latest
ARG CONTEXT7_MCP_VERSION=@upstash/context7-mcp@latest
RUN npm install -g "$PUPPETEER_MCP_VERSION" "$CONTEXT7_MCP_VERSION" \
    && npm cache clean --force

# -------------------------
# Development stage
# -------------------------
FROM base as development

# Copy project files
COPY --chown=appuser:appuser . .

# Install Python dependencies
RUN uv sync --system-site-packages

# Install package in development mode
RUN uv pip install -e .

# Create directories for logs and config
RUN mkdir -p /app/logs /app/config && \
    chown -R appuser:appuser /app/logs /app/config

# Switch to app user
USER appuser

# Expose ports
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default command for development
CMD ["uvicorn", "hive_mcp_gateway.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]

# -------------------------
# Production stage
# -------------------------
FROM base as production

# Copy only necessary files for production
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser hive_mcp_gateway_config.json ./

# Install Python dependencies (production only)
RUN uv sync --frozen --no-dev --system-site-packages

# Install package
RUN uv pip install .

# Create necessary directories
RUN mkdir -p /app/logs /app/config /app/data && \
    chown -R appuser:appuser /app/logs /app/config /app/data

# Switch to app user
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Production command
CMD ["hive-mcp-gateway"]

# -------------------------------------------------------------
# GUI stage (disabled/untested in Docker)
# -------------------------------------------------------------
# Note: The PyQt6 GUI via Docker/X11 is not tested and not
# recommended. Use the native macOS app bundle for GUI usage.
# If you want to experiment, you can uncomment the following
# block and adjust compose to build with target=gui.
#
# FROM base as gui
# RUN apt-get update && apt-get install -y \
#     libx11-6 \
#     libxext6 \
#     libxrender1 \
#     libxtst6 \
#     libxi6 \
#     libgl1-mesa-glx \
#     libglib2.0-0 \
#     libqt6gui6 \
#     libqt6widgets6 \
#     libqt6core6 \
#     libasound2 \
#     && rm -rf /var/lib/apt/lists/*
# COPY --chown=appuser:appuser . .
# RUN uv sync --system-site-packages
# RUN uv pip install -e .
# RUN mkdir -p /app/logs /app/config && \
#     chown -R appuser:appuser /app/logs /app/config
# USER appuser
# ENV DISPLAY=:0
# CMD ["python", "gui/main_app.py"]
