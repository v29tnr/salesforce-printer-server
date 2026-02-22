FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install dependencies first
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install them
COPY pyproject.toml setup.cfg ./
RUN pip install --no-cache-dir \
    requests>=2.25.1 \
    simple-salesforce>=1.12.0 \
    toml>=0.10.2 \
    aiohttp>=3.8.0 \
    grpcio>=1.50.0 \
    grpcio-tools>=1.50.0 \
    avro-python3>=1.10.0 \
    certifi>=2021.5.30 \
    sqlalchemy>=2.0.0

# Copy proto file and scripts  
COPY pubsub_api.proto ./
COPY scripts ./scripts

# Copy source code FIRST
COPY src/ ./src/
COPY examples ./examples
COPY README.md ./

# Debug: Show what we have before generation
RUN echo "=== Before stub generation ===" && \
    ls -la /app/ && \
    ls -la /app/src/sf_printer_server/salesforce/ || echo "salesforce dir doesn't exist yet"

# Generate gRPC stub files AFTER copying source (so we don't overwrite them)
RUN echo "=== Generating stubs ===" && \
    python scripts/generate_stubs.py && \
    echo "=== After stub generation ===" && \
    ls -la /app/src/sf_printer_server/salesforce/ && \
    echo "=== Checking for stub files ===" && \
    ls -la /app/src/sf_printer_server/salesforce/pubsub_api_pb2*.py && \
    echo "✓ Stub files verified!"

# Set PYTHONPATH so Python can find the modules
ENV PYTHONPATH=/app/src

# Command to run the application directly from source
CMD ["python", "/app/src/sf_printer_server/main.py"]