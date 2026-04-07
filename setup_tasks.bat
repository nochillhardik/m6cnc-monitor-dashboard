@echo off
REM CNC Monitor - Daily Backup & Auto-Delete Tasks Setup
REM Run this script as Administrator to set up scheduled tasks

echo === CNC Monitor Scheduled Tasks Setup ===
echo.

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Get Python path
set PYTHON_PATH=python

REM Task names
set BACKUP_TASK=CNCMonitor_Backup
set DELETE_TASK=CNCMonitor_AutoDelete

REM Delete existing tasks
echo Cleaning up existing tasks...
schtasks /delete /tn "%BACKUP_TASK%" /f >nul 2>&1
schtasks /delete /tn "%DELETE_TASK%" /f >nul 2>&1

REM Create backup task - daily at midnight
echo Creating backup task...
schtasks /create /tn "%BACKUP_TASK%" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%\backup_daily.py\"" /sc daily /st 00:00 /f
if %errorlevel% equ 0 (
    echo   Backup task created successfully
) else (
    echo   Failed to create backup task
)

REM Create auto-delete task - daily at 00:15
echo Creating auto-delete task...
schtasks /create /tn "%DELETE_TASK%" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%\auto_delete.py\"" /sc daily /st 00:15 /f
if %errorlevel% equ 0 (
    echo   Auto-delete task created successfully
) else (
    echo   Failed to create auto-delete task
)

echo.
echo === Task Summary ===
echo.
schtasks /query /tn "%BACKUP_TASK%" | findstr "TaskName"
schtasks /query /tn "%DELETE_TASK%" | findstr "TaskName"

echo.
echo Tasks scheduled:
echo   Backup: Daily at 00:00 IST
echo   Auto-Delete: Daily at 00:15 IST
echo.
echo Manual commands:
echo   Run backup now: schtasks /run /tn "%BACKUP_TASK%"
echo   Run delete now: schtasks /run /tn "%DELETE_TASK%"
echo   Remove tasks: python setup_tasks.py --remove
echo.
pause
