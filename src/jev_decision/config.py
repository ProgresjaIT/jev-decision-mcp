from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    typesafe_api_key: SecretStr = SecretStr("")
    mcp_token: SecretStr
    model: str = "jev-1.14.0"
    db_path: str = "./data/history.sqlite3"
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    allowed_hosts: str = "localhost,127.0.0.1"
    timeout_seconds: float = Field(default=20, gt=0, le=120)
    min_confidence: float = Field(default=0.8, ge=0, le=1)
    min_probability: float = Field(default=0.9, gt=0.5, le=1)
    noul_reject_threshold: float = Field(default=0.1, ge=0, lt=0.5)
    score_min_fraction: float = Field(default=0.75, ge=0, le=1)
    max_questions: int = Field(default=32, ge=1, le=256)
    max_input_bytes: int = Field(default=65536, ge=256, le=262144)
    input_usd_per_million: float = Field(default=0.042, ge=0, allow_inf_nan=False)
    output_usd_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    # Reserve the full documented default context, not a guessed tokenizer count.
    reserved_input_tokens: int = Field(default=65536, ge=65536)
    reserved_output_tokens: int = Field(default=65536, ge=65536)
    daily_budget_usd: float = Field(default=1, gt=0, allow_inf_nan=False)
    max_request_cost_usd: float = Field(default=0.01, gt=0, allow_inf_nan=False)
    max_daily_calls: int = Field(default=1000, ge=1)

    @model_validator(mode="after")
    def secure_token(self):
        if len(self.mcp_token.get_secret_value()) < 32:
            raise ValueError("MCP_TOKEN must contain at least 32 characters")
        return self

    @property
    def reservation(self):
        return (
            self.reserved_input_tokens * self.input_usd_per_million
            + self.reserved_output_tokens * self.output_usd_per_million
        ) / 1_000_000
