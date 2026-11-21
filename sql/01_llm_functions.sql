-- =============================================================================
-- 01_llm_functions.sql  |  Cortex LLM functions
-- Prereq: 00_setup.sql
-- Note: Snowflake is also rolling out AI_* equivalents (AI_COMPLETE, AI_CLASSIFY,
-- AI_SENTIMENT, ...). The SNOWFLAKE.CORTEX.* functions below remain valid; check
-- the Snowflake docs for the current recommended set in your region.
-- =============================================================================

USE ROLE CORTEX_DEV_ROLE;
USE WAREHOUSE CORTEX_WH;
USE SCHEMA SNOWCORTEX.SUPPORT;

-- 1) COMPLETE: free-form generation -------------------------------------------
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'mistral-large2',
  'In two sentences, explain what a data warehouse is to a new analyst.'
) AS answer;

-- 2) SUMMARIZE -----------------------------------------------------------------
SELECT TICKET_ID, SNOWFLAKE.CORTEX.SUMMARIZE(DESCRIPTION) AS summary
FROM SUPPORT_TICKETS
LIMIT 5;

-- 3) SENTIMENT: returns a score from -1 (negative) to 1 (positive) --------------
SELECT TICKET_ID, DESCRIPTION, SNOWFLAKE.CORTEX.SENTIMENT(DESCRIPTION) AS sentiment
FROM SUPPORT_TICKETS
ORDER BY sentiment ASC;

-- 4) CLASSIFY_TEXT: zero-shot classification ------------------------------------
SELECT
  TICKET_ID,
  SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
    DESCRIPTION,
    ['billing', 'bug', 'how-to question', 'feature request', 'security']
  ):label::STRING AS predicted_category,
  CATEGORY AS labeled_category
FROM SUPPORT_TICKETS;

-- 5) EXTRACT_ANSWER: pull a specific fact out of text ----------------------------
SELECT
  TICKET_ID,
  SNOWFLAKE.CORTEX.EXTRACT_ANSWER(DESCRIPTION, 'Which product or feature is affected?')[0]:answer::STRING AS affected_area
FROM SUPPORT_TICKETS
WHERE CATEGORY = 'Bug';

-- 6) TRANSLATE ------------------------------------------------------------------
SELECT TICKET_ID, SNOWFLAKE.CORTEX.TRANSLATE(DESCRIPTION, 'en', 'es') AS description_es
FROM SUPPORT_TICKETS
LIMIT 3;

-- 7) Structured extraction with COMPLETE + TRY_PARSE_JSON -----------------------
SELECT
  TICKET_ID,
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.COMPLETE(
      'mistral-large2',
      'Extract data from this support ticket. Respond with ONLY a JSON object with keys '
      || '"urgency" (low|medium|high), "customer_emotion" (angry|neutral|happy), and '
      || '"suggested_team" (billing|engineering|security|success). Ticket: ' || DESCRIPTION
    )
  ) AS extracted
FROM SUPPORT_TICKETS;

-- 8) Materialize enrichment so you pay for inference once ------------------------
CREATE OR REPLACE TABLE SUPPORT_TICKETS_ENRICHED AS
SELECT
  t.*,
  SNOWFLAKE.CORTEX.SENTIMENT(t.DESCRIPTION)                                           AS SENTIMENT_SCORE,
  SNOWFLAKE.CORTEX.SUMMARIZE(t.DESCRIPTION)                                           AS SUMMARY,
  SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
    t.DESCRIPTION, ['billing', 'bug', 'how-to question', 'feature request', 'security']
  ):label::STRING                                                                     AS PREDICTED_CATEGORY
FROM SUPPORT_TICKETS t;

SELECT PRODUCT, ROUND(AVG(SENTIMENT_SCORE), 3) AS avg_sentiment, COUNT(*) AS tickets
FROM SUPPORT_TICKETS_ENRICHED
GROUP BY PRODUCT
ORDER BY avg_sentiment;
