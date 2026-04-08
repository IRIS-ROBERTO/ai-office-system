"""
AI Office System — Settings
Todas as configurações via variáveis de ambiente.
Senior Agent: Gemini 2.0 Flash (via endpoint OpenAI-compatível)
Local Agents: Ollama (qwen2.5-coder:32b, qwen3-vl:8b, iris-fast, iris-comments, llama3.1:8b)
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):

    # === Senior Agent — Camada 1: OpenRouter (gratuito, controlado pelo ModelGate) ===
    OPENROUTER_API_KEY: str = ""

    # === Senior Agent — Camada 2: Gemini 2.0 Flash (fallback) ===
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # === Modelos Locais (Ollama) ===
    # Roteamento por especialidade — baseado nos modelos disponíveis localmente
    LOCAL_MODEL_CODE: str = "qwen2.5-coder:32b"       # Frontend, Backend, Planner
    LOCAL_MODEL_VISION: str = "qwen3-vl:8b"           # QA, Security, Analytics
    LOCAL_MODEL_DOCS: str = "iris-comments:latest"    # Docs — modelo customizado
    LOCAL_MODEL_FAST: str = "iris-fast:latest"        # Social, SEO — tarefas rápidas
    LOCAL_MODEL_GENERAL: str = "llama3.1:8b"          # Research, Content, Strategy

    # Fallbacks caso modelo não esteja disponível
    LOCAL_MODEL_FALLBACK: str = "qwen2.5:7b"
    LOCAL_MODEL_FALLBACK_SMALL: str = "llama3.2:3b"

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    LOCAL_MODEL_PATH: str = "./models/qwen2.5-3b-instruct"  # modelo quantizado local opcional

    # === Supabase ===
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379"

    # === API ===
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # === OpenRouter Management (IRIS Key Pool) ===
    OPENROUTER_MANAGEMENT_KEY: str = ""

    # === GitHub (para os agentes commitarem) ===
    GITHUB_TOKEN: str = ""
    GITHUB_USERNAME: str = "IRIS-ROBERTO"
    GITHUB_DEFAULT_ORG: Optional[str] = None

    # === Performance ===
    # MAX_CONCURRENT_AGENTS: 2 = 1 dev + 1 marketing simultâneos (Ollama single-GPU)
    # Em GPUs com >24GB VRAM, aumentar para 6 ou 12.
    MAX_CONCURRENT_AGENTS: int = 2
    SENIOR_MAX_TOKENS: int = 1024         # Conciso: planning JSON não precisa de mais
    LOCAL_MAX_TOKENS: int = 2048          # Reduzido para acelerar inferência local
    ANIMATION_QUEUE_BUFFER_MS: int = 500

    # === Qualidade ===
    MAX_RETRIES_PER_SUBTASK: int = 3
    QUALITY_GATE_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
