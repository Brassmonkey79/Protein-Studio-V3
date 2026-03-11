@echo off
echo ============================================================
echo   Protein Design Studio V3 - Server Launcher
echo ============================================================
echo.
echo Installing dependencies...
pip install flask paramiko scp >nul 2>&1
echo Starting server...
echo.
python "%~dp0server.py"
pause
