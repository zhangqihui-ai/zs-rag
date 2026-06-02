# Backend Dockerfile
# Multi-stage build for development and production

# ============== Base Stage ==============
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

ARG APT_MIRROR=

# Install system dependencies（构建时可传 APT_MIRROR 使用国内 Debian 镜像）
RUN set -eux; \
    if [ -n "${APT_MIRROR}" ] && [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
      sed -i "s|http://deb.debian.org/debian-security|${APT_MIRROR}-security|g" /etc/apt/sources.list.d/debian.sources || true; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    default-jre-headless \
    libreoffice-writer-nogui \
    libreoffice-java-common \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# javaldx 需要能找到 JVM（与 OpenDataLoader / PDF 解析共用）
RUN mkdir -p /usr/lib/jvm \
    && if [ -d /usr/lib/jvm/default-java ]; then true; \
    elif [ -d /opt/java/bin ]; then ln -sfn /opt/java /usr/lib/jvm/default-java; \
    fi

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000


# ============== Development Stage ==============
FROM base AS development

# Install development dependencies
RUN pip install --no-cache-dir \
    uvicorn[standard] \
    watchfiles

# Set development environment
ENV APP_ENV=development

# Command for development with hot reload
# timeout-graceful-shutdown：避免 parse-stream 等长连接阻塞热重载，导致整站无法登录
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--timeout-graceful-shutdown", "5"]


# ============== Production Stage ==============
FROM base AS production

# Create non-root user for security
# 预建 /app/storage 并归属 appuser：挂载空命名卷时 Docker 会继承该目录属主，避免 PermissionError
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/storage && \
    chown -R appuser:appuser /app
USER appuser

# Set production environment
ENV APP_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
