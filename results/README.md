# Results Directory

This directory contains benchmark results and analysis outputs.

## Expected Files

- `benchmark_results.csv` - Raw benchmark metrics across all engines
- `performance_comparison.json` - Structured performance data
- `charts/` - Generated visualization charts
- `reports/` - Analysis reports and summaries

## Metrics Captured

### Performance
- Execution time (seconds)
- CPU utilization (%)
- Memory usage (MB)

### Storage
- Raw CSV size (MB)
- BigQuery table size (MB)
- External table scan bytes
- PySpark memory footprint (MB)

### Cost
- BigQuery processing cost ($)
- BigQuery storage cost ($)
- PySpark compute cost ($)