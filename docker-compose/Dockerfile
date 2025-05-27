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

# Copy the working python-script-organize code structure
COPY python-script-organize/ ./

# Copy Docker-specific service entry points
COPY docker-services/ ./docker-services/

# Copy shared utilities
COPY shared/ ./shared/

# Create shared directory for data exchange between services
RUN mkdir -p /app/shared && chmod 777 /app/shared

# Default command (will be overridden by docker-compose)
CMD ["python", "-c", "print('Hono Load Test Container - Specify service command')"]
