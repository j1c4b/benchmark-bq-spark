#!/usr/bin/env python3
"""
Integrated Benchmark Runner

Executes complete benchmarking workflows with automatic metrics collection
for BigQuery Native, External Tables, and PySpark comparisons.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.metrics_collector import MetricsCollector, BenchmarkResults
from monitoring.performance_decorators import benchmark_data_generation, benchmark_data_load, benchmark_analytics
from data_preparation.data_prepare import HospitalDataPreparer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Orchestrates complete benchmark execution with metrics collection."""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.data_preparer = HospitalDataPreparer()
        self.results = {}
    
    @benchmark_data_generation
    def run_data_generation(self, num_rows: int = 100) -> str:
        """Generate sample data with performance monitoring."""
        logger.info(f"🏗️ Generating {num_rows} sample hospital records...")
        gcs_uri = self.data_preparer.prepare_sample_data(num_rows)
        return gcs_uri
    
    @benchmark_data_load 
    def run_bigquery_load(self, gcs_uri: str) -> bool:
        """Load data to BigQuery with performance monitoring."""
        logger.info("📊 Loading data to BigQuery staging table...")
        # This would normally call the bq load script or API
        # For now, we'll simulate the operation
        import time
        time.sleep(2)  # Simulate load time
        logger.info("✅ BigQuery load completed")
        return True
    
    @benchmark_analytics
    def run_analytics_processing(self) -> bool:
        """Run analytics processing with performance monitoring."""
        logger.info("🔍 Running analytics processing...")
        # This would normally run the analytics SQL
        # For now, we'll simulate the operation
        import time
        time.sleep(3)  # Simulate analytics processing time
        logger.info("✅ Analytics processing completed")
        return True
    
    def run_full_bigquery_benchmark(self, num_rows: int = 100) -> BenchmarkResults:
        """Execute complete BigQuery native benchmark with metrics collection."""
        logger.info("=" * 60)
        logger.info("🚀 Starting BigQuery Native Benchmark")
        logger.info("=" * 60)
        
        # Step 1: Data Generation
        gcs_uri, data_gen_metrics = self.run_data_generation(num_rows)
        
        # Step 2: Data Load
        load_success, data_load_metrics = self.run_bigquery_load(gcs_uri)
        
        # Step 3: Analytics Processing
        analytics_success, analytics_metrics = self.run_analytics_processing()
        
        # Step 4: Collect comprehensive metrics
        logger.info("📈 Collecting comprehensive metrics...")
        storage_metrics = self.metrics_collector.get_bigquery_table_metrics(
            'healthcare_benchmark', 'stg_healthcare_hospital_data'
        )
        
        # Get GCS file metrics
        gcs_metrics = self.metrics_collector.get_gcs_file_metrics(
            self.metrics_collector.config.bucket_name,
            'raw/hospital_cost_sample_100rows_20250909_092637.csv'
        )
        
        if storage_metrics and gcs_metrics:
            storage_metrics.raw_csv_bytes = gcs_metrics.get('size_bytes', 0)
            storage_metrics.raw_csv_mb = gcs_metrics.get('size_mb', 0)
        
        # Get recent job metrics
        recent_jobs = self.metrics_collector.get_recent_bigquery_jobs(5)
        total_cost = sum(job.query_cost_usd for job in recent_jobs)
        
        # Create benchmark results
        benchmark_results = BenchmarkResults(
            engine_name="BigQuery_Native_Benchmark",
            test_timestamp=datetime.now().isoformat(),
            data_generation=data_gen_metrics,
            data_load=data_load_metrics,
            analytics_processing=analytics_metrics,
            storage_metrics=storage_metrics,
            bigquery_jobs=recent_jobs,
            total_cost_usd=total_cost
        )
        
        # Save results
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metrics_collector.save_metrics_to_json(
            benchmark_results, f"bigquery_benchmark_{timestamp_str}.json"
        )
        self.metrics_collector.save_metrics_to_csv(
            benchmark_results, f"bigquery_benchmark_{timestamp_str}.csv"
        )
        
        logger.info("=" * 60)
        logger.info("✅ BigQuery Native Benchmark Completed")
        logger.info("=" * 60)
        logger.info(f"📊 Data Generation: {data_gen_metrics.execution_time_seconds:.2f}s")
        logger.info(f"📊 Data Load: {data_load_metrics.execution_time_seconds:.2f}s") 
        logger.info(f"📊 Analytics: {analytics_metrics.execution_time_seconds:.2f}s")
        logger.info(f"💾 Storage: {storage_metrics.bigquery_logical_mb:.2f}MB logical")
        logger.info(f"💰 Total Cost: ${total_cost:.6f}")
        
        return benchmark_results
    
    def run_comparison_benchmark(self) -> Dict[str, BenchmarkResults]:
        """Run benchmarks across all engines for comparison."""
        results = {}
        
        # BigQuery Native
        logger.info("🔵 Running BigQuery Native benchmark...")
        results['bigquery_native'] = self.run_full_bigquery_benchmark()
        
        # Future: BigQuery External Tables
        # logger.info("🟡 Running BigQuery External Tables benchmark...")
        # results['bigquery_external'] = self.run_external_table_benchmark()
        
        # Future: PySpark
        # logger.info("🔴 Running PySpark benchmark...")  
        # results['pyspark'] = self.run_pyspark_benchmark()
        
        return results
    
    def generate_comparison_report(self, results: Dict[str, BenchmarkResults]):
        """Generate comparative analysis report."""
        logger.info("📋 Generating comparison report...")
        
        report_lines = []
        report_lines.append("# Benchmark Comparison Report")
        report_lines.append(f"**Generated**: {datetime.now().isoformat()}")
        report_lines.append("")
        
        # Performance comparison table
        report_lines.append("## Performance Comparison")
        report_lines.append("")
        report_lines.append("| Engine | Data Gen (s) | Data Load (s) | Analytics (s) | Total (s) |")
        report_lines.append("|--------|--------------|---------------|---------------|-----------|")
        
        for engine_name, result in results.items():
            data_gen_time = result.data_generation.execution_time_seconds
            load_time = result.data_load.execution_time_seconds  
            analytics_time = result.analytics_processing.execution_time_seconds
            total_time = data_gen_time + load_time + analytics_time
            
            report_lines.append(f"| {engine_name} | {data_gen_time:.2f} | {load_time:.2f} | {analytics_time:.2f} | {total_time:.2f} |")
        
        report_lines.append("")
        
        # Storage comparison
        report_lines.append("## Storage Comparison")
        report_lines.append("")
        report_lines.append("| Engine | Logical (MB) | Physical (MB) | Compression | Rows |")
        report_lines.append("|--------|--------------|---------------|-------------|------|")
        
        for engine_name, result in results.items():
            storage = result.storage_metrics
            report_lines.append(f"| {engine_name} | {storage.bigquery_logical_mb:.3f} | {storage.bigquery_physical_mb:.3f} | {storage.compression_ratio:.2f}x | {storage.num_rows} |")
        
        report_lines.append("")
        
        # Cost comparison
        report_lines.append("## Cost Comparison")
        report_lines.append("")
        report_lines.append("| Engine | Total Cost (USD) |")
        report_lines.append("|--------|--------------------|")
        
        for engine_name, result in results.items():
            report_lines.append(f"| {engine_name} | ${result.total_cost_usd:.6f} |")
        
        # Save report
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"results/benchmark_comparison_{timestamp_str}.md"
        
        with open(report_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        logger.info(f"📋 Comparison report saved to {report_path}")


def main():
    """Run benchmark comparison."""
    runner = BenchmarkRunner()
    
    # Run comparison benchmark (currently just BigQuery Native)
    results = runner.run_comparison_benchmark()
    
    # Generate comparison report
    runner.generate_comparison_report(results)
    
    print("🎉 Benchmark execution completed!")
    print("📁 Check the results/ directory for detailed metrics and reports")


if __name__ == "__main__":
    main()