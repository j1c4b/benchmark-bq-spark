# Complete Pipeline Execution Summary
**Generated**: 2025-09-09 10:17:01
**Pipeline**: CSV → GCS → BigQuery Staging → Analytics Processing

## 🚀 Performance Metrics

### CSV Upload
- **Duration**: 0.37 seconds
- **CPU Usage**: 5.5% average, 10.9% peak
- **Memory**: 100.5MB peak

### Table Creation
- **Duration**: 0.59 seconds
- **CPU Usage**: 4.5% average, 8.9% peak
- **Memory**: 102.7MB peak

### Data Load
- **Duration**: 2.31 seconds
- **CPU Usage**: 0.3% average, 0.7% peak
- **Memory**: 102.8MB peak

### Analytics Processing
- **Duration**: 2.75 seconds
- **CPU Usage**: 0.3% average, 0.7% peak
- **Memory**: 102.9MB peak

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

## 🏆 Analytics Summary

**Analytics Records**: 86

### Top 5 Performers by Year
| Provider | Year | Net Income | Rank | Total Expenses |
|----------|------|------------|------|----------------|
| 100035 | 2021 | $215,090,022 | 1 | $110,511,980 |
| 100028 | 2021 | $193,968,730 | 2 | $161,185,544 |
| 100083 | 2021 | $147,797,010 | 3 | $119,361,215 |
| 100071 | 2021 | $117,824,954 | 4 | $170,344,691 |
| 100030 | 2021 | $94,766,001 | 5 | $137,023,458 |
| 100052 | 2022 | $210,967,605 | 1 | $186,686,266 |
| 100018 | 2022 | $128,531,679 | 2 | $140,701,361 |
| 100097 | 2022 | $127,613,687 | 3 | $109,994,012 |
| 100093 | 2022 | $110,927,921 | 4 | $110,839,315 |
| 100080 | 2022 | $109,207,072 | 5 | $98,690,863 |