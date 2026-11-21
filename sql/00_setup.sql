-- =============================================================================
-- 00_setup.sql  |  SnowCortex: environment + sample data
-- Run as ACCOUNTADMIN (or a role that can create roles, warehouses, databases).
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- ---- Role, warehouse, database ---------------------------------------------
CREATE ROLE IF NOT EXISTS CORTEX_DEV_ROLE;

CREATE WAREHOUSE IF NOT EXISTS CORTEX_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND   = 60
  AUTO_RESUME    = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS SNOWCORTEX;
CREATE SCHEMA   IF NOT EXISTS SNOWCORTEX.SUPPORT;

-- ---- Privileges --------------------------------------------------------------
-- CORTEX_USER is required for the LLM functions, Cortex Search and Analyst.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE CORTEX_DEV_ROLE;

GRANT USAGE, OPERATE ON WAREHOUSE CORTEX_WH TO ROLE CORTEX_DEV_ROLE;
GRANT ALL ON DATABASE SNOWCORTEX TO ROLE CORTEX_DEV_ROLE;
GRANT ALL ON ALL SCHEMAS IN DATABASE SNOWCORTEX TO ROLE CORTEX_DEV_ROLE;
GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA SNOWCORTEX.SUPPORT TO ROLE CORTEX_DEV_ROLE;

-- Replace <YOUR_USER> with your Snowflake username, then run:
-- GRANT ROLE CORTEX_DEV_ROLE TO USER <YOUR_USER>;

USE ROLE CORTEX_DEV_ROLE;
USE WAREHOUSE CORTEX_WH;
USE SCHEMA SNOWCORTEX.SUPPORT;

-- ---- Structured data (used by Cortex LLM functions + Cortex Analyst) ---------
CREATE OR REPLACE TABLE SUPPORT_TICKETS (
  TICKET_ID     NUMBER        NOT NULL,
  CUSTOMER_NAME VARCHAR,
  PRODUCT       VARCHAR,
  CATEGORY      VARCHAR,
  PRIORITY      VARCHAR,
  STATUS        VARCHAR,
  CREATED_AT    TIMESTAMP_NTZ,
  RESOLVED_AT   TIMESTAMP_NTZ,
  DESCRIPTION   VARCHAR,
  CSAT_SCORE    NUMBER(2, 0),
  PRIMARY KEY (TICKET_ID)
);

INSERT INTO SUPPORT_TICKETS
  (TICKET_ID, CUSTOMER_NAME, PRODUCT, CATEGORY, PRIORITY, STATUS, CREATED_AT, RESOLVED_AT, DESCRIPTION, CSAT_SCORE)
VALUES
  (1001, 'Acme Corp',      'DataSync',  'Billing',     'High',   'Resolved', '2026-09-02 09:15:00', '2026-09-02 14:30:00',
   'We were charged twice for our October invoice. Please refund the duplicate payment as soon as possible. This is the second time this has happened.', 2),
  (1002, 'Globex',         'DataSync',  'Bug',         'High',   'Resolved', '2026-09-05 11:00:00', '2026-09-07 10:00:00',
   'Scheduled sync jobs fail with a timeout error every night after the latest upgrade. Our reporting is completely blocked.', 3),
  (1003, 'Initech',        'InsightBI', 'How-To',      'Low',    'Resolved', '2026-09-08 16:20:00', '2026-09-08 17:05:00',
   'How do I schedule a dashboard to be emailed to my team every Monday morning? Thanks, love the product so far!', 5),
  (1004, 'Umbrella Ltd',   'InsightBI', 'Bug',         'Medium', 'Open',     '2026-09-12 08:45:00', NULL,
   'Pie charts render with the wrong colors in dark mode and the legend is unreadable. Not urgent but quite annoying.', NULL),
  (1005, 'Hooli',          'DataSync',  'Feature',     'Low',    'Open',     '2026-09-15 13:10:00', NULL,
   'It would be great to have native support for incremental loads from Postgres. Currently we have to script this ourselves.', NULL),
  (1006, 'Stark Industries','AuthGuard','Security',    'High',   'Resolved', '2026-09-18 07:30:00', '2026-09-18 12:00:00',
   'We noticed multiple failed login attempts from unknown IP addresses on our admin account. Please advise on enabling MFA and IP allow-lists.', 4),
  (1007, 'Wayne Enterprises','AuthGuard','Bug',        'Medium', 'Resolved', '2026-09-21 10:05:00', '2026-09-22 09:00:00',
   'SSO login loops back to the sign-in page for users in our Europe region. Works fine in the US.', 3),
  (1008, 'Acme Corp',      'InsightBI', 'Billing',     'Medium', 'Resolved', '2026-09-25 15:40:00', '2026-09-26 11:20:00',
   'Can you send me a copy of last quarter''s invoices in PDF format? Our finance team needs them for the audit.', 5),
  (1009, 'Globex',         'AuthGuard', 'How-To',      'Low',    'Resolved', '2026-10-01 09:00:00', '2026-10-01 09:40:00',
   'Where can I find the audit log export for user permission changes?', 4),
  (1010, 'Initech',        'DataSync',  'Bug',         'High',   'Open',     '2026-10-06 12:25:00', NULL,
   'Data duplication in the destination table after a retry. This corrupted our customer master data and we are very frustrated.', NULL);

-- ---- Unstructured knowledge base (used by Cortex Search / RAG) --------------
CREATE OR REPLACE TABLE KB_ARTICLES (
  ARTICLE_ID NUMBER NOT NULL,
  TITLE      VARCHAR,
  CATEGORY   VARCHAR,
  BODY       VARCHAR,
  PRIMARY KEY (ARTICLE_ID)
);

INSERT INTO KB_ARTICLES (ARTICLE_ID, TITLE, CATEGORY, BODY)
VALUES
  (1, 'Fixing DataSync nightly job timeouts', 'Troubleshooting',
   'If scheduled DataSync jobs time out after an upgrade, increase the job timeout in Settings > Jobs from 30 to 120 minutes, '
   || 'and enable parallel extraction for tables larger than 10 million rows. If the problem persists, check that the connector '
   || 'version is 4.2.1 or later, which fixes a connection pool leak introduced in 4.1.0.'),
  (2, 'Scheduling dashboard emails in InsightBI', 'How-To',
   'Open the dashboard, click Share > Schedule delivery, choose a recipient list, pick a cadence (daily, weekly or monthly), '
   || 'and set the delivery time and time zone. Recipients without an InsightBI license receive a static PDF snapshot.'),
  (3, 'Enabling MFA and IP allow-lists in AuthGuard', 'Security',
   'Administrators can require multi-factor authentication under Security > Policies > MFA. To restrict logins, add CIDR ranges '
   || 'under Security > Network > IP allow-list. We recommend also enabling login anomaly alerts, which email admins when sign-ins '
   || 'occur from a new country or an unrecognized device.'),
  (4, 'Requesting invoices and refunds', 'Billing',
   'Invoices are available as PDFs under Account > Billing > Invoice history. Duplicate charges are refunded within 5 to 7 business '
   || 'days once confirmed by billing support. Please include the invoice number and last four digits of the card in your request.'),
  (5, 'Troubleshooting SSO redirect loops', 'Troubleshooting',
   'Redirect loops after SAML sign-in are most often caused by clock skew between the identity provider and AuthGuard, or by a '
   || 'mismatched Assertion Consumer Service URL for regional tenants. Verify the ACS URL matches the regional endpoint and that '
   || 'server time is synchronized via NTP.');

SELECT 'tickets' AS table_name, COUNT(*) AS row_count FROM SUPPORT_TICKETS
UNION ALL
SELECT 'kb_articles', COUNT(*) FROM KB_ARTICLES;
