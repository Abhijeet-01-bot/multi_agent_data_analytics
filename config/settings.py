from pathlib import Path

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)


class Settings(BaseSettings):
    # Application configuration
    app_name: str = (
        "Multi-Agent Data Analytics System"
    )

    app_env: str = "development"

    # LLM provider selection
    llm_provider: str = "ollama"

    # Ollama configuration
    ollama_model: str = "llama3.2:latest"

    ollama_base_url: str = (
        "http://127.0.0.1:11434"
    )

    ollama_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    ollama_num_predict: int = Field(
        default=4096,
        ge=128,
        le=32768,
    )

    ollama_context_size: int = Field(
        default=8192,
        ge=2048,
        le=131072,
    )

    # Optional Gemini configuration
    gemini_api_key: str = ""

    llm_model: str = (
        "gemini-3.5-flash-lite"
    )

    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    # Shared model settings
    llm_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )

    llm_timeout_seconds: int = Field(
        default=180,
        ge=1,
        le=600,
    )

    # Database configuration
    database_path: str = (
        "database/northwind.db"
    )

    max_sql_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )

    max_query_rows: int = Field(
        default=5000,
        ge=1,
        le=50000,
    )

    query_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
    )

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    mcp_enabled: bool = False

    mcp_fallback_to_direct: bool = True

    mcp_transport: str = "stdio"

    mcp_server_module: str = (
        "mcp_servers.analytics_server"
    )

    mcp_timeout_seconds: int = 30

    @property
    def absolute_database_path(self) -> Path:
        configured_path = Path(
            self.database_path
        )

        if configured_path.is_absolute():
            return configured_path

        return PROJECT_ROOT / configured_path

    def validate_llm_configuration(
        self,
    ) -> None:
        provider = (
            self.llm_provider.strip().lower()
        )

        supported_providers = {
            "ollama",
            "gemini",
        }

        if provider not in supported_providers:
            raise ValueError(
                "Unsupported LLM_PROVIDER. "
                "Use 'ollama' or 'gemini'."
            )

        if provider == "ollama":
            if not self.ollama_model.strip():
                raise ValueError(
                    "OLLAMA_MODEL is missing."
                )

            if not self.ollama_base_url.strip():
                raise ValueError(
                    "OLLAMA_BASE_URL is missing."
                )

        if provider == "gemini":
            if not self.gemini_api_key.strip():
                raise ValueError(
                    "GEMINI_API_KEY is missing."
                )

            if not self.llm_model.strip():
                raise ValueError(
                    "LLM_MODEL is missing."
                )


settings = Settings()