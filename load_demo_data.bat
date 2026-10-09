@echo off
REM Load demo contents for LeadPlus360
REM Usage: load_demo_data.bat [options]
REM   --fresh     Reset DB and load fresh demo data (use in dev only)
REM   --demo      Load demo data without resetting (safe for existing data)
REM   --migrations Apply migrations before seeding
cd /d "%~dp0"

call venv\Scripts\activate.bat

REM Optionally apply migrations
if /I "%1"=="--migrations" (
    echo.
    echo === Applying migrations ===
    call python manage.py migrate
)

REM Seed demo data
if /I "%1"=="--fresh" (
    echo.
    echo === Loading fresh demo data (flushes existing) ===
    call python manage.py seed_demo_data --fresh-demo
) else (
    echo.
    echo === Loading demo data ===
    call python manage.py seed_demo_data
)

echo.
echo === Done ===
deactivate
pause
