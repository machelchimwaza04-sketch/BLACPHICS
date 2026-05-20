@echo off
REM PostgreSQL Docker Helper for Windows
REM Usage: postgres_docker.bat [start|stop|status|remove]

setlocal enabledelayedexpansion

set CONTAINER_NAME=blacphics-postgres
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=postgres
set POSTGRES_DB=blacphics_db
set POSTGRES_PORT=5432

if "%1"=="" goto show_menu
if "%1"=="start" goto start_postgres
if "%1"=="stop" goto stop_postgres
if "%1"=="status" goto status_postgres
if "%1"=="remove" goto remove_postgres
if "%1"=="logs" goto logs_postgres

goto show_menu

:show_menu
echo.
echo PostgreSQL Docker Helper
echo.
echo Usage: postgres_docker.bat [command]
echo.
echo Commands:
echo   start   - Start PostgreSQL container
echo   stop    - Stop PostgreSQL container
echo   status  - Check container status
echo   logs    - View container logs
echo   remove  - Remove container completely
echo.
goto end

:start_postgres
echo.
echo Checking if Docker is running...
docker ps >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop first.
    goto end
)

echo Checking if container already exists...
docker ps -a --filter "name=%CONTAINER_NAME%" --format "{{.ID}}" >nul 2>&1
if errorlevel 1 (
    echo Creating and starting container...
    docker run --name %CONTAINER_NAME% ^
      -e POSTGRES_USER=%POSTGRES_USER% ^
      -e POSTGRES_PASSWORD=%POSTGRES_PASSWORD% ^
      -e POSTGRES_DB=%POSTGRES_DB% ^
      -p %POSTGRES_PORT%:5432 ^
      -d postgres:15
    echo.
    echo Container created and starting...
    timeout /t 3 /nobreak
) else (
    echo Container exists. Starting it...
    docker start %CONTAINER_NAME%
)

echo.
echo PostgreSQL is starting. Waiting for connection...
timeout /t 2 /nobreak

set "DATABASE_URL=postgres://%POSTGRES_USER%:%POSTGRES_PASSWORD%@localhost:%POSTGRES_PORT%/%POSTGRES_DB%"
echo.
echo DATABASE_URL=%DATABASE_URL%
echo.
echo Add this to your .env file
echo.
goto end

:stop_postgres
echo Stopping PostgreSQL container...
docker stop %CONTAINER_NAME%
echo Container stopped.
goto end

:status_postgres
echo.
docker ps --filter "name=%CONTAINER_NAME%" --format "table {{.Names}}\t{{.Status}}"
echo.
goto end

:logs_postgres
echo.
echo Latest logs from %CONTAINER_NAME%:
echo.
docker logs --tail 20 %CONTAINER_NAME%
echo.
goto end

:remove_postgres
echo.
echo WARNING: This will delete the PostgreSQL container and all data.
set /p confirm="Continue? (y/N): "
if /i not "%confirm%"=="y" goto end

echo Stopping container...
docker stop %CONTAINER_NAME% 2>nul
echo Removing container...
docker rm %CONTAINER_NAME% 2>nul
echo Removed.
goto end

:end
pause
