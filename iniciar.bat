@echo off
cd /d "%~dp0"

set PASTA_BACKEND=%~dp0backend
set PASTA_FRONTEND=%~dp0frontend
set PASTA_LOGS=%~dp0logs

rem dados (banco, backups, logs, sessao do Instagram) fora do OneDrive: o
rem sincronizador trava o leads.db e o SQLite responde "database is locked"
set PROSPECCAO_DIR_DADOS=%LOCALAPPDATA%\SeriaxOS

rem usa o ambiente virtual do backend (.venv) se ele existir
set PYTHON_BACKEND=py
if exist "%PASTA_BACKEND%\.venv\Scripts\python.exe" set PYTHON_BACKEND=%PASTA_BACKEND%\.venv\Scripts\python.exe

if not exist "%PASTA_LOGS%" mkdir "%PASTA_LOGS%"
if not exist "%PASTA_LOGS%\vazio.txt" type nul > "%PASTA_LOGS%\vazio.txt"

echo Verificando se o backend ja esta rodando...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri http://127.0.0.1:5000/api/metricas -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"

if %errorlevel%==0 (
    echo Backend ja estava rodando.
) else (
    echo Iniciando o backend...
    powershell -NoProfile -Command "Start-Process '%PYTHON_BACKEND%' -ArgumentList 'app.py' -WorkingDirectory '%PASTA_BACKEND%' -WindowStyle Hidden -RedirectStandardOutput '%PASTA_LOGS%\backend-saida.log' -RedirectStandardError '%PASTA_LOGS%\backend-erro.log' -RedirectStandardInput '%PASTA_LOGS%\vazio.txt'"
)

echo Verificando se a interface ja esta rodando...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri http://localhost:5173 -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"

if %errorlevel%==0 (
    echo Interface ja estava rodando.
) else (
    echo Iniciando a interface...
    powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c','npm run dev' -WorkingDirectory '%PASTA_FRONTEND%' -WindowStyle Hidden -RedirectStandardOutput '%PASTA_LOGS%\frontend-saida.log' -RedirectStandardError '%PASTA_LOGS%\frontend-erro.log' -RedirectStandardInput '%PASTA_LOGS%\vazio.txt'"
    timeout /t 4 /nobreak >nul
)

start http://localhost:5173
