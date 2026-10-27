@echo off
REM Ejecución manual o desde el Programador de tareas.
REM Uso: scripts\ejecutar_etl.bat [--forzar] [--simulacion]
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m etl %*
exit /b %ERRORLEVEL%
