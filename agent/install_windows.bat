@echo off
REM GreenOps Windows Agent Installer
REM Run as Administrator

setlocal enabledelayedexpansion

echo.
echo ===================================
echo  GreenOps Agent - Windows Installer
echo ===================================
echo.

REM Check administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script must be run as Administrator.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python 3.9+ is required but not found.
    echo Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Python found.

REM Get server URL
set /p SERVER_URL="Enter GreenOps server URL [http://localhost:8000]: "
if "%SERVER_URL%"=="" set SERVER_URL=http://localhost:8000

REM Create directories
set INSTALL_DIR=C:\ProgramData\GreenOps
set AGENT_DIR=%INSTALL_DIR%\agent

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%AGENT_DIR%" mkdir "%AGENT_DIR%"

echo [INFO] Created directory: %AGENT_DIR%

REM Copy agent files
echo [INFO] Copying agent files...
copy /Y "%~dp0agent.py" "%AGENT_DIR%\agent.py"
copy /Y "%~dp0requirements.txt" "%AGENT_DIR%\requirements.txt"

REM Install Python dependencies
echo [INFO] Installing Python dependencies...
python -m pip install -r "%AGENT_DIR%\requirements.txt" --quiet

REM Create config file
echo [INFO] Creating configuration...
(
echo {
echo   "server_url": "%SERVER_URL%",
echo   "heartbeat_interval": 60,
echo   "idle_threshold": 300,
echo   "log_level": "INFO"
echo }
) > "%INSTALL_DIR%\config.json"

REM Create Windows Service using NSSM (if available) or Task Scheduler
where nssm >nul 2>&1
if %errorLevel% equ 0 (
    echo [INFO] Installing as Windows service using NSSM...
    nssm install GreenOpsAgent python "%AGENT_DIR%\agent.py"
    nssm set GreenOpsAgent AppDirectory "%AGENT_DIR%"
    nssm set GreenOpsAgent AppStdout "%INSTALL_DIR%\agent.log"
    nssm set GreenOpsAgent AppStderr "%INSTALL_DIR%\agent_error.log"
    nssm set GreenOpsAgent Start SERVICE_AUTO_START
    nssm set GreenOpsAgent Description "GreenOps Energy Monitoring Agent"
    nssm start GreenOpsAgent
    echo [SUCCESS] GreenOps Agent installed and started as Windows service!
) else (
    echo [INFO] Installing via Task Scheduler (NSSM not found)...
    
    REM Create VBS wrapper for silent execution
    (
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.Run "python %AGENT_DIR%\agent.py", 0, False
    ) > "%AGENT_DIR%\run_agent.vbs"
    
    schtasks /create /tn "GreenOps Agent" /tr "wscript.exe \"%AGENT_DIR%\run_agent.vbs\"" /sc onlogon /ru SYSTEM /f
    schtasks /run /tn "GreenOps Agent"
    
    echo [SUCCESS] GreenOps Agent installed via Task Scheduler!
)

echo.
echo ===================================
echo  Installation Complete!
echo ===================================
echo  Server: %SERVER_URL%
echo  Config: %INSTALL_DIR%\config.json
echo  Logs:   %INSTALL_DIR%\agent.log
echo ===================================
echo.
pause
