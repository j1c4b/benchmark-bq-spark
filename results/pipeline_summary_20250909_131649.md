# Complete Pipeline Execution Summary
**Generated**: 2025-09-09 13:16:49
**Pipeline**: CSV → GCS → BigQuery Staging

## 🚀 Performance Metrics

### CSV Upload
- **Duration**: 3.83 seconds
- **CPU Usage**: 6.0% average, 11.9% peak
- **Memory**: 101.9MB peak

### Table Creation
- **Duration**: 0.72 seconds
- **CPU Usage**: 3.0% average, 6.0% peak
- **Memory**: 101.6MB peak

### Data Load
- **Duration**: 3.49 seconds
- **CPU Usage**: 0.2% average, 0.5% peak
- **Memory**: 101.9MB peak

## 📊 Staging Table Summary

**Total Records**: 100

### Year Distribution
| Year | Hospitals | Avg Beds | Total Expenses | Avg Expenses |
|------|-----------|----------|----------------|--------------|
| 2021 | 32 | 148 | $2,130,925,752 | $66,591,430 |
| 2022 | 25 | 124 | $1,581,803,981 | $63,272,159 |
| 2023 | 22 | 114 | $1,029,717,829 | $46,805,356 |
| 2024 | 21 | 149 | $1,383,744,187 | $65,892,580 |

### Hospital Size Categories
| Size Category | Hospitals | Avg Expenses | Avg Net Income |
|---------------|-----------|--------------|----------------|
| Small (<50) | 12 | $18,550,603 | $27,958,386 |
| Medium (50-99) | 28 | $33,894,532 | $30,842,108 |
| Large (100-199) | 43 | $62,139,152 | $62,813,562 |
| Very Large (200+) | 17 | $134,267,887 | $113,693,649 |

## 📊 Pipeline Focus: Staging Table Ready

The staging table is optimized and ready for:
- **BigQuery Native**: Direct querying with partitioning/clustering benefits
- **BigQuery External**: Link to GCS files for direct querying
- **Spark Processing**: Load staging data into Spark DataFrames
