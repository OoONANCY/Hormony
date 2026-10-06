import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings use the HORMONY_ prefix; provider keys also accept their standard names."""

    model_config = SettingsConfigDict(
        env_prefix="HORMONY_",
        env_file=os.environ.get("HORMONY_ENV_FILE", ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = "sqlite:///./hormony.db"
    # LLM provider: "demo" | "anthropic" | "openrouter".
    # Empty = pick from whichever key is configured (OpenRouter, then Anthropic), else the demo engine.
    # The active provider is always reported by /health and in the first event of every analysis.
    llm: str = ""
    model: str = "claude-opus-5"  # Anthropic model
    anthropic_api_key: str = Field("", validation_alias=AliasChoices("HORMONY_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"))
    openrouter_api_key: str = Field("", validation_alias=AliasChoices("HORMONY_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"))
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    today: str = "2026-09-29"
    demo_replay: bool = False
    auth_secret: str = "change-this-secret-in-env"


    @property
    def today_date(self):
        from datetime import date
        return date.fromisoformat(self.today)


settings = Settings()
