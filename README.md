# SnowCortex

Working examples of **Snowflake Cortex** end to end: LLM functions, Cortex Search (RAG), Cortex Analyst (text-to-SQL), a Cortex Agent that combines both, and an MCP server that exposes them to any MCP client.

The demo domain is a customer-support desk: structured `SUPPORT_TICKETS` (for Analyst and LLM functions) and an unstructured `KB_ARTICLES` knowledge base (for Search).

```
sql/                        Setup + SQL-only examples (run in Snowsight, in order)
  00_setup.sql                role, warehouse, database, sample data
  01_llm_functions.sql        COMPLETE, SUMMARIZE, SENTIMENT, CLASSIFY_TEXT, EXTRACT_ANSWER, TRANSLATE
  02_cortex_search.sql        Cortex Search service over the knowledge base
  03_cortex_analyst.sql       stage for the semantic model
semantic_models/
  support_tickets.yaml        Cortex Analyst semantic model
src/snowcortex/
  config.py / connection.py   settings + auth (named connection, key-pair, password, PAT)
  llm.py                      Python wrappers for the LLM functions
  rag.py                      Cortex Search + COMPLETE retrieval-augmented answers
  analyst.py                  Cortex Analyst REST client
  agent.py                    Cortex Agent (agent:run) combining Search + Analyst
  mcp_server.py               MCP server exposing all of the above as tools
  cli.py                      `snowcortex` command-line interface
tests/test_parsing.py         offline unit tests (no Snowflake needed)
```

## Prerequisites

- A Snowflake account in a region where Cortex is available (check model availability per region; cross-region inference may need `ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGIONS'`).
- Python 3.10+

## Quick start

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[mcp]"

# 2. Configure
cp .env.example .env        # fill in your account / user / auth

# 3. Create objects (Snowsight worksheet, or `snow sql -f <file>`), in order:
#    sql/00_setup.sql  ->  sql/02_cortex_search.sql  ->  sql/03_cortex_analyst.sql

# 4. Upload the semantic model to the stage
snowcortex upload-model

# 5. Try it
snowcortex complete "Explain Cortex Search in one sentence"
snowcortex sentiment "The new release broke everything and support is slow"
snowcortex classify "I was charged twice" billing bug "feature request"
snowcortex search "sync job timeout" --category Troubleshooting
snowcortex ask "How do I enable MFA and restrict logins by IP?"
snowcortex analyst "Which product has the lowest average CSAT score?"
snowcortex agent "How many high priority tickets are open, and how do I fix DataSync timeouts?"
```

`sql/01_llm_functions.sql` is standalone SQL; run it any time after step 3.

## Use as an MCP server

```json
{
  "mcpServers": {
    "snowcortex": {
      "command": "python",
      "args": ["-m", "snowcortex.mcp_server"],
      "env": { "SNOWFLAKE_CONNECTION_NAME": "default" }
    }
  }
}
```

Tools: `cortex_complete`, `cortex_summarize`, `cortex_sentiment`, `cortex_classify`, `search_knowledge_base`, `answer_from_knowledge_base`, `ask_data_analyst`, `ask_agent`.

## Authentication

| Method | Setting |
| --- | --- |
| Named connection (`~/.snowflake/connections.toml`) | `SNOWFLAKE_CONNECTION_NAME` |
| Key-pair (recommended for services) | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH` |
| Password | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD` |
| Programmatic access token for REST calls (optional) | `SNOWFLAKE_PAT` |

Analyst and Agent calls use the connection's session token unless `SNOWFLAKE_PAT` is set.

## Tests

```bash
python -m unittest discover -s tests -v
```

These cover response parsing, SSE handling, request construction and semantic-model consistency, and need no Snowflake account.

## Notes

- Model names (`mistral-large2`, agent orchestration `auto`) vary by region and change over time. Override with `CORTEX_LLM_MODEL` / `CORTEX_AGENT_MODEL`.
- Snowflake is introducing `AI_*` equivalents of the `SNOWFLAKE.CORTEX.*` functions; check the current docs before standardizing on one set.
- Cortex features are billed in credits. The enrichment CTAS in `01_llm_functions.sql` runs inference on every row, so keep it on small tables while experimenting.
- The REST payloads in `analyst.py` and `agent.py` follow the Snowflake docs at the time of writing. If Snowflake revises the schema, `tests/test_parsing.py` is the place to adjust expectations.
