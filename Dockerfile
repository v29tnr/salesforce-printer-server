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
    aiosfstream>=0.5.0 \
    sqlalchemy>=2.0.0

# Copy source code
COPY src/ ./src/
COPY scripts ./scripts
COPY examples ./examples
COPY README.md ./

# Set PYTHONPATH so Python can find the modules
ENV PYTHONPATH=/app/src

# Command to run the application directly from source
CMD ["python", "/app/src/sf_printer_server/main.py"]