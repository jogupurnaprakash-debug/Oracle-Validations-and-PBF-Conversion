# Generate mcp.json from mcp.template.json using environment variables.

param(
    [string]$TemplatePath = "mcp.template.json",
    [string]$OutputPath = "mcp.json"
)

function Get-RequiredEnv {
    param([string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $Name"
    }

    return $value.Trim()
}

try {
    if (-not (Test-Path $TemplatePath)) {
        throw "Template file not found: $TemplatePath"
    }

    $oracleHost = Get-RequiredEnv "ORACLE_HOST"
    $oracleUser = Get-RequiredEnv "ORACLE_USER"
    $rbmService = Get-RequiredEnv "ORACLE_RBM_SERVICE"
    $ubsrService = Get-RequiredEnv "ORACLE_UBSR_SERVICE"
    $rbmPassword = Get-RequiredEnv "ORACLE_RBM_PASSWORD"
    $ubsrPassword = Get-RequiredEnv "ORACLE_UBSR_PASSWORD"

    $oraclePort = [Environment]::GetEnvironmentVariable("ORACLE_PORT")
    if ([string]::IsNullOrWhiteSpace($oraclePort)) {
        $oraclePort = "1521"
    } else {
        $oraclePort = $oraclePort.Trim()
    }

    $config = Get-Content -Raw -Path $TemplatePath | ConvertFrom-Json

    if (-not $config.mcpServers."oracle-rbm" -or -not $config.mcpServers."oracle-ubsr") {
        throw "Template missing expected server keys: oracle-rbm and oracle-ubsr"
    }

    $config.mcpServers."oracle-rbm".env.ORACLE_HOST = $oracleHost
    $config.mcpServers."oracle-rbm".env.ORACLE_PORT = $oraclePort
    $config.mcpServers."oracle-rbm".env.ORACLE_SERVICE = $rbmService
    $config.mcpServers."oracle-rbm".env.ORACLE_USER = $oracleUser
    $config.mcpServers."oracle-rbm".env.ORACLE_PASSWORD = $rbmPassword

    $config.mcpServers."oracle-ubsr".env.ORACLE_HOST = $oracleHost
    $config.mcpServers."oracle-ubsr".env.ORACLE_PORT = $oraclePort
    $config.mcpServers."oracle-ubsr".env.ORACLE_SERVICE = $ubsrService
    $config.mcpServers."oracle-ubsr".env.ORACLE_USER = $oracleUser
    $config.mcpServers."oracle-ubsr".env.ORACLE_PASSWORD = $ubsrPassword

    $json = $config | ConvertTo-Json -Depth 20
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $absoluteOutputPath = Join-Path (Get-Location) $OutputPath
    [System.IO.File]::WriteAllText($absoluteOutputPath, $json, $utf8NoBom)

    Write-Host "Generated $OutputPath from $TemplatePath" -ForegroundColor Green
    Write-Host "Servers configured: oracle-rbm, oracle-ubsr" -ForegroundColor Cyan
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
