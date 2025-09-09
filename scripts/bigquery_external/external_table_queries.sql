-- External Table Analytics Queries for BigQuery vs External vs Spark Benchmarking
-- Adapted for external table column names (beds, reporting_period_end vs beds_number, report_period)
-- Based on the main benchmark query from README.md

-- =============================================================================
-- QUERY 1: Original Analytics Query (No Optimization Filters) - External Table
-- =============================================================================
-- This query uses the main benchmark logic without additional WHERE clauses
-- Tests: Full CSV file scan performance across all files
-- Expected: Slower performance than native table due to file scanning overhead

WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM reporting_period_end) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.ext_healthcare_hospital_data`
  WHERE
    beds > 50
  GROUP BY
    provider_id, report_year
)
SELECT
  provider_id,
  report_year,
  total_expenses,
  avg_charges,
  total_net_income,
  RANK() OVER (PARTITION BY report_year ORDER BY total_net_income DESC) AS income_rank,
  DENSE_RANK() OVER (PARTITION BY report_year ORDER BY total_net_income DESC) AS dense_income_rank,
  LAG(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS prev_net_income,
  LEAD(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS next_net_income,
  total_net_income - LAG(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS yoy_change
FROM
  yearly_summary
ORDER BY
  report_year, income_rank
LIMIT 100;

-- =============================================================================
-- QUERY 2: Year-Filtered Analytics Query - External Table
-- =============================================================================
-- This query adds a specific year filter 
-- Tests: File scanning with year filter (no partition pruning available)
-- Expected: Similar performance to Query 1 (external tables don't support partitioning)

WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM reporting_period_end) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.ext_healthcare_hospital_data`
  WHERE
    beds > 50
    AND EXTRACT(YEAR FROM reporting_period_end) = 2023  -- Year filter (no partition benefits)
  GROUP BY
    provider_id, report_year
)
SELECT
  provider_id,
  report_year,
  total_expenses,
  avg_charges,
  total_net_income,
  RANK() OVER (PARTITION BY report_year ORDER BY total_net_income DESC) AS income_rank,
  DENSE_RANK() OVER (PARTITION BY report_year ORDER BY total_net_income DESC) AS dense_income_rank,
  LAG(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS prev_net_income,
  LEAD(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS next_net_income,
  total_net_income - LAG(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS yoy_change
FROM
  yearly_summary
ORDER BY
  report_year, income_rank
LIMIT 100;

-- =============================================================================
-- QUERY 3: Year + Provider Filtered Analytics Query - External Table  
-- =============================================================================
-- This query adds both year and provider_id filters
-- Tests: File scanning with multiple filters (no clustering benefits available)
-- Expected: Similar performance to Query 1&2 (external tables scan all files)

WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM reporting_period_end) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.ext_healthcare_hospital_data`
  WHERE
    beds > 50
    AND EXTRACT(YEAR FROM reporting_period_end) = 2023  -- Year filter (no partition benefits)
    AND provider_id >= 100020 AND provider_id <= 100040  -- Provider filter (no clustering benefits)
  GROUP BY
    provider_id, report_year
)
SELECT
  provider_id,
  report_year,
  total_expenses,
  avg_charges,
  total_net_income,
  RANK() OVER (PARTITION BY report_year ORDER BY total_net_income DESC) AS income_rank,
  DENSE_RANK() OVER (PARTITION BY report_year ORDER BY total_net_income DESC) AS dense_income_rank,
  LAG(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS prev_net_income,
  LEAD(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS next_net_income,
  total_net_income - LAG(total_net_income) OVER (PARTITION BY provider_id ORDER BY report_year) AS yoy_change
FROM
  yearly_summary
ORDER BY
  report_year, income_rank
LIMIT 100;

-- =============================================================================
-- PERFORMANCE EXPECTATIONS FOR EXTERNAL TABLE
-- =============================================================================
/*
BigQuery External Table Performance Expectations:
- Query 1: ~3-5 seconds (full CSV file scan, 8 files × ~12KB each)
- Query 2: ~3-5 seconds (same file scanning, filtering happens after scan)  
- Query 3: ~3-5 seconds (same file scanning, no optimization benefits)

Key Differences from Native Table:
- NO partition pruning: All CSV files are scanned regardless of year filter
- NO clustering benefits: provider_id filtering happens after full file scan
- Network I/O overhead: Data transferred from GCS to BigQuery for processing
- Higher latency: File scanning + network transfer vs direct table access
- Different cost model: Bytes scanned from GCS vs bytes processed in BigQuery

Expected Performance Comparison:
- Native Table Query 1: 2.3s → External Table Query 1: ~4s (74% slower)
- Native Table Query 2: 2.1s → External Table Query 2: ~4s (90% slower - no partition benefits)
- Native Table Query 3: 2.1s → External Table Query 3: ~4s (90% slower - no clustering benefits)

Cost Implications:
- Native: BigQuery processing costs ($5/TB) + storage costs ($20/TB/month)
- External: BigQuery scan costs ($5/TB) + GCS storage costs ($0.023/GB/month) + network egress
- External tables typically more cost-effective for infrequently queried data
- Native tables better for frequently queried data due to optimizations
*/

-- =============================================================================
-- SCHEMA MAPPING: Native Table vs External Table
-- =============================================================================
/*
Native Table (stg_healthcare_hospital_data):
- beds_number (INTEGER) 
- report_period (DATE)
- Partitioned by report_period
- Clustered by provider_id

External Table (ext_healthcare_hospital_data):  
- beds (INTEGER)
- reporting_period_end (DATE)
- No partitioning support
- No clustering support

Query Adaptations Required:
1. beds_number → beds
2. report_period → reporting_period_end  
3. Remove partition optimization expectations
4. Remove clustering optimization expectations
5. Expect consistent ~4s performance across all queries
*/