FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy all project files needed for installation
COPY pyproject.toml setup.cfg MANIFEST.in README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy additional files
COPY scripts ./scripts
COPY examples ./examples

# Expose any necessary ports (if applicable)
# EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "sf_printer_server.main"]