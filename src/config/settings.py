"""Application configuration via environment variables."""

from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    QDRANT_HOST: str = Field(default="localhost", description="Qdrant vector DB host")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant HTTP port")
    QDRANT_COLLECTION: str = Field(
        default="adops_knowledge", description="Qdrant collection name"
    )

    POSTGRES_URL: str = Field(
        default="postgresql+psycopg2://adops:adops@localhost:5432/adops",
        description="SQLAlchemy PostgreSQL connection URL",
    )

    OPENAI_API_KEY: Optional[str] = Field(
        default=None, description="OpenAI API key (optional, for GPT fallback)"
    )
    MODEL_NAME: str = Field(
        default="llama-2-7b", description="Primary LLM model identifier"
    )
    EMBEDDING_MODEL: str = Field(
        default="all-MiniLM-L6-v2", description="Sentence-transformer embedding model"
    )

    API_KEY: str = Field(
        default="changeme", description="Bearer token for API authentication"
    )
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60, description="Max requests per minute per API key"
    )

    LOG_LEVEL: str = Field(default="INFO", description="Python logging level")

    ISSUE_CATEGORIES: list[str] = Field(
        default=[
            "fill_rate",
            "ctr",
            "underdelivery",
            "inventory",
            "revenue",
            "pacing",
        ],
        description="Supported issue categories for classification",
    )

    KEYWORD_MAP: dict[str, list[str]] = Field(
        default={
            "fill_rate": [
                "fill rate", "fill_rate", "fillrate", "not filling",
                "low fill", "fill dropped", "fill drop", "unfilled",
                "no fill", "fill rate drop", "fill decline",
            ],
            "ctr": [
                "ctr", "click-through", "click through rate", "click rate",
                "low clicks", "ctr drop", "ctr decline", "ctr falling",
                "clicks dropping", "click decline",
            ],
            "underdelivery": [
                "underdeliver", "under delivery", "under-deliver",
                "not delivering", "delivery issue", "low delivery",
                "delivery problem", "slow delivery", "delivery drop",
                "not serving", "serving issue",
            ],
            "inventory": [
                "inventory", "ad unit", "adunit", "placement", "site",
                "publisher", "supply", "inventory not serving",
                "inventory issue", "inventory problem", "no inventory",
            ],
            "revenue": [
                "revenue", "rpm", "arpm", "earnings", "income",
                "revenue drop", "revenue decline", "low revenue",
                "revenue fell", "money",
            ],
            "pacing": [
                "pacing", "pacing behind", "pacing ahead", "pace",
                "over pace", "under pace", "budget pace", "spend rate",
                "daily pacing", "pacing issue",
            ],
        },
        description="Keyword mapping for issue classification",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
