"""Runtime configuration, read once from environment variables (and a local .env file)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Any port on localhost / 127.0.0.1, http or https.
LOCALHOST_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def _csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    api_keys: list[str]
    cors_origins: list[str]
    rate_limit_chat: str
    rate_limit_data: str
    checkpoint_db: str
    max_history_messages: int
    agent_timeout_seconds: float
    docs_enabled: bool


def load_settings() -> Settings:
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        api_keys=_csv("API_KEYS"),
        cors_origins=_csv("CORS_ORIGINS", "https://sohamchaudhari.in"),
        rate_limit_chat=os.getenv("RATE_LIMIT_CHAT", "10/minute;200/day"),
        rate_limit_data=os.getenv("RATE_LIMIT_DATA", "60/minute"),
        checkpoint_db=os.getenv("CHECKPOINT_DB", "data/checkpoints.sqlite"),
        max_history_messages=int(os.getenv("MAX_HISTORY_MESSAGES", "30")),
        agent_timeout_seconds=float(os.getenv("AGENT_TIMEOUT_SECONDS", "90")),
        docs_enabled=os.getenv("DOCS_ENABLED", "true").lower() == "true",
    )


settings = load_settings()
