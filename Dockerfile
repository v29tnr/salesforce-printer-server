FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY pyproject.toml .
COPY setup.cfg .
RUN pip install --no-cache-dir .

# Copy the source code into the container
COPY src/sf_printer_server /app/src/sf_printer_server

# Copy scripts and examples
COPY scripts /app/scripts
COPY examples /app/examples

# Expose any necessary ports (if applicable)
# EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "sf_printer_server.main"]