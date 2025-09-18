# 🚀 BigQuery vs BigQuery External Tables vs PySpark Benchmarking

## 📌 Project Overview

This project provides a comprehensive performance comparison between three data processing engines using identical analytical workloads:

1. **BigQuery Native Table** – fully ingested CSV into BigQuery tables
2. **BigQuery External Table** – querying CSV files directly from Google Cloud Storage
3. **PySpark** – distributed processing using Apache Spark

**Dataset**: CMS Hospital Cost Report Information System (HCRIS) - financial and utilization data reported annually by U.S. hospitals.

The goal is to provide hands-on performance benchmarking across different data processing engines with identical queries, measuring CPU, storage, and cost performance while keeping workflows reproducible.

## 📂 Project Structure

```
benchmark-bq-spark/
├── data/
│   ├── raw/                    # Raw CSV files (source data for benchmarking)
│   └── processed/              # Cleaned and processed CSV files ready for engine comparison
├── scripts/
│   ├── config/                 # GCP configuration and connection management
│   ├── data_preparation/       # Sample and multi-year data generation ✅
│   │   ├── data_prepare.py     # Original sample data generator
│   │   ├── create_multiyear_sample.py  # Multi-year partitioned data generator ✅
│   │   └── hcris_downloader.py # Real CMS HCRIS data downloader (experimental)
│   ├── bigquery_native/        # BigQuery native table scripts ✅
│   ├── bigquery_external/      # BigQuery external table scripts ✅
│   ├── pyspark/               # PySpark processing scripts (planned)
│   ├── monitoring/            # Performance monitoring tools ✅
│   ├── pipeline_runner.py      # End-to-end pipeline orchestration ✅
│   └── staging_queries.sql     # Benchmark analytics queries ✅
├── results/                   # Performance metrics and analysis results
├── docs/                      # Project documentation
├── requirements.txt           # Python dependencies
├── .env.example              # Environment configuration template
└── .gitignore               # Git exclusions
```

### 📊 Dataset: CMS Hospital Cost Report Information System (HCRIS)

**What it is**: Financial and utilization data reported annually by U.S. hospitals  
**Why this dataset**: Contains complex analytical queries with joins, aggregations, and window functions - perfect for benchmarking different data processing engines.

### 🔄 Data Flow Across Engines

1. **Raw Data**: Source CSV files stored in `data/raw/` directory
2. **Processing**: Data preparation scripts clean and standardize data  
3. **Staging**: Processed files saved to `data/processed/` directory
4. **Engine Distribution**:
   - **BigQuery Native**: Ingest CSV into BigQuery tables
   - **BigQuery External**: Upload to GCS, query directly from storage  
   - **PySpark**: Load CSV into DataFrames for distributed processing

## 📊 Benchmark Query

This standardized analytical query is executed identically across all three engines to ensure fair performance comparison:

```sql
WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM reporting_period_end) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    hosp_cost_report
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
```

## ⚙️ Engine-Specific Query Adaptations

- **BigQuery Native** → works directly with the standard SQL
- **BigQuery External** → may need `EXTRACT(YEAR FROM CAST(reporting_period_end AS DATE))`
- **PySpark SQL** → replace `EXTRACT(YEAR FROM ...)` with `YEAR(reporting_period_end)`

## 📈 Performance Comparison Metrics

### 1. Query Performance
- Execution time (seconds)
- CPU utilization (%)
- Memory usage (MB/GB)

### 2. Storage Efficiency
- Raw CSV size on disk
- BigQuery native table storage
- External table scan volume
- PySpark memory footprint

### 3. Cost Analysis
- BigQuery processing costs (per query)
- BigQuery storage costs
- PySpark compute costs (local/cluster)

## 🚀 Workflow

### 1. Data Preparation
- Run `scripts/data_preparation/data_prepare.py` to download, unzip, and clean CSVs
- Cleaned CSVs are saved to `/data/processed/`

### 2. GCS Staging
- Upload processed CSVs to GCS bucket (`gs://your-bucket/processed/`)

### 3. Execution
- **BigQuery Native**: `bq_ingest.py` loads CSV into BigQuery table → run benchmark
- **BigQuery External**: `create_external_table.py` points to CSV in GCS → run benchmark
- **PySpark**: `pyspark_load.py` reads CSV into DataFrame → run benchmark

### 4. Monitoring & Metrics
- Use `monitor_cpu.py` to track CPU/memory during PySpark execution
- `benchmark.py` in orchestrator/ collects runtime, storage, and cost metrics

### 5. Performance Analysis
- Compare execution time, storage efficiency, and cost across all three engines
- Store results in `/results/benchmark_results.csv` and generate comparison charts

## 🛠️ Setup Instructions

### 1. Environment Setup
```bash
# Clone repo
git clone https://github.com/your-username/benchmark-bq-spark.git
cd benchmark-bq-spark

# Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Google Cloud Platform Configuration ✅
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your GCP project settings:
# - GOOGLE_CLOUD_PROJECT=your-project-id
# - GCS_BUCKET_NAME=your-unique-bucket-name
# - GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Authenticate with GCP
gcloud auth application-default login

# Enable required APIs
gcloud services enable bigquery.googleapis.com storage.googleapis.com

# Create BigQuery dataset
bq mk --dataset --location=us-east1 your-project:healthcare_benchmark

# Create GCS bucket (must be globally unique)
gsutil mb -p your-project -l us-east1 gs://your-unique-bucket-name/

# Test connections
python scripts/test_connections.py
```

### 3. Verification
- ✅ **Virtual Environment**: Python dependencies installed
- ✅ **GCP Authentication**: Service account or default credentials configured  
- ✅ **BigQuery Access**: Dataset created and accessible
- ✅ **Cloud Storage Access**: Bucket created and accessible
- ✅ **Connection Tests**: All 6 connection tests passing

## 🧪 POC: BigQuery Load to Staging Table ✅

### Data Pipeline Implementation
We've successfully implemented and tested the first part of our benchmarking pipeline:

#### 1. **Multi-Year Data Generation & Upload** ✅ NEW
```bash
# Generate realistic multi-year hospital cost data for partitioning demonstration
python scripts/data_preparation/create_multiyear_sample.py

# Options:
# --years 2021,2022,2023    # Comma-separated years (default: 2021,2022,2023)
# --hospitals 1000          # Hospitals per year (default: 1000)
# --test-mode              # Generate smaller dataset for testing (100 per year)

# Result: Multi-year data uploaded to GCS
# Location: gs://your-bucket/raw/multiyear/multiyear_hospitals_YYYY.csv
# Size: 300 hospitals across 3 years with realistic financial trends
```

**Multi-Year Data Features**:
- 📊 **Yearly Partitioning**: Automatic partitioning by `report_period` field
- 📈 **Realistic Trends**: 3.5% annual cost inflation + COVID-19 impact (2020-2022)
- 🏥 **Hospital Consistency**: Same provider IDs across years with evolving financials
- 🎯 **Partition Pruning**: 67% data reduction when filtering by year

#### 2. **BigQuery Staging Table Creation**
- **Table**: `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
- **Optimization**: 
  - 📅 **Partitioned** by `report_period` (daily partitioning enables yearly filtering)
  - 🏷️ **Clustered** by `provider_id` for efficient lookups
- **Schema**: 14 columns with proper data types (STRING, INTEGER, FLOAT, DATE)
- **Data**: 300 hospital records across 3 years (2021-2023) for meaningful partitioning demonstration

#### 3. **Data Load Methods Comparison**

##### Option 1: Shell Script with `bq load` ✅ COMPLETED
```bash
# Execute optimized load script
./scripts/bigquery_native/load_to_staging.sh

# Features:
# - Automatic table creation with partitioning/clustering
# - Schema validation and file discovery  
# - Comprehensive error handling and logging
# - Load time: ~1-2 seconds for 100 rows
```

**Results**: 
- ✅ 300 multi-year records successfully loaded (replacing previous 100-record sample)
- ✅ Data distributed across 3 yearly partitions (2021-2023)
- ✅ Table optimized for benchmark queries with partition pruning
- ✅ Performance metrics documented in `results/option1_bq_load_metrics.md`

##### Multi-Year Data Validation ✅ COMPLETED
```bash
# Verify yearly partitioning
bq query --use_legacy_sql=false "SELECT EXTRACT(YEAR FROM report_period) as year, COUNT(*) as hospitals FROM healthcare_benchmark.stg_healthcare_hospital_data GROUP BY year ORDER BY year"

# Results:
# 2021: 100 hospitals
# 2022: 100 hospitals  
# 2023: 100 hospitals

# Test partition pruning (67% data reduction)
bq query --use_legacy_sql=false "SELECT COUNT(*) FROM healthcare_benchmark.stg_healthcare_hospital_data WHERE EXTRACT(YEAR FROM report_period) = 2023"
# Result: 100 hospitals (scans only 2023 partition vs all 300 records)
```

**Partition Pruning Benefits**:
- 🎯 **67% Data Reduction**: Year-specific queries scan only relevant partition
- 📊 **Realistic Financial Trends**: Average expenses increased from $78.9M (2021) to $80.8M (2023)
- 💰 **Cost Optimization**: Partition pruning significantly reduces BigQuery processing costs
- 🔄 **Temporary Storage**: Multi-year files uploaded to GCS and cleaned up after testing

#### 4. **Next Steps: Additional Load Methods**
- **Option 2**: Python script with BigQuery API (planned)
- **Option 3**: BigQuery Transfer Service (planned)
- **Comparison**: Performance, complexity, and operational analysis

#### 5. **Benchmark Ready**
The staging table is now ready for engine comparison benchmarking:
```sql
-- Sample benchmark query (hospitals with >50 beds)
WITH yearly_summary AS (
  SELECT provider_id, EXTRACT(YEAR FROM reporting_period_end) AS report_year,
         SUM(total_expenses) AS total_expenses, SUM(net_income) AS total_net_income
  FROM `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
  WHERE beds > 50
  GROUP BY provider_id, report_year
)
SELECT * FROM yearly_summary LIMIT 10;
```

## 📊 Benchmark Query Validation Results ✅

### Performance Testing Completed
Successfully executed and validated 3 analytics queries with progressive optimization:

| Query | Description | Execution Time | Data Processed | Optimization | Status |
|-------|-------------|----------------|----------------|--------------|--------|
| **Query 1** | Original (Full Table Scan) | 2.3 seconds | 4.8KB (4 partitions) | None | ✅ Validated |
| **Query 2** | Year-Filtered (Partition Pruning) | 2.1 seconds | 1KB (1 partition) | 78% data reduction | ✅ Validated |
| **Query 3** | Year + Provider (Full Optimization) | 2.1 seconds | 1KB (4 records) | 60% result reduction | ✅ Validated |

### Key Validation Results
- ✅ **Window Functions**: RANK, DENSE_RANK, LAG, LEAD all working correctly
- ✅ **Partition Pruning**: 78% reduction in data scanned (4.8KB → 1KB)
- ✅ **Clustering Benefits**: 60% reduction in result set (10 → 4 records)
- ✅ **Cost Optimization**: Free tier to Tier 1 based on query complexity
- ✅ **BigQuery Native Baseline**: Ready for engine comparison

### Staging Table Ready for Engine Comparison
- **Table**: `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
- **Optimization**: Partitioned by `report_period`, clustered by `provider_id`
- **Data**: 100 sample records across 4 years (2021-2024)
- **Schema**: 14 columns with proper data types
- **Queries**: 3 benchmark queries in `scripts/staging_queries.sql`

**📈 Detailed Performance Analysis**: See `results/benchmark_queries_performance_analysis.md`

## 📊 BigQuery Native vs External Table Comparison ✅

### Performance Testing Completed
Successfully executed comparative benchmarks between BigQuery Native and External Tables:

| Query | Native Table | External Table | Performance Difference | Winner |
|-------|--------------|----------------|------------------------|--------|
| **Query 1 (Original)** | 2.67s | 2.48s | 7.1% faster | 🟢 External |
| **Query 2 (Year Filter)** | 2.14s | 2.37s | 11.0% slower | 🔴 External |
| **Query 3 (Multi Filter)** | 2.08s | 2.16s | 4.2% slower | 🟡 External |
| **Overall Average** | 2.29s | 2.34s | 2.0% slower | External competitive |

### Key Comparison Results
- ✅ **Competitive Performance**: External tables within 2% of native table performance
- ✅ **External Table**: `ext_healthcare_hospital_data` (800 records across 8 CSV files)
- ❌ **No Optimization Benefits**: External tables scan all files regardless of filters
- ✅ **Cost Trade-offs**: Lower storage costs but higher processing for frequent queries
- ✅ **Automated Framework**: Complete benchmark runner for repeatable comparisons

### External Table Implementation
- **Table**: `benchmark-bq-spark.healthcare_benchmark.ext_healthcare_hospital_data`
- **Data Source**: Direct CSV file scanning from GCS (`gs://bucket/raw/*.csv`)
- **Schema**: 14 columns adapted for CSV structure (`beds` vs `beds_number`)
- **Queries**: 3 adapted benchmark queries in `scripts/bigquery_external/`
- **Framework**: Automated creation and benchmarking scripts

**📈 Detailed External Table Analysis**: See `results/external_table_performance_analysis.md` and `EXTERNAL_TABLE_SUMMARY.md`

## ☁️ Engine Deployment

- **Google Cloud Storage**: CSV file staging for both BigQuery approaches
- **BigQuery Native** ✅: Table ingestion completed with performance baseline
- **BigQuery External** ✅: CSV file querying completed with performance comparison
- **PySpark** 🔄: Local execution or cloud clusters (next implementation)

## 🤝 Contributing

- Pull requests welcome for additional benchmark queries, datasets, or engine comparisons
- Follow the engine-based folder convention for clear separation of concerns

## 📄 License

[Add license information]