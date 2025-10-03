# Multi-stage build for data generator service
# Stage 1: Builder - Install dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime - Final minimal image
FROM python:3.12-slim

WORKDIR /app

# Copy only runtime dependencies from builder
COPY --from=builder /root/.local /root/.local

# Create non-root user for security
RUN groupadd --system --gid 1001 appgroup && \
    useradd --system --uid 1001 --gid appgroup --create-home appuser

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/

# Set PATH for user-installed packages
ENV PATH=/root/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run data generator
CMD ["python", "src/data_generator.py"]
