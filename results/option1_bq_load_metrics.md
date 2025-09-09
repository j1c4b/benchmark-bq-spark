# Option 1: Shell Script with bq load - Performance Metrics

## 📊 Test Overview
- **Date**: September 8, 2025
- **Method**: Shell script using `bq load` command
- **Data Source**: GCS bucket (`gs://benchmark-bq-spark-hospital-data-1757386491/raw/`)
- **Target**: BigQuery staging table with partitioning and clustering
- **Data Size**: 100 hospital records (11,890 bytes / 11.61 KiB)

## 🎯 Table Configuration
- **Full Table ID**: `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
- **Schema**: 14 columns with appropriate data types
- **Partitioning**: Daily partitioning by `reporting_period_end` (DATE field)
- **Clustering**: Clustered by `provider_id` 
- **Description**: "Staging table for hospital cost report data with optimized partitioning and clustering"

## ⚡ Performance Results

### Load Operation
- **Command**: `bq load --source_format=CSV --skip_leading_rows=1 --replace=false`
- **Duration**: ~1-2 seconds (small dataset)
- **Status**: ✅ SUCCESS
- **Job Status**: DONE without errors

### Data Verification
- **Total Records Loaded**: 100 rows
- **Data Integrity**: ✅ All records successfully loaded
- **Partitioning**: ✅ Data distributed across 4 partitions:
  - 2021-12-31: 32 records
  - 2022-12-31: 25 records  
  - 2023-12-31: 22 records
  - 2024-12-31: 21 records

### Data Quality Check
```sql
SELECT provider_id, hospital_name, city, state, beds, reporting_period_end, total_expenses 
FROM `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data` 
ORDER BY reporting_period_end, provider_id
LIMIT 5
```

**Sample Results**:
| provider_id | hospital_name | city | state | beds | reporting_period_end | total_expenses |
|-------------|---------------|------|-------|------|----------------------|----------------|
| 100001 | San Diego Regional | San Diego | OH | 304 | 2021-12-31 | 1.601456881E8 |
| 100004 | San Diego Presbyterian | San Diego | MI | 106 | 2021-12-31 | 1.938626324E7 |

## 🏗️ Implementation Details

### Shell Script Features
- ✅ **Environment Validation**: Checks bq CLI, gcloud auth, project config
- ✅ **Schema Management**: Auto-generates JSON schema file
- ✅ **File Discovery**: Automatically finds latest data file in GCS
- ✅ **Table Optimization**: Creates partitioned and clustered table
- ✅ **Error Handling**: Comprehensive error checking and logging
- ✅ **Cleanup**: Removes temporary files after execution

### Schema Definition
```json
{
  "provider_id": "STRING (REQUIRED)",
  "hospital_name": "STRING",
  "city": "STRING", 
  "state": "STRING",
  "beds": "INTEGER",
  "reporting_period_end": "DATE",
  "total_expenses": "FLOAT",
  "total_charges": "FLOAT",
  "net_income": "FLOAT",
  "patient_days": "INTEGER",
  "discharges": "INTEGER", 
  "fte_employees": "INTEGER",
  "medicare_days": "INTEGER",
  "medicaid_days": "INTEGER"
}
```

## 💡 Pros and Cons

### ✅ Advantages
1. **Simple and Direct**: Straightforward bq CLI commands
2. **Built-in Optimization**: Native BigQuery partitioning and clustering
3. **Fast Execution**: Quick load for small to medium datasets
4. **Scriptable**: Easy to integrate into automation workflows
5. **Error Handling**: Clear error messages and validation
6. **No Code Dependencies**: Uses standard Google Cloud SDK tools

### ⚠️ Limitations
1. **CLI Dependency**: Requires gcloud SDK and bq CLI installed
2. **Limited Monitoring**: Basic job status only
3. **Shell Script Complexity**: Error handling and validation add complexity
4. **Platform Dependent**: Shell script may need adaptation for different OS
5. **Manual Schema Management**: Requires maintaining separate schema files

## 🔄 Next Steps
1. Implement **Option 2**: Python script with BigQuery API
2. Implement **Option 3**: BigQuery Transfer Service
3. Compare performance metrics across all three approaches
4. Analyze cost and operational complexity differences

## 📈 Benchmark Query Ready
The staging table is now ready for benchmark queries:
```sql
WITH yearly_summary AS (
  SELECT
    provider_id,
    EXTRACT(YEAR FROM reporting_period_end) AS report_year,
    SUM(total_expenses) AS total_expenses,
    AVG(total_charges) AS avg_charges,
    SUM(net_income) AS total_net_income
  FROM
    `benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data`
  WHERE
    beds > 50
  GROUP BY
    provider_id, report_year
)
SELECT * FROM yearly_summary LIMIT 10;
```

---
**Status**: ✅ Option 1 Complete - Ready for engine comparison benchmarking