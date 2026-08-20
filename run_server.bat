@echo off
REM Oracle MCP Server Startup Script for Windows
REM This script activates the virtual environment and starts the MCP server

echo.
echo ======================================
echo Oracle MCP Server Startup
echo ======================================
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo.
    echo Please follow these steps:
    echo 1. Copy .env.example to .env
    echo 2. Edit .env with your Oracle credentials
    echo 3. Run this script again
    echo.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please run setup.bat first to create the virtual environment.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Run the server
echo.
echo Starting Oracle MCP Server...
echo Press Ctrl+C to stop the server
echo.
python oracle_mcp_server.py

pause
