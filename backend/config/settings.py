"""
AI Office System — Settings
Todas as configurações via variáveis de ambiente.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # === Modelos ===
    # Senior Agent (caro — usado com parcimônia)
    SENIOR_MODEL: str = "anthropic/claude-sonnet-4-6"
    SENIOR_PROVIDER: str = "openrouter"

    # Local Agent (Ollama — custo zero)
    LOCAL_MODEL_CODE: str = "qwen2.5-coder:32b"
    LOCAL_MODEL_GENERAL: str = "llama3.3:70b"
    LOCAL_MODEL_REASONING: str = "deepseek-r1:32b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Fallback via OpenRouter (modelos baratos)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379"

    # === API ===
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # === Supabase ===
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # === GitHub (para os agentes commitarem) ===
    GITHUB_TOKEN: str = ""
    GITHUB_USERNAME: str = "IRIS-ROBERTO"
    GITHUB_DEFAULT_ORG: Optional[str] = None

    # === Performance ===
    MAX_CONCURRENT_AGENTS: int = 12       # 6 dev + 6 marketing
    SENIOR_MAX_TOKENS: int = 2048         # Sênior é conciso
    LOCAL_MAX_TOKENS: int = 4096
    ANIMATION_QUEUE_BUFFER_MS: int = 500  # Buffer visual para sincronização

    # === Qualidade ===
    MAX_RETRIES_PER_SUBTASK: int = 3
    QUALITY_GATE_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
