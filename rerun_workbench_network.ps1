# One-click network launcher for Validation Workbench (Streamlit)
# Starts the app on port 8502 and opens a network URL for colleague access.

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Validation Workbench Network Launcher" -ForegroundColor Cyan
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
$port = 8502

# Prefer the same IP you used earlier; fallback to first active non-loopback IPv4.
$preferredIp = "63.10.106.182"
$resolvedIp = $preferredIp

try {
    $candidateIps = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -ne "0.0.0.0" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Select-Object -ExpandProperty IPAddress

    if ($candidateIps -and ($candidateIps -notcontains $preferredIp)) {
        $resolvedIp = $candidateIps[0]
    }
} catch {
    # Keep preferred IP if adapter inspection is unavailable.
    $resolvedIp = $preferredIp
}

$networkUrl = "http://$resolvedIp`:$port"

Write-Host "Starting Streamlit app..." -ForegroundColor Green
Write-Host "Network URL: $networkUrl" -ForegroundColor Cyan
Write-Host "Press Ctrl+C in this window to stop the app." -ForegroundColor Yellow
Write-Host ""

Start-Process $networkUrl | Out-Null
& $pythonExe -m streamlit run streamlit_app.py --server.port $port --server.address 0.0.0.0
