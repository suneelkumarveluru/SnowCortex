"""Central configuration, read from environment variables (or a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional
        return
    load_dotenv()


_load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    # --- connection -----------------------------------------------------------
    connection_name: str | None = field(default_factory=lambda: _env("SNOWFLAKE_CONNECTION_NAME"))
    account: str | None = field(default_factory=lambda: _env("SNOWFLAKE_ACCOUNT"))
    user: str | None = field(default_factory=lambda: _env("SNOWFLAKE_USER"))
    password: str | None = field(default_factory=lambda: _env("SNOWFLAKE_PASSWORD"))
    private_key_path: str | None = field(default_factory=lambda: _env("SNOWFLAKE_PRIVATE_KEY_PATH"))
    pat: str | None = field(default_factory=lambda: _env("SNOWFLAKE_PAT"))
    role: str = field(default_factory=lambda: _env("SNOWFLAKE_ROLE", "CORTEX_DEV_ROLE"))
    warehouse: str = field(default_factory=lambda: _env("SNOWFLAKE_WAREHOUSE", "CORTEX_WH"))
    database: str = field(default_factory=lambda: _env("SNOWFLAKE_DATABASE", "SNOWCORTEX"))
    schema: str = field(default_factory=lambda: _env("SNOWFLAKE_SCHEMA", "SUPPORT"))

    # --- Cortex objects -------------------------------------------------------
    search_service: str = field(default_factory=lambda: _env("CORTEX_SEARCH_SERVICE", "KB_SEARCH"))
    semantic_stage: str = field(default_factory=lambda: _env("CORTEX_SEMANTIC_STAGE", "SEMANTIC_MODELS"))
    semantic_file: str = field(default_factory=lambda: _env("CORTEX_SEMANTIC_FILE", "support_tickets.yaml"))

    # --- models ---------------------------------------------------------------
    llm_model: str = field(default_factory=lambda: _env("CORTEX_LLM_MODEL", "mistral-large2"))
    agent_model: str = field(default_factory=lambda: _env("CORTEX_AGENT_MODEL", "auto"))

    @property
    def semantic_model_path(self) -> str:
        """Fully qualified stage path to the semantic model YAML."""
        return f"@{self.database}.{self.schema}.{self.semantic_stage}/{self.semantic_file}"

    @property
    def search_service_fqn(self) -> str:
        return f"{self.database}.{self.schema}.{self.search_service}"


def get_settings() -> Settings:
    return Settings()
