#!/usr/bin/env bash
# AI Office System — Setup Rápido
set -e

echo "🚀 AI Office System — Setup"
echo "================================"

# 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ .env criado a partir de .env.example"
  echo "⚠️  Preencha as variáveis em .env antes de continuar"
fi

# 2. Python venv
if [ ! -d .venv ]; then
  python3 -m venv .venv
  echo "✅ Virtual environment criado"
fi
source .venv/bin/activate
pip install -q -r requirements.txt
echo "✅ Dependências Python instaladas"

# 3. Frontend deps
cd frontend && npm install --silent && cd ..
echo "✅ Dependências Node instaladas"

# 4. Redis via Docker
if command -v docker &> /dev/null; then
  docker compose up -d redis
  echo "✅ Redis rodando via Docker"
else
  echo "⚠️  Docker não encontrado — inicie o Redis manualmente"
fi

# 5. Ollama models (se disponível)
if command -v ollama &> /dev/null; then
  echo "📦 Baixando modelos Ollama..."
  ollama pull qwen2.5-coder:32b &
  ollama pull llama3.3:70b &
  ollama pull deepseek-r1:32b &
  wait
  echo "✅ Modelos Ollama prontos"
fi

echo ""
echo "================================"
echo "✅ Setup completo!"
echo ""
echo "Para iniciar:"
echo "  Backend:  uvicorn backend.api.main:app --reload"
echo "  Frontend: cd frontend && npm run dev"
echo "  Tudo:     docker compose up"
