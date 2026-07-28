@echo off
REM Doble click para instalar JarvisRemote sin abrir una terminal a mano.
REM (Los .ps1 no corren con doble click en Windows por default -- este .bat
REM  es el punto de entrada real de "un click".)
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-JarvisRemote.ps1"
echo.
pause
