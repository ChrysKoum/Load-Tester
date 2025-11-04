FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FIXED python-script code structure
COPY ../python-script/config ./config
COPY ../python-script/core ./core
COPY ../python-script/models ./models
COPY ../python-script/utils ./utils

# Copy Docker-specific service entry points
COPY docker-services/ ./docker-services/

# Copy shared utilities
COPY shared/ ./shared/

# Create necessary directories
RUN mkdir -p /app/shared /app/cache /app/reports /app/logs && \
    chmod -R 777 /app/shared /app/cache /app/reports /app/logs

# Default command (will be overridden by docker-compose)
CMD ["python", "-c", "print('Hono Load Test Container - Specify service command')"]
