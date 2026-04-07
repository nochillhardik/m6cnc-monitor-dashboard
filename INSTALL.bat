@echo off
echo =========================================================================
echo  CNC Monitor Dashboard - INSTALLATION
echo =========================================================================
echo.

rem Ensure Python is installed
python --version 1>NUL 2>NUL
if errorlevel 1 (
    echo [ERROR] Python is not installed. Install Python 3.8+ and rerun.
    pause
    exit /b 1
)

rem Create a virtual environment if not present
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo.
echo Activating virtual environment...
call "%~dp0venv\Scripts\activate.bat"

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo =========================================================================
echo  INSTALLATION COMPLETE
echo =========================================================================
echo.
echo Run START.bat to launch the dashboard and data collector.
echo.
pause