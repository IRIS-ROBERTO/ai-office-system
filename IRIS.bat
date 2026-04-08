@echo off
chcp 65001 >nul 2>&1
title IRIS - AI Office System

setlocal EnableExtensions DisableDelayedExpansion

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv\Scripts"
set "FRONTEND=%ROOT%frontend"
set "FRONTEND_ENV_FILE=%FRONTEND%\.env.local"
set "COMPOSE_FILE=%ROOT%docker-compose.yml"
set "LOG_DIR=%ROOT%logs"
set "BACKEND_LOG=%LOG_DIR%\iris-backend.log"
set "FRONTEND_LOG=%LOG_DIR%\iris-frontend.log"
set "BACKEND_MODULE=backend.api.main:app"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"
set "REDIS_PORT=6379"
set "REDIS_CONTAINER_NAME=ai-office-redis"
set "API_URL=http://127.0.0.1:%BACKEND_PORT%"
set "WS_URL=ws://127.0.0.1:%BACKEND_PORT%/ws"
set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"

echo.
echo  ========================================================
echo   IRIS - AI Office System ^| Boot completo
echo  ========================================================
echo.

if not exist "%ROOT%backend" (
    echo  [ERRO] Pasta backend nao encontrada em %ROOT%
    pause
    exit /b 1
)

if not exist "%ROOT%frontend" (
    echo  [ERRO] Pasta frontend nao encontrada em %ROOT%
    pause
    exit /b 1
)

if not exist "%ROOT%.env" (
    echo  [ERRO] Arquivo .env nao encontrado em %ROOT%
    echo         Copie .env.example para .env e configure as chaves.
    pause
    exit /b 1
)
echo  [OK] .env encontrado

if not exist "%VENV%\python.exe" (
    echo  [ERRO] Virtualenv nao encontrado em %VENV%
    echo         Execute: python -m venv .venv
    echo         Depois:  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo  [OK] Virtualenv Python detectado

where node >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Node.js nao encontrado no PATH
    echo         Instale em: https://nodejs.org
    pause
    exit /b 1
)
echo  [OK] Node.js detectado

where npm >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] npm nao encontrado no PATH
    pause
    exit /b 1
)
echo  [OK] npm detectado

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%" >nul 2>&1
)
break > "%BACKEND_LOG%"
break > "%FRONTEND_LOG%"
echo  [OK] Logs serao gravados em %LOG_DIR%

echo  [CHECK] Validando dependencias Python do backend...
"%VENV%\python.exe" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo  [SETUP] Instalando dependencias Python...
    call "%VENV%\pip.exe" install -r "%ROOT%requirements.txt"
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar dependencias Python
        pause
        exit /b 1
    )
)
echo  [OK] Backend Python pronto

if not exist "%FRONTEND%\node_modules\vite" (
    echo  [SETUP] Instalando dependencias do frontend...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        popd
        echo  [ERRO] Falha ao instalar dependencias do frontend
        pause
        exit /b 1
    )
    popd
)
echo  [OK] Frontend pronto

where ollama >nul 2>&1
if errorlevel 1 (
    echo  [AVISO] Ollama nao encontrado no PATH. O sistema ainda sobe, mas usara o fallback configurado.
)
if not errorlevel 1 (
    ollama list >nul 2>&1
    if errorlevel 1 (
        echo  [AVISO] Ollama instalado, mas o daemon nao respondeu.
    ) else (
        echo  [OK] Ollama detectado
    )
)

echo.
echo  [CLEANUP] Encerrando janelas IRIS antigas...
taskkill /F /FI "WindowTitle eq IRIS-Backend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq IRIS-Frontend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq IRIS-Redis*" >nul 2>&1

echo  [PORTAS] Validando portas preferenciais %BACKEND_PORT% e %FRONTEND_PORT%...
call :ResolveBackendPort
if errorlevel 1 exit /b 1
call :ResolveFrontendPort
if errorlevel 1 exit /b 1
set "API_URL=http://127.0.0.1:%BACKEND_PORT%"
set "WS_URL=ws://127.0.0.1:%BACKEND_PORT%/ws"
set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"
echo  [OK] Backend usara %BACKEND_PORT% e frontend usara %FRONTEND_PORT%

echo  [CONFIG] Gerando %FRONTEND_ENV_FILE%...
(
    echo VITE_API_URL=%API_URL%
    echo VITE_WS_URL=%WS_URL%
) > "%FRONTEND_ENV_FILE%"
if errorlevel 1 (
    echo  [ERRO] Nao foi possivel gerar %FRONTEND_ENV_FILE%
    pause
    exit /b 1
)
echo  [OK] Frontend configurado para apontar ao backend local

echo.
echo  [REDIS] Tentando iniciar Redis...
call :IsPortListening %REDIS_PORT%
if not errorlevel 1 (
    echo  [OK] Porta %REDIS_PORT% ja esta em uso. Assumindo Redis ativo.
    goto RedisOK
)

docker info >nul 2>&1
if not errorlevel 1 (
    if exist "%COMPOSE_FILE%" (
        echo  [REDIS] Usando docker compose...
        docker compose -f "%COMPOSE_FILE%" up -d redis >nul 2>&1
        if not errorlevel 1 (
            echo  [OK] Redis iniciado via docker compose (%REDIS_CONTAINER_NAME%)
            goto RedisOK
        )
        echo  [AVISO] docker compose nao conseguiu subir o servico redis
    )

    echo  [REDIS] Tentando container Docker dedicado...
    docker start %REDIS_CONTAINER_NAME% >nul 2>&1
    if errorlevel 1 (
        docker start iris-redis >nul 2>&1
    )
    if errorlevel 1 (
        docker run -d --name %REDIS_CONTAINER_NAME% -p %REDIS_PORT%:%REDIS_PORT% --restart unless-stopped redis:7-alpine >nul 2>&1
        if errorlevel 1 (
            echo  [AVISO] Falha ao iniciar Redis via Docker
            goto TryWSL
        )
    )
    echo  [OK] Redis rodando via Docker
    goto RedisOK
)

:TryWSL
wsl --list >nul 2>&1
if not errorlevel 1 (
    echo  [REDIS] Tentando WSL...
    start /B "IRIS-Redis" wsl redis-server --daemonize no --loglevel warning 2>nul
    timeout /t 2 /nobreak >nul
    wsl redis-cli ping >nul 2>&1
    if not errorlevel 1 (
        echo  [OK] Redis rodando via WSL
        goto RedisOK
    )
)

where redis-server >nul 2>&1
if not errorlevel 1 (
    echo  [REDIS] Usando redis-server nativo do PATH...
    start /B "IRIS-Redis" redis-server --port 6379 --loglevel warning
    timeout /t 2 /nobreak >nul
    echo  [OK] Redis iniciado
    goto RedisOK
)

echo  [AVISO] Redis nao detectado. O backend sobe mesmo assim com o fallback configurado.
echo          Para tempo real completo, use Docker Desktop, WSL ou redis-server no PATH.

:RedisOK

echo.
echo  [BACKEND] Iniciando FastAPI em %API_URL%...
start "IRIS-Backend" /min cmd /k "cd /d \"%ROOT%\" && set \"REDIS_URL=redis://127.0.0.1:%REDIS_PORT%\" && \"%VENV%\python.exe\" -m uvicorn %BACKEND_MODULE% --host 0.0.0.0 --port %BACKEND_PORT% --reload --log-level info >> \"%BACKEND_LOG%\" 2>&1"
call :WaitForHttp "%API_URL%/docs" 45
if errorlevel 1 (
    echo  [ERRO] Backend nao respondeu em %API_URL%/docs
    echo         Verifique a janela IRIS-Backend ou o log:
    echo         %BACKEND_LOG%
    pause
    exit /b 1
)
echo  [OK] Backend respondeu ao boot check
call :WaitForHttp "%API_URL%/health" 10
if errorlevel 1 (
    echo  [AVISO] API subiu, mas /health ainda nao respondeu imediatamente.
    echo          Consulte %BACKEND_LOG% se quiser diagnostico adicional.
) else (
    echo  [OK] Backend respondeu ao health check
)

echo.
echo  [FRONTEND] Iniciando Vite em %FRONTEND_URL%...
start "IRIS-Frontend" /min cmd /k "cd /d \"%FRONTEND%\" && set \"VITE_API_URL=%API_URL%\" && set \"VITE_WS_URL=%WS_URL%\" && npm run dev -- --port %FRONTEND_PORT% >> \"%FRONTEND_LOG%\" 2>&1"
call :WaitForHttp "%FRONTEND_URL%" 45
if errorlevel 1 (
    echo  [ERRO] Frontend nao respondeu em %FRONTEND_URL%
    echo         Verifique a janela IRIS-Frontend ou o log:
    echo         %FRONTEND_LOG%
    pause
    exit /b 1
)
echo  [OK] Frontend respondeu

echo.
echo  [IRIS] Abrindo interface...
call :OpenBrowser "%FRONTEND_URL%"

echo.
echo  ========================================================
echo   IRIS esta rodando
echo.
echo   Interface:  %FRONTEND_URL%
echo   API Docs:   %API_URL%/docs
echo   Health:     %API_URL%/health
echo   WebSocket:  %WS_URL%
echo.
echo   Logs:
echo     Backend  - janela "IRIS-Backend"
echo     Frontend - janela "IRIS-Frontend"
echo     Arquivos  - %LOG_DIR%
echo.
echo   Pressione qualquer tecla para ENCERRAR tudo.
echo  ========================================================
echo.
pause >nul

echo  [IRIS] Encerrando servicos...
taskkill /F /FI "WindowTitle eq IRIS-Backend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq IRIS-Frontend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq IRIS-Redis*" >nul 2>&1
echo  [OK] Servicos encerrados.
timeout /t 1 /nobreak >nul
exit /b 0

:EnsurePortFree
set "PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    exit /b 1
)
exit /b 0

:IsPortListening
set "PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    exit /b 0
)
exit /b 1

:ResolveBackendPort
call :EnsurePortFree %BACKEND_PORT%
if not errorlevel 1 exit /b 0

echo  [AVISO] A porta %BACKEND_PORT% esta ocupada. Procurando backend limpo...
for %%P in (8011 8012 8013 8014 8015) do (
    call :EnsurePortFree %%P
    if not errorlevel 1 (
        set "BACKEND_PORT=%%P"
        exit /b 0
    )
)
echo  [ERRO] Nenhuma porta livre encontrada para o backend.
pause
exit /b 1

:ResolveFrontendPort
call :EnsurePortFree %FRONTEND_PORT%
if not errorlevel 1 exit /b 0

echo  [AVISO] A porta %FRONTEND_PORT% esta ocupada. Procurando frontend limpo...
for %%P in (3001 3002 3003 3004 3005) do (
    call :EnsurePortFree %%P
    if not errorlevel 1 (
        set "FRONTEND_PORT=%%P"
        exit /b 0
    )
)
echo  [ERRO] Nenhuma porta livre encontrada para o frontend.
pause
exit /b 1

:OpenBrowser
set "TARGET_URL=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Start-Process '%TARGET_URL%'; exit 0 } catch { exit 1 }"
if not errorlevel 1 exit /b 0

start "" "%TARGET_URL%" >nul 2>&1
if not errorlevel 1 exit /b 0

explorer "%TARGET_URL%" >nul 2>&1
if not errorlevel 1 exit /b 0

echo  [AVISO] Nao foi possivel abrir o navegador automaticamente.
echo          Abra manualmente: %TARGET_URL%
exit /b 0

:WaitForHttp
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline = (Get-Date).AddSeconds(%~2);" ^
  "while ((Get-Date) -lt $deadline) {" ^
  "  try {" ^
  "    $response = Invoke-WebRequest -Uri '%~1' -UseBasicParsing -TimeoutSec 3;" ^
  "    if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 }" ^
  "  } catch { }" ^
  "  Start-Sleep -Seconds 1" ^
  "}" ^
  "exit 1"
exit /b %errorlevel%
