from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden with a TRIAGE_* env var."""

    model_config = SettingsConfigDict(env_prefix="TRIAGE_", env_file=".env", extra="ignore", populate_by_name=True)

    backend: Literal["aws", "local"] = "local"
    aws_region: str = "eu-west-1"

    # --- routing policy (the tunable knobs) ---
    acceptance_threshold: float = 0.75  # classifier confidence needed to generate a draft
    min_grounding_score: float = 0.35  # best RAG cosine similarity needed to trust a draft
    rag_top_k: int = 4

    # --- Anthropic API (optional; only needed by app/classification/Anthropic.py) ---
    # Accepts both the plain ANTHROPIC_* names used in .env and the TRIAGE_-prefixed ones.
    ANTHROPIC_MODEL: str = Field(
        "claude-haiku-4-5-20251001", validation_alias=AliasChoices("ANTHROPIC_MODEL", "TRIAGE_ANTHROPIC_MODEL"))
    ANTHROPIC_API_KEY: str | None = Field(
        None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "TRIAGE_ANTHROPIC_API_KEY"))

    # --- web ---
    # Only needed when the UI is served from a different origin (e.g. `npm run dev` on :5173).
    # In Docker / on AWS the UI is served by this same app, so no CORS is involved.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- AWS resources ---
    opensearch_endpoint: str = ""
    opensearch_index: str = "kb-chunks"
    kb_bucket: str = ""
    kb_prefix: str = "kb/"
    tickets_table: str = "triage-tickets"
    tickets_decision_index: str = "decision-index"
    feedback_table: str = "triage-feedback"
    feedback_category_index: str = "category-created-index"

    # --- models (Amazon Bedrock) ---
    llm_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_dim: int = 1024

    # --- local backend ---
    local_kb_dir: str = "kb"

    metrics_namespace: str = "SupportTriage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
