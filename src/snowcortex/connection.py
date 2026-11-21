"""Snowflake connectivity helpers.

Heavy dependencies (snowflake-connector, snowflake.core) are imported lazily so the
pure-Python parts of this package stay importable and unit-testable without them.

Authentication, in order of precedence:
  1. SNOWFLAKE_CONNECTION_NAME  -> a named entry in ~/.snowflake/connections.toml
  2. SNOWFLAKE_PRIVATE_KEY_PATH -> key-pair auth (recommended for services)
  3. SNOWFLAKE_PASSWORD         -> username/password (+ MFA if your account enforces it)
"""

from __future__ import annotations

from typing import Any

from .config import Settings, get_settings


def get_connection(settings: Settings | None = None):
    """Open a snowflake.connector connection."""
    import snowflake.connector

    s = settings or get_settings()
    common: dict[str, Any] = {
        "role": s.role,
        "warehouse": s.warehouse,
        "database": s.database,
        "schema": s.schema,
    }

    if s.connection_name:
        return snowflake.connector.connect(connection_name=s.connection_name, **common)

    if not (s.account and s.user):
        raise RuntimeError(
            "Set SNOWFLAKE_CONNECTION_NAME, or SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER "
            "(see .env.example)."
        )

    params: dict[str, Any] = {"account": s.account, "user": s.user, **common}

    if s.private_key_path:
        params["private_key_file"] = s.private_key_path
    elif s.password:
        params["password"] = s.password
    else:
        raise RuntimeError("Set SNOWFLAKE_PRIVATE_KEY_PATH or SNOWFLAKE_PASSWORD.")

    return snowflake.connector.connect(**params)


def get_root(conn):
    """snowflake.core Root handle (used for the Cortex Search Python API)."""
    from snowflake.core import Root

    return Root(conn)


def rest_base_url(conn) -> str:
    """Base URL for Snowflake REST APIs, e.g. https://<account>.snowflakecomputing.com."""
    return f"https://{conn.host}"


def auth_headers(conn, settings: Settings | None = None) -> dict[str, str]:
    """Headers for Cortex REST APIs (Analyst, Agents).

    Uses a programmatic access token (PAT) when SNOWFLAKE_PAT is set, otherwise the
    live session token of the connector connection.
    """
    s = settings or get_settings()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if s.pat:
        headers["Authorization"] = f"Bearer {s.pat}"
        headers["X-Snowflake-Authorization-Token-Type"] = "PROGRAMMATIC_ACCESS_TOKEN"
    else:
        headers["Authorization"] = f'Snowflake Token="{conn.rest.token}"'
    return headers


def run_query(conn, sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    """Execute SQL and return rows as dictionaries."""
    from snowflake.connector import DictCursor

    with conn.cursor(DictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())
