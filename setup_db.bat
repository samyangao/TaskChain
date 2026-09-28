@echo off
setlocal
cd /d "%~dp0"
if "%DB_PASSWORD%"=="" set /p DB_PASSWORD=Enter PostgreSQL password: 
set PGPASSWORD=%DB_PASSWORD%
set /p DB_NAME=Enter database name [ias_auth_demo]: 
if "%DB_NAME%"=="" set DB_NAME=ias_auth_demo
set /p DB_USER=Enter PostgreSQL user [postgres]: 
if "%DB_USER%"=="" set DB_USER=postgres
psql -U "%DB_USER%" -d "%DB_NAME%" -f schema.sql
if errorlevel 1 (
  echo Database setup failed. Verify PostgreSQL is running and your credentials/database are correct.
  pause
  exit /b 1
)
echo TaskChain database schema applied successfully.
pause
