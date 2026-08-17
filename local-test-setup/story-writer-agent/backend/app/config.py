from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    llm_provider: str = "ollama"
    llm_model: str = "llama3"
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # MCP servers
    db_mcp_server_url: str = "http://localhost:8001/mcp"
    email_mcp_server_url: str = "http://localhost:8002/mcp"
    mcp_agent_key: str | None = None

    # CORS
    frontend_origin: str = "http://localhost:4200"


settings = Settings()
