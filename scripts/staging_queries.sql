-- Analytics Queries for BigQuery vs External vs Spark Benchmarking
-- Based on the main benchmark query from README.md
-- Adapted to use staging table with partitioning and clustering optimizations

-- =============================================================================
-- QUERY 1: Original Analytics Query (No Optimization Filters)
-- =============================================================================
-- This query uses the main benchmark logic without additional WHERE clauses
-- Tests: Full table scan performance across all partitions
-- Expected: Slower performance but complete dataset analysis

WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM report_period) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
  WHERE
    beds_number > 50
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
-- QUERY 2: Year-Filtered Analytics Query (Partition Optimization)
-- =============================================================================
-- This query adds a specific year filter to leverage date partitioning
-- Tests: Partition pruning performance - should scan only 1 partition
-- Expected: Faster performance due to partition elimination

WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM report_period) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
  WHERE
    beds_number > 50
    AND EXTRACT(YEAR FROM report_period) = 2023  -- Partition filter
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
-- QUERY 3: Year + Provider Filtered Analytics Query (Full Optimization)
-- =============================================================================
-- This query adds both year and provider_id filters for maximum optimization
-- Tests: Both partition pruning + clustering benefits
-- Expected: Fastest performance due to both optimizations active

WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM report_period) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
  WHERE
    beds_number > 50
    AND EXTRACT(YEAR FROM report_period) = 2023  -- Partition filter
    AND provider_id >= 100020 AND provider_id <= 100040  -- Clustering filter
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
-- PERFORMANCE EXPECTATIONS
-- =============================================================================
/*
BigQuery Native Performance Expectations:
- Query 1: ~2-3 seconds (full table scan, all partitions)
- Query 2: ~1-2 seconds (single partition scan)  
- Query 3: <1 second (partition + clustering optimization)

BigQuery External Performance Expectations:
- Query 1: ~5-8 seconds (full GCS file scan)
- Query 2: ~3-5 seconds (filtered GCS scan)
- Query 3: ~2-3 seconds (optimized GCS scan)

Spark Performance Expectations:
- Query 1: ~3-5 seconds (DataFrame full scan)
- Query 2: ~2-3 seconds (DataFrame partition filter)
- Query 3: ~1-2 seconds (DataFrame optimized filter)

Cost Expectations:
- Query 1: Highest (most data processed)
- Query 2: Medium (partition pruning saves cost)
- Query 3: Lowest (both optimizations active)
*/

-- =============================================================================
-- ADAPTATION NOTES FOR EACH ENGINE
-- =============================================================================
/*
BigQuery Native:
- Uses table directly: `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
- Partition filter: EXTRACT(YEAR FROM report_period) = 2023
- Clustering filter: provider_id >= 100020 AND provider_id <= 100040

BigQuery External:
- Points to GCS files: CREATE EXTERNAL TABLE ... OPTIONS (uris=['gs://bucket/raw/*.csv'])
- Same query logic, but scans CSV files directly
- Partitioning simulation via file organization

Spark SQL:
- DataFrame: df = spark.read.csv("gs://bucket/raw/*.csv")
- Spark SQL syntax: df.createOrReplaceTempView("stg_healthcare_hospital_data")
- Query adaptation: YEAR(report_period) instead of EXTRACT(YEAR FROM report_period)
*/