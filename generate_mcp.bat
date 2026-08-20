@echo off
REM Wrapper to generate mcp.json from mcp.template.json
powershell -ExecutionPolicy Bypass -File "%~dp0generate_mcp.ps1" %*
