@echo off
REM PostgreSQL Backup Script for Blacphics Database
REM This script creates a daily backup of the blacphics database

set BACKUP_DIR=C:\Users\Nettz Energy\Desktop\Blacphics\backups
set DB_NAME=blacphics
set DB_USER=postgres
set DB_HOST=localhost
set DB_PORT=5432
set PGPASSWORD=Machel1704

REM Create backup directory if it doesn't exist
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Generate timestamp for backup filename
for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set datetime=%%i
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%

REM Backup filename
set BACKUP_FILE=%BACKUP_DIR%\blacphics_backup_%TIMESTAMP%.sql

echo Starting PostgreSQL backup...
echo Backup file: %BACKUP_FILE%

REM Create the backup using pg_dump
"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -f "%BACKUP_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo Backup completed successfully: %BACKUP_FILE%
    REM Clean up old backups (keep last 7 days)
    forfiles /p "%BACKUP_DIR%" /s /m *.sql /d -7 /c "cmd /c del @path"
    echo Old backups cleaned up.
) else (
    echo Backup failed with error code %ERRORLEVEL%
)

echo Backup process completed.