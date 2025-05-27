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

# Copy application code
COPY registrar/ ./registrar/
COPY validator/ ./validator/
COPY loadgen/ ./loadgen/
COPY shared/ ./shared/

# Create shared directory
RUN mkdir -p /app/shared && chmod 777 /app/shared

# Default command (will be overridden by docker-compose)
CMD ["python", "-c", "print('Hono Load Test Container - Specify service command')"]
