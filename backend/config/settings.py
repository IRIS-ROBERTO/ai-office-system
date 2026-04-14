from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENROUTER_API_KEY: str = ""

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    BRAIN_CLOUD_ENABLED: bool = True
    BRAIN_PREFER_OPENROUTER_FREE: bool = True
    BRAIN_REQUIRE_FREE_MODELS: bool = True
    OPENROUTER_MODEL_CATALOG_TTL_SECONDS: int = 600

    LOCAL_MODEL_CODE: str = "qwen2.5-coder:32b"
    LOCAL_MODEL_VISION: str = "qwen3-vl:8b"
    LOCAL_MODEL_DOCS: str = "iris-comments:latest"
    LOCAL_MODEL_FAST: str = "iris-fast:latest"
    LOCAL_MODEL_GENERAL: str = "llama3.1:8b"
    LOCAL_MODEL_FALLBACK: str = "qwen2.5:7b"
    LOCAL_MODEL_FALLBACK_SMALL: str = "llama3.2:3b"

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    LOCAL_MODEL_PATH: str = "./models/qwen2.5-3b-instruct"

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6379"
    EVENTBUS_ALLOW_FAKE_REDIS: bool = True

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    OPENROUTER_MANAGEMENT_KEY: str = ""

    GITHUB_TOKEN: str = ""
    GITHUB_USERNAME: str = "IRIS-ROBERTO"
    GITHUB_DEFAULT_ORG: Optional[str] = None

    N8N_BASE_URL: str = "http://localhost:5678"
    N8N_API_KEY: str = ""

    NOTION_TOKEN: str = ""
    NOTION_DEFAULT_PARENT_ID: str = ""

    PICOCLAW_HOST: str = "http://localhost:8765"
    PICOCLAW_ENABLED: bool = True

    MAX_CONCURRENT_AGENTS: int = 2
    SENIOR_MAX_TOKENS: int = 1024
    LOCAL_MAX_TOKENS: int = 2048
    ANIMATION_QUEUE_BUFFER_MS: int = 500

    MAX_RETRIES_PER_SUBTASK: int = 2
    QUALITY_GATE_ENABLED: bool = True
    SUBTASK_EXECUTION_TIMEOUT_SECONDS: int = 240
    EXECUTION_HEARTBEAT_SECONDS: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
