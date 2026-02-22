# Setup script for Pub/Sub API
# PowerShell version for Windows

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Pub/Sub API Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "Error: Python 3 is not installed." -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install grpcio grpcio-tools avro-python3 certifi requests

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "Error installing dependencies" -ForegroundColor Red
    exit 1
}

# Generate stub files
Write-Host ""
Write-Host "Generating gRPC stub files..." -ForegroundColor Yellow
python scripts/generate_stubs.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Stub files generated" -ForegroundColor Green
} else {
    Write-Host "Error generating stub files" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The Pub/Sub API client is now ready to use." -ForegroundColor White
Write-Host ""
Write-Host "To run the server:" -ForegroundColor White
Write-Host "  python -m sf_printer_server.main" -ForegroundColor Yellow
Write-Host ""
