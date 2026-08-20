# One-click starter for the UBSR MCP server

$ErrorActionPreference = "Stop"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: Virtual environment not found at .venv" -ForegroundColor Red
    exit 1
}

$ubsrPassword = [Environment]::GetEnvironmentVariable("ORACLE_UBSR_PASSWORD")
if ([string]::IsNullOrWhiteSpace($ubsrPassword)) {
    Write-Host "ERROR: ORACLE_UBSR_PASSWORD is not set in your environment." -ForegroundColor Red
    Write-Host "Set it first in this terminal, then rerun this script." -ForegroundColor Yellow
    exit 1
}

$env:ORACLE_HOST = "tpaldiipvd047scan.ebiz.verizon.com"
$env:ORACLE_PORT = "2056"
$env:ORACLE_SERVICE = "ub2wst011"
$env:ORACLE_USER = "purnajo"
$env:ORACLE_PASSWORD = $ubsrPassword

Write-Host "Starting UBSR MCP server..." -ForegroundColor Green
& ".\.venv\Scripts\python.exe" ".\server.py"
