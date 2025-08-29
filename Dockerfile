# Multi-stage Dockerfile for Hive MCP Gateway
# Supports both development and production environments

FROM python:3.12-slim-bookworm as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Essential build tools
    build-essential \
    curl \
    git \
    # Node.js and npm for MCP servers
    nodejs \
    npm \
    # Additional tools
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

# Install global Node.js packages for MCP servers
RUN npm install -g \
    @modelcontextprotocol/server-puppeteer \
    @upstash/context7-mcp \
    && npm cache clean --force

# Development stage
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

# Production stage
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

# GUI stage (for running with display)
FROM base as gui

# Install additional GUI dependencies
RUN apt-get update && apt-get install -y \
    # X11 and GUI libraries
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # Qt dependencies
    libqt6gui6 \
    libqt6widgets6 \
    libqt6core6 \
    # Audio (optional)
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY --chown=appuser:appuser . .

# Install Python dependencies including GUI
RUN uv sync --system-site-packages

# Install package in development mode
RUN uv pip install -e .

# Create directories
RUN mkdir -p /app/logs /app/config && \
    chown -R appuser:appuser /app/logs /app/config

# Switch to app user
USER appuser

# Set display environment
ENV DISPLAY=:0

# GUI command
CMD ["python", "gui/main_app.py"]