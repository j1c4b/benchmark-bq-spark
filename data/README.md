# Data Directory

## Structure

- `raw/` - Raw CSV files (source data for benchmarking)
- `processed/` - Cleaned and processed CSV files ready for engine comparison

## Dataset: CMS Hospital Cost Report Information System (HCRIS)

**What it is**: Financial and utilization data reported annually by U.S. hospitals  
**Why this dataset**: Contains complex analytical queries with joins, aggregations, and window functions - perfect for benchmarking different data processing engines.

## Multi-Engine Data Flow

1. **Raw Data**: Place source CSV files in the `raw/` directory
2. **Processing**: Run data preparation scripts to clean and standardize data
3. **Staging**: Processed files saved to `processed/` directory
4. **Engine Distribution**:
   - **BigQuery Native**: Ingest into BigQuery tables
   - **BigQuery External**: Upload to GCS, query directly from storage
   - **PySpark**: Load into DataFrames for distributed processing