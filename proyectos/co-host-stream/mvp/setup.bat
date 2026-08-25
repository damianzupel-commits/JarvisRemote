@echo off
REM ============================================================
REM  Co-host de stream - INSTALADOR (doble clic)
REM  Instala las dependencias de Python y prepara el .env
REM ============================================================
cd /d "%~dp0"

echo.
echo === Co-host de stream: instalando dependencias ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python. Instalalo desde https://www.python.org/downloads/
    echo         y marca "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias. Revisa tu conexion a internet.
    pause
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo === Se creo el archivo .env ===
    echo Abrilo con el Bloc de notas y pega tu API KEY de OpenRouter
    echo en la linea OPENROUTER_API_KEY=
    echo.
)

echo.
echo === Listo! ===
echo 1) Abri el archivo .env y pega tu API key de OpenRouter (modelo de vision).
echo 2) Despues hace doble clic en run.bat para arrancar el co-host.
echo.
pause
