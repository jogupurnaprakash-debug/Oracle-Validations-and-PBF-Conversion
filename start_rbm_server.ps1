# One-click starter for the RBM MCP server

$ErrorActionPreference = "Stop"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: Virtual environment not found at .venv" -ForegroundColor Red
    exit 1
}

$rbmPassword = [Environment]::GetEnvironmentVariable("ORACLE_RBM_PASSWORD")
if ([string]::IsNullOrWhiteSpace($rbmPassword)) {
    Write-Host "ERROR: ORACLE_RBM_PASSWORD is not set in your environment." -ForegroundColor Red
    Write-Host "Set it first in this terminal, then rerun this script." -ForegroundColor Yellow
    exit 1
}

$env:ORACLE_HOST = "tpaldiipvd047scan.ebiz.verizon.com"
$env:ORACLE_PORT = "2056"
$env:ORACLE_SERVICE = "r2w1st011"
$env:ORACLE_USER = "purnajo"
$env:ORACLE_PASSWORD = $rbmPassword

Write-Host "Starting RBM MCP server..." -ForegroundColor Green
& ".\.venv\Scripts\python.exe" ".\server.py"
