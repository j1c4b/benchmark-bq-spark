#!/usr/bin/env python3
"""
Complete CSV-to-Analytics Pipeline Runner

Takes a CSV file input and executes the complete benchmark pipeline:
1. Upload CSV to GCS
2. Load to BigQuery staging table
3. Process analytics with window functions
4. Generate comprehensive data summaries
5. Capture all performance metrics
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import gcp_config
from monitoring.metrics_collector import MetricsCollector, BenchmarkResults
from monitoring.performance_decorators import measure_performance
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CSVPipelineRunner:
    """Complete CSV-to-analytics pipeline with comprehensive reporting."""
    
    def __init__(self):
        self.config = gcp_config
        self.bigquery_client = self.config.get_bigquery_client()
        self.storage_client = self.config.get_storage_client()
        self.metrics_collector = MetricsCollector()
        
        # Pipeline configuration
        self.dataset_id = "healthcare_benchmark"
        self.staging_table = "stg_healthcare_hospital_data"
        
        self.results = {}
        
    @measure_performance("CSV Upload to GCS")
    def upload_csv_to_gcs(self, csv_file_path: str) -> str:
        """Upload CSV file to GCS bucket."""
        logger.info(f"📤 Uploading CSV file: {csv_file_path}")
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Path(csv_file_path).stem
        gcs_path = f"raw/{filename}_{timestamp}.csv"
        
        # Upload to GCS
        bucket = self.storage_client.bucket(self.config.bucket_name)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(csv_file_path)
        
        gcs_uri = f"gs://{self.config.bucket_name}/{gcs_path}"
        logger.info(f"✅ CSV uploaded to: {gcs_uri}")
        
        return gcs_uri
    
    @measure_performance("BigQuery Table Creation")
    def create_staging_table(self) -> bool:
        """Create optimized BigQuery staging table."""
        logger.info("🏗️ Creating BigQuery staging table...")
        
        # Define schema
        schema = [
            bigquery.SchemaField("provider_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("hospital_name", "STRING"),
            bigquery.SchemaField("city", "STRING"),
            bigquery.SchemaField("state", "STRING"),
            bigquery.SchemaField("beds_number", "INTEGER"),
            bigquery.SchemaField("report_period", "DATE"),
            bigquery.SchemaField("total_expenses", "FLOAT"),
            bigquery.SchemaField("total_charges", "FLOAT"),
            bigquery.SchemaField("net_income", "FLOAT"),
            bigquery.SchemaField("patient_days", "INTEGER"),
            bigquery.SchemaField("discharges", "INTEGER"),
            bigquery.SchemaField("fte_employees", "INTEGER"),
            bigquery.SchemaField("medicare_days", "INTEGER"),
            bigquery.SchemaField("medicaid_days", "INTEGER")
        ]
        
        # Table configuration
        table_ref = self.bigquery_client.dataset(self.dataset_id).table(self.staging_table)
        table = bigquery.Table(table_ref, schema=schema)
        
        # Set partitioning and clustering
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="report_period"
        )
        table.clustering_fields = ["provider_id"]
        table.description = "Staging table for hospital cost report data with optimized partitioning and clustering"
        
        # Create or replace table
        try:
            self.bigquery_client.delete_table(table_ref, not_found_ok=True)
            table = self.bigquery_client.create_table(table)
            logger.info(f"✅ Staging table created: {table.full_table_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create staging table: {e}")
            return False
    
    @measure_performance("Data Load to BigQuery")
    def load_csv_to_staging(self, gcs_uri: str) -> bool:
        """Load CSV data from GCS to BigQuery staging table."""
        logger.info(f"📊 Loading data from {gcs_uri}")
        
        # Configure load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=False,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        
        # Start load job
        table_ref = self.bigquery_client.dataset(self.dataset_id).table(self.staging_table)
        load_job = self.bigquery_client.load_table_from_uri(
            gcs_uri, table_ref, job_config=job_config
        )
        
        # Wait for completion
        load_job.result()
        
        if load_job.state == "DONE":
            logger.info(f"✅ Data loaded successfully: {load_job.output_rows} rows")
            return True
        else:
            logger.error(f"❌ Load job failed: {load_job.errors}")
            return False
    
    
    def get_staging_summary(self) -> Dict[str, Any]:
        """Generate comprehensive staging table summary."""
        logger.info("📋 Generating staging table summary...")
        
        queries = {
            "total_records": f"SELECT COUNT(*) as count FROM `{self.config.project_id}.{self.dataset_id}.{self.staging_table}`",
            
            "year_distribution": f"""
                SELECT 
                    EXTRACT(YEAR FROM report_period) as year,
                    COUNT(*) as hospitals,
                    AVG(beds_number) as avg_beds,
                    SUM(total_expenses) as total_expenses,
                    AVG(total_expenses) as avg_expenses
                FROM `{self.config.project_id}.{self.dataset_id}.{self.staging_table}`
                GROUP BY year
                ORDER BY year
            """,
            
            "state_distribution": f"""
                SELECT 
                    state,
                    COUNT(*) as hospitals,
                    AVG(beds_number) as avg_beds,
                    AVG(total_expenses) as avg_expenses
                FROM `{self.config.project_id}.{self.dataset_id}.{self.staging_table}`
                GROUP BY state
                ORDER BY hospitals DESC
                LIMIT 10
            """,
            
            "bed_size_categories": f"""
                SELECT 
                    CASE 
                        WHEN beds_number < 50 THEN 'Small (<50)'
                        WHEN beds_number < 100 THEN 'Medium (50-99)'
                        WHEN beds_number < 200 THEN 'Large (100-199)'
                        ELSE 'Very Large (200+)'
                    END as size_category,
                    COUNT(*) as hospitals,
                    AVG(total_expenses) as avg_expenses,
                    AVG(net_income) as avg_net_income
                FROM `{self.config.project_id}.{self.dataset_id}.{self.staging_table}`
                GROUP BY size_category
                ORDER BY 
                    CASE size_category
                        WHEN 'Small (<50)' THEN 1
                        WHEN 'Medium (50-99)' THEN 2
                        WHEN 'Large (100-199)' THEN 3
                        ELSE 4
                    END
            """,
            
            "financial_summary": f"""
                SELECT 
                    MIN(total_expenses) as min_expenses,
                    MAX(total_expenses) as max_expenses,
                    AVG(total_expenses) as avg_expenses,
                    STDDEV(total_expenses) as stddev_expenses,
                    MIN(net_income) as min_net_income,
                    MAX(net_income) as max_net_income,
                    AVG(net_income) as avg_net_income,
                    COUNT(CASE WHEN net_income < 0 THEN 1 END) as loss_making_hospitals
                FROM `{self.config.project_id}.{self.dataset_id}.{self.staging_table}`
            """
        }
        
        summary = {}
        for name, query in queries.items():
            try:
                query_job = self.bigquery_client.query(query)
                results = [dict(row) for row in query_job]
                summary[name] = results
            except Exception as e:
                logger.error(f"Failed to execute {name} query: {e}")
                summary[name] = []
        
        return summary
    
    
    def generate_summary_report(self, staging_summary: Dict, performance_metrics: Dict) -> str:
        """Generate comprehensive summary report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report_lines = [
            "# Complete Pipeline Execution Summary",
            f"**Generated**: {timestamp}",
            f"**Pipeline**: CSV → GCS → BigQuery Staging",
            "",
            "## 🚀 Performance Metrics",
            ""
        ]
        
        # Performance summary
        for phase, metrics in performance_metrics.items():
            if metrics and hasattr(metrics, 'execution_time_seconds'):
                report_lines.extend([
                    f"### {phase}",
                    f"- **Duration**: {metrics.execution_time_seconds:.2f} seconds",
                    f"- **CPU Usage**: {metrics.cpu_percent_avg:.1f}% average, {metrics.cpu_percent_max:.1f}% peak",
                    f"- **Memory**: {metrics.memory_mb_peak:.1f}MB peak",
                    ""
                ])
        
        # Staging table summary
        report_lines.extend([
            "## 📊 Staging Table Summary",
            ""
        ])
        
        if staging_summary.get("total_records"):
            total_count = staging_summary["total_records"][0]["count"]
            report_lines.append(f"**Total Records**: {total_count:,}")
        
        if staging_summary.get("year_distribution"):
            report_lines.extend([
                "",
                "### Year Distribution",
                "| Year | Hospitals | Avg Beds | Total Expenses | Avg Expenses |",
                "|------|-----------|----------|----------------|--------------|"
            ])
            for row in staging_summary["year_distribution"]:
                report_lines.append(f"| {row['year']} | {row['hospitals']} | {row['avg_beds']:.0f} | ${row['total_expenses']:,.0f} | ${row['avg_expenses']:,.0f} |")
        
        if staging_summary.get("bed_size_categories"):
            report_lines.extend([
                "",
                "### Hospital Size Categories", 
                "| Size Category | Hospitals | Avg Expenses | Avg Net Income |",
                "|---------------|-----------|--------------|----------------|"
            ])
            for row in staging_summary["bed_size_categories"]:
                report_lines.append(f"| {row['size_category']} | {row['hospitals']} | ${row['avg_expenses']:,.0f} | ${row['avg_net_income']:,.0f} |")
        
        # Staging table focus
        report_lines.extend([
            "",
            "## 📊 Pipeline Focus: Staging Table Ready",
            "",
            "The staging table is optimized and ready for:",
            "- **BigQuery Native**: Direct querying with partitioning/clustering benefits",
            "- **BigQuery External**: Link to GCS files for direct querying",
            "- **Spark Processing**: Load staging data into Spark DataFrames",
            ""
        ])
        
        return "\n".join(report_lines)
    
    def run_complete_pipeline(self, csv_file_path: str) -> Tuple[BenchmarkResults, str]:
        """Execute the complete CSV-to-analytics pipeline."""
        logger.info("=" * 80)
        logger.info("🚀 Starting Complete CSV Pipeline")
        logger.info("=" * 80)
        
        performance_metrics = {}
        
        # Step 1: Upload CSV to GCS
        gcs_uri, upload_metrics = self.upload_csv_to_gcs(csv_file_path)
        performance_metrics["CSV Upload"] = upload_metrics
        
        # Step 2: Create staging table
        _, table_creation_metrics = self.create_staging_table()
        performance_metrics["Table Creation"] = table_creation_metrics
        
        # Step 3: Load data to staging
        _, load_metrics = self.load_csv_to_staging(gcs_uri)
        performance_metrics["Data Load"] = load_metrics
        
        # Staging table is now ready for BigQuery/Spark processing
        
        # Step 4: Generate staging table summary
        logger.info("📋 Generating staging table summary...")
        staging_summary = self.get_staging_summary()
        
        # Step 6: Collect comprehensive metrics
        logger.info("📈 Collecting final metrics...")
        benchmark_results = self.metrics_collector.collect_end_to_end_metrics("CSV_Pipeline_Complete")
        
        # Update with actual performance metrics
        benchmark_results.data_generation = upload_metrics
        benchmark_results.data_load = load_metrics
        # No analytics processing - focus on staging table only
        
        # Recalculate costs with actual performance metrics
        if upload_metrics and load_metrics:
            # Combine performance metrics for total execution time
            total_execution_time = (
                upload_metrics.execution_time_seconds +
                load_metrics.execution_time_seconds
            )
            peak_memory = max(
                upload_metrics.memory_mb_peak,
                load_metrics.memory_mb_peak
            )
            
            # Create combined performance metrics for cost calculation
            combined_perf = upload_metrics
            combined_perf.execution_time_seconds = total_execution_time
            combined_perf.memory_mb_peak = peak_memory
            
            # Recalculate costs with actual metrics
            updated_costs = self.metrics_collector.calculate_comprehensive_costs(
                combined_perf, benchmark_results.storage_metrics, benchmark_results.bigquery_jobs
            )
            benchmark_results.cost_metrics = updated_costs
            benchmark_results.total_cost_usd = updated_costs.total_cost_usd
        
        # Step 5: Generate summary report
        summary_report = self.generate_summary_report(
            staging_summary, performance_metrics
        )
        
        # Save all results
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save benchmark metrics
        self.metrics_collector.save_metrics_to_json(
            benchmark_results, f"csv_pipeline_{timestamp_str}.json"
        )
        self.metrics_collector.save_metrics_to_csv(
            benchmark_results, f"csv_pipeline_{timestamp_str}.csv"
        )
        
        # Save summary report
        summary_path = f"results/pipeline_summary_{timestamp_str}.md"
        with open(summary_path, 'w') as f:
            f.write(summary_report)
        
        logger.info("=" * 80)
        logger.info("✅ Complete Pipeline Executed Successfully")
        logger.info("=" * 80)
        logger.info(f"📊 CSV Upload: {upload_metrics.execution_time_seconds:.2f}s")
        logger.info(f"📊 Data Load: {load_metrics.execution_time_seconds:.2f}s")
        logger.info(f"🎯 Staging Table: Ready for BigQuery/Spark processing")
        logger.info(f"💰 Total Cost: ${benchmark_results.cost_metrics.total_cost_usd:.6f}")
        logger.info(f"💰 Cost Breakdown:")
        logger.info(f"   - Cloud Storage: ${benchmark_results.cost_metrics.cloud_storage_cost_usd:.6f}")
        logger.info(f"   - BigQuery Processing: ${benchmark_results.cost_metrics.bigquery_processing_cost_usd:.6f}")
        logger.info(f"   - BigQuery Storage: ${benchmark_results.cost_metrics.bigquery_storage_cost_usd:.6f}")
        logger.info(f"   - Compute: ${benchmark_results.cost_metrics.compute_cost_usd:.6f}")
        logger.info(f"   - Network: ${benchmark_results.cost_metrics.network_cost_usd:.6f}")
        logger.info(f"📋 Summary Report: {summary_path}")
        
        return benchmark_results, summary_report


def main():
    """Example usage with existing CSV file."""
    runner = CSVPipelineRunner()
    
    # Use existing sample file
    csv_file = "data/raw/hospital_cost_sample_100rows_20250909_092637.csv"
    
    if not os.path.exists(csv_file):
        logger.error(f"CSV file not found: {csv_file}")
        logger.info("Please provide a valid CSV file path")
        sys.exit(1)
    
    # Run complete pipeline
    benchmark_results, summary_report = runner.run_complete_pipeline(csv_file)
    
    print("\n🎉 Pipeline execution completed!")
    print("📁 Check results/ directory for detailed metrics and summaries")
    print(f"\n📊 Total execution time: {benchmark_results.data_generation.execution_time_seconds + benchmark_results.data_load.execution_time_seconds + benchmark_results.analytics_processing.execution_time_seconds:.2f}s")


if __name__ == "__main__":
    main()