-- =============================================================================
-- 02_cortex_search.sql  |  Cortex Search service over the knowledge base
-- Prereq: 00_setup.sql
-- =============================================================================

USE ROLE CORTEX_DEV_ROLE;
USE WAREHOUSE CORTEX_WH;
USE SCHEMA SNOWCORTEX.SUPPORT;

CREATE OR REPLACE CORTEX SEARCH SERVICE KB_SEARCH
  ON BODY                              -- column that is indexed for text + vector search
  ATTRIBUTES TITLE, CATEGORY           -- columns usable for filtering and returned in results
  WAREHOUSE = CORTEX_WH
  TARGET_LAG = '1 hour'
  AS (
    SELECT ARTICLE_ID, TITLE, CATEGORY, BODY
    FROM KB_ARTICLES
  );

-- Smoke test: hybrid (keyword + semantic) search through SQL
SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'SNOWCORTEX.SUPPORT.KB_SEARCH',
    '{
       "query": "nightly sync job keeps timing out",
       "columns": ["TITLE", "CATEGORY", "BODY"],
       "limit": 3
     }'
  )
)['results'] AS results;

-- Same, with an attribute filter
SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'SNOWCORTEX.SUPPORT.KB_SEARCH',
    '{
       "query": "how do I stop suspicious logins",
       "columns": ["TITLE", "BODY"],
       "filter": {"@eq": {"CATEGORY": "Security"}},
       "limit": 2
     }'
  )
)['results'] AS results;

-- Inspect the service
SHOW CORTEX SEARCH SERVICES IN SCHEMA SNOWCORTEX.SUPPORT;
