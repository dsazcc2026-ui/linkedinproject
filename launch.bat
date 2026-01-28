@echo off
echo ================================================
echo   Brain - LinkedIn Profile Search Tool
echo ================================================
echo.
echo Starting web server...
echo.

:: Open browser after a short delay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Run Flask app
python app.py

pause
