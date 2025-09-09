# CSV Pipeline Runner Usage Guide

## 🚀 Quick Start

### Option 1: Use Existing CSV File
```bash
python run_pipeline.py path/to/your/hospital_data.csv
```

### Option 2: Generate Sample Data
```bash
# Generate 100 sample records (default)
python run_pipeline.py --generate-sample

# Generate custom number of records  
python run_pipeline.py --generate-sample --rows 500
```

### Option 3: Use Existing Sample (Auto-detect)
```bash
python run_pipeline.py
```

## 📊 What the Pipeline Does

### Complete Process Flow:
1. **📤 CSV Upload** → Upload file to Google Cloud Storage
2. **🏗️ Table Creation** → Create partitioned/clustered BigQuery staging table  
3. **📊 Data Load** → Load CSV data into BigQuery with schema validation
4. **🔍 Analytics Processing** → Create analytics table with computed metrics
5. **📋 Data Summarization** → Generate comprehensive staging/analytics summaries
6. **📈 Metrics Collection** → Capture performance, storage, and cost metrics

### Real-Time Metrics Captured:
- **Performance**: Execution time, CPU usage, memory consumption  
- **Storage**: BigQuery table sizes, compression ratios, partition counts
- **Data Quality**: Record counts, value distributions, rankings
- **Cost**: BigQuery processing costs and slot usage

## 📋 Output Files Generated

All results saved in `results/` directory:

### Performance & Metrics:
- `csv_pipeline_YYYYMMDD_HHMMSS.json` - Detailed metrics (structured)
- `csv_pipeline_YYYYMMDD_HHMMSS.csv` - Flattened metrics (for analysis)

### Data Summaries:  
- `pipeline_summary_YYYYMMDD_HHMMSS.md` - Human-readable comprehensive report

### Example Output Structure:
```
results/
├── csv_pipeline_20250909_101701.json      # Detailed performance metrics
├── csv_pipeline_20250909_101701.csv       # Metrics for analysis  
└── pipeline_summary_20250909_101701.md    # Complete data summary
```

## 🔍 Sample Output Summary

```
🎉 PIPELINE COMPLETED SUCCESSFULLY!
⏱️  Total Execution Time: 5.43 seconds
📊 Records Processed: 100
🏆 Analytics Records: 86 (filtered for hospitals >50 beds)
💾 Storage Efficiency: 2.14x compression
💰 Estimated Cost: $0.000000
```

## 📊 Data Summaries Generated

### Staging Table Analysis:
- **Year Distribution**: Hospitals by reporting year with financial metrics
- **Size Categories**: Small/Medium/Large/Very Large hospital analysis
- **Geographic Distribution**: Top states by hospital count  
- **Financial Summary**: Min/max/avg expenses and net income statistics

### Analytics Table Insights:
- **Top Performers**: Top 5 hospitals by net income per year
- **Year-over-Year Growth**: Growing vs declining hospitals
- **Income Rankings**: Performance rankings and distributions
- **Financial Quartiles**: Income distribution analysis

## 🏗️ BigQuery Tables Created

### Staging Table: `healthcare_benchmark.stg_healthcare_hospital_data`
- **Partitioned by**: `report_period` (daily partitions)  
- **Clustered by**: `provider_id` (for efficient lookups)
- **Schema**: 14 columns with proper data types
- **Purpose**: Optimized raw data storage

### Analytics Table: `healthcare_benchmark.analytics_healthcare_hospital_data`  
- **Computed Metrics**: Rankings, year-over-year changes, lag/lead calculations
- **Window Functions**: RANK(), DENSE_RANK(), LAG(), LEAD()
- **Purpose**: Business intelligence and performance analysis

## ⚙️ Requirements

- Python 3.8+ with virtual environment activated
- Google Cloud SDK configured
- BigQuery and Cloud Storage APIs enabled
- Valid service account or default credentials

## 🎯 CSV File Format Expected

The pipeline expects CSV files with these columns:
- `provider_id` (integer)
- `hospital_name` (string)  
- `city`, `state` (strings)
- `beds_number` (integer)
- `report_period` (date: YYYY-MM-DD)
- `total_expenses`, `total_charges`, `net_income` (floats)
- `patient_days`, `discharges`, `fte_employees` (integers)
- `medicare_days`, `medicaid_days` (integers)

## 🔄 Next Steps

After running the pipeline:

1. **Review Summary**: Check `pipeline_summary_*.md` for insights
2. **Analyze Metrics**: Import CSV metrics into your preferred analysis tool
3. **Query Analytics**: Use BigQuery to explore the analytics table
4. **Compare Engines**: Run same data through External Tables or PySpark versions

## 💡 Pro Tips

- **Performance**: Larger datasets show better compression ratios
- **Cost Optimization**: Partitioning by date enables efficient querying  
- **Scaling**: Pipeline handles datasets from 100 to millions of records
- **Monitoring**: All execution phases are timed with resource monitoring

Ready to benchmark your data processing engines! 🚀