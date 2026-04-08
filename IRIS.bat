@echo off
chcp 65001 >nul 2>&1
title IRIS — AI Office System

:: ============================================================
::  IRIS.bat  —  Lançador da Plataforma AI Office System
::  Equipe Dev + Marketing com agentes locais e LLMs livres
:: ============================================================

setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv\Scripts"
set "FRONTEND=%ROOT%frontend"
set "BACKEND_MODULE=backend.api.main:app"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"

echo.
echo  ========================================================
echo   IRIS — AI Office System  ^|  Iniciando...
echo  ========================================================
echo.

:: ---------- 1. Verificar .env ----------
if not exist "%ROOT%.env" (
    echo  [ERRO] Arquivo .env nao encontrado em %ROOT%
    echo         Copie .env.example para .env e configure as chaves.
    pause
    exit /b 1
)
echo  [OK] .env encontrado

:: ---------- 2. Verificar venv Python ----------
if not exist "%VENV%\python.exe" (
    echo  [ERRO] Virtualenv nao encontrado em %VENV%
    echo         Execute: python -m venv .venv  ^&^&  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo  [OK] Virtualenv Python detectado

:: ---------- 3. Verificar Node/npm ----------
where node >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Node.js nao encontrado no PATH
    echo         Instale em: https://nodejs.org
    pause
    exit /b 1
)
echo  [OK] Node.js detectado

:: ---------- 4. Instalar deps frontend se necessario ----------
if not exist "%FRONTEND%\node_modules\react" (
    echo  [SETUP] Instalando dependencias do frontend...
    cd /d "%FRONTEND%"
    call npm install --silent
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar deps do frontend
        pause
        exit /b 1
    )
    cd /d "%ROOT%"
)
echo  [OK] Dependencias frontend prontas

:: ---------- 5. Iniciar Redis ----------
echo.
echo  [REDIS] Tentando iniciar Redis...

:: Tenta Docker primeiro
docker info >nul 2>&1
if not errorlevel 1 (
    echo  [REDIS] Usando Docker...
    docker start iris-redis >nul 2>&1
    if errorlevel 1 (
        docker run -d --name iris-redis -p 6379:6379 --restart unless-stopped redis:7-alpine >nul 2>&1
        if errorlevel 1 (
            echo  [AVISO] Falha ao iniciar Redis via Docker
            goto TryWSL
        )
    )
    echo  [OK] Redis rodando via Docker ^(iris-redis^)
    goto RedisOK
)

:TryWSL
:: Tenta WSL como fallback
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

:: Tenta Redis Windows nativo (Memurai ou redis-server.exe no PATH)
where redis-server >nul 2>&1
if not errorlevel 1 (
    echo  [REDIS] Usando redis-server nativo do PATH...
    start /B "IRIS-Redis" redis-server --port 6379 --loglevel warning
    timeout /t 2 /nobreak >nul
    echo  [OK] Redis iniciado
    goto RedisOK
)

echo  [AVISO] Redis nao detectado. O sistema rodara sem cache/eventos em tempo real.
echo          Para instalar: https://github.com/microsoftarchive/redis/releases
echo          Ou habilite Docker Desktop e tente novamente.
echo.
echo          Pressione ENTER para continuar so com backend+frontend, ou CTRL+C para cancelar.
pause >nul

:RedisOK

:: ---------- 6. Iniciar Backend FastAPI ----------
echo.
echo  [BACKEND] Iniciando FastAPI na porta %BACKEND_PORT%...
start "IRIS-Backend" /min cmd /c ""%VENV%\python.exe" -m uvicorn %BACKEND_MODULE% --host 0.0.0.0 --port %BACKEND_PORT% --reload --log-level info && pause"
timeout /t 3 /nobreak >nul
echo  [OK] Backend iniciado

:: ---------- 7. Iniciar Frontend Vite ----------
echo  [FRONTEND] Iniciando Vite na porta %FRONTEND_PORT%...
cd /d "%FRONTEND%"
start "IRIS-Frontend" /min cmd /c "npm run dev && pause"
cd /d "%ROOT%"
timeout /t 4 /nobreak >nul
echo  [OK] Frontend iniciado

:: ---------- 8. Abrir no navegador ----------
echo.
echo  [IRIS] Abrindo interface...
timeout /t 2 /nobreak >nul
start "" "http://localhost:%FRONTEND_PORT%"

:: ---------- 9. Painel de status ----------
echo.
echo  ========================================================
echo   IRIS esta rodando!
echo.
echo   Interface:  http://localhost:%FRONTEND_PORT%
echo   API Docs:   http://localhost:%BACKEND_PORT%/docs
echo   WebSocket:  ws://localhost:%BACKEND_PORT%/ws
echo.
echo   Logs:
echo     Backend  →  janela "IRIS-Backend"
echo     Frontend →  janela "IRIS-Frontend"
echo.
echo   Pressione qualquer tecla para ENCERRAR tudo.
echo  ========================================================
echo.
pause >nul

:: ---------- 10. Encerrar todos os processos ----------
echo  [IRIS] Encerrando servicos...
taskkill /F /FI "WindowTitle eq IRIS-Backend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq IRIS-Frontend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq IRIS-Redis*" >nul 2>&1
echo  [OK] Servicos encerrados. Ate logo!
timeout /t 2 /nobreak >nul
exit /b 0
