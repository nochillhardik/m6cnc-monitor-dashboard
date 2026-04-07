@echo off
echo =========================================================================
echo  CNC Monitor Dashboard - STARTUP
echo =========================================================================
echo.

rem Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

rem Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found. Run INSTALL.bat first.
    pause
    exit /b 1
)

echo.
echo Starting Streamlit Dashboard...
start "CNC Monitor Dashboard" cmd /k "python -m streamlit run dashboard.py"

timeout /t 2 >nul

echo Starting Data Collector...
start "CNC Monitor - Data Collector" cmd /k "python run_monitor.py --loop"

echo.
echo =========================================================================
echo  SERVICES STARTED
echo =========================================================================
echo.
echo Dashboard: http://localhost:8501
echo Logs: logs\cnc_monitor.log
echo.
echo To stop: close both windows or press Ctrl+C in each.
echo.
pause