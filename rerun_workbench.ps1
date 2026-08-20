# One-click launcher for Validation Workbench (Streamlit)
# Starts the app on port 8502 and opens the local URL.

Write-Host "" 
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Validation Workbench Launcher" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: Virtual environment not found at .venv\\Scripts\\python.exe" -ForegroundColor Red
    Write-Host "Run setup.ps1 first, then rerun this script." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".\.env")) {
    Write-Host "ERROR: .env file not found." -ForegroundColor Red
    Write-Host "Copy .env.example to .env and fill Oracle credentials." -ForegroundColor Yellow
    exit 1
}

$pythonExe = ".\.venv\Scripts\python.exe"
$appUrl = "http://localhost:8502"

Write-Host "Starting Streamlit app..." -ForegroundColor Green
Write-Host "Local URL: $appUrl" -ForegroundColor Cyan
Write-Host "Press Ctrl+C in this window to stop the app." -ForegroundColor Yellow
Write-Host ""

Start-Process $appUrl | Out-Null
& $pythonExe -m streamlit run streamlit_app.py --server.port 8502 --server.address 0.0.0.0
