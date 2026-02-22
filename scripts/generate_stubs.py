#!/usr/bin/env python3
"""
Generate gRPC stub files from the pubsub_api.proto file.

This script runs the protoc compiler to generate the Python client stubs
for the Salesforce Pub/Sub API.
"""
import subprocess
import sys
from pathlib import Path


def main():
    """Generate stub files from proto file."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    proto_file = project_root / "pubsub_api.proto"
    output_dir = project_root / "src" / "sf_printer_server" / "salesforce"
    
    # Ensure proto file exists
    if not proto_file.exists():
        print(f"Error: Proto file not found at {proto_file}")
        return 1
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run protoc to generate stub files
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={project_root}",
        str(proto_file),
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}"
    ]
    
    print(f"Generating stub files...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Stub files generated successfully!")
        print(f"  - {output_dir / 'pubsub_api_pb2.py'}")
        print(f"  - {output_dir / 'pubsub_api_pb2_grpc.py'}")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error generating stub files: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
