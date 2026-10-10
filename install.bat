@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title LeadPlus360 Installer

REM Always begin from a clean local database. Demo/test data is intentionally disabled.
if exist "db.sqlite3" del /f /q "db.sqlite3"
if exist "db.sqlite3-journal" del /f /q "db.sqlite3-journal"
if exist "db.sqlite3-shm" del /f /q "db.sqlite3-shm"
if exist "db.sqlite3-wal" del /f /q "db.sqlite3-wal"

set "ADMIN_USERNAME="
set "ADMIN_PASSWORD="
set "ADMIN_EMAIL="

echo ============================================================
echo          LEADPLUS360 - INSTALL AND START
 echo ============================================================
echo Project: %CD%
echo.
echo This installer creates a clean database and a fresh super admin account.
echo Demo data seeding is disabled.
echo.

set /p ADMIN_USERNAME=Super admin username [admin]: 
if "%ADMIN_USERNAME%"=="" set "ADMIN_USERNAME=admin"

set /p ADMIN_EMAIL=Super admin email [admin@leadplus360.local]: 
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@leadplus360.local"

set /p ADMIN_PASSWORD=Super admin password [leave blank for Admin@12345]: 
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Admin@12345"

echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python is not installed or not available in PATH.
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo [1/7] Creating virtual environment...
  python -m venv venv
  if errorlevel 1 goto :fail
) else echo [1/7] Virtual environment already exists.

call "venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

if not exist "requirements.txt" (
  echo ERROR: requirements.txt not found.
  goto :fail
)

echo [2/7] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 goto :fail

echo [2.5/7] Verifying required Python packages...
python -c "import django, openpyxl, PIL, numpy, cv2; print('All required packages are available.')"
if errorlevel 1 (
  echo ERROR: One or more required Python packages could not be imported.
  goto :fail
)

echo [3/7] Checking Django project...
python manage.py check
if errorlevel 1 goto :fail

echo [4/7] Applying database migrations...
python manage.py migrate --noinput
if errorlevel 1 goto :fail

echo [5/7] Creating standard organization roles...
python manage.py ensure_org_roles
if errorlevel 1 goto :fail

echo [6/7] Creating/updating administrator account...
python manage.py bootstrap_admin --username "%ADMIN_USERNAME%" --password "%ADMIN_PASSWORD%" --email "%ADMIN_EMAIL%"
if errorlevel 1 goto :fail

echo [7/7] Starting LeadPlus360...
echo.
echo ============================================================
echo Login: http://127.0.0.1:8000/login/
echo Username: %ADMIN_USERNAME%
echo Password: %ADMIN_PASSWORD%
echo ============================================================
echo.
python manage.py runserver 127.0.0.1:8000
exit /b %errorlevel%

:fail
echo.
echo ============================================================
echo INSTALLATION FAILED
 echo ============================================================
echo Review the error above, then run install.bat again.
pause
exit /b 1
