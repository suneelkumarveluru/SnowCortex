-- =============================================================================
-- 03_cortex_analyst.sql  |  Stage for the Cortex Analyst semantic model
-- Prereq: 00_setup.sql
-- =============================================================================

USE ROLE CORTEX_DEV_ROLE;
USE WAREHOUSE CORTEX_WH;
USE SCHEMA SNOWCORTEX.SUPPORT;

-- Stage must use server-side encryption so Cortex can read the YAML.
CREATE STAGE IF NOT EXISTS SEMANTIC_MODELS
  DIRECTORY  = (ENABLE = TRUE)
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- Upload the semantic model. Run ONE of the following from your machine:
--
--   SnowSQL / Snowflake CLI:
--     PUT file://semantic_models/support_tickets.yaml @SNOWCORTEX.SUPPORT.SEMANTIC_MODELS
--         AUTO_COMPRESS = FALSE OVERWRITE = TRUE;
--
--   Or run the helper that ships with this repo:
--     python -m snowcortex.cli upload-model
--
-- Verify:
LIST @SNOWCORTEX.SUPPORT.SEMANTIC_MODELS;

-- Once uploaded, ask questions through the REST API (see src/snowcortex/analyst.py):
--   python -m snowcortex.cli analyst "Which product has the lowest average CSAT score?"
