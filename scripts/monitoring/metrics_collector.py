#!/usr/bin/env python3
"""
Comprehensive Metrics Collection System

Captures performance, storage, and cost metrics for benchmarking
BigQuery Native vs External Tables vs PySpark implementations.
"""

import os
import sys
import time
import json
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import psutil

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import gcp_config
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound
from .gcp_pricing import GCPPricingCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance timing and resource utilization metrics."""
    execution_time_seconds: float
    cpu_percent_avg: float
    cpu_percent_max: float
    memory_mb_avg: float
    memory_mb_max: float
    memory_mb_peak: float
    start_time: str
    end_time: str


@dataclass
class StorageMetrics:
    """Storage size and efficiency metrics."""
    raw_csv_bytes: int
    raw_csv_mb: float
    bigquery_logical_bytes: int
    bigquery_physical_bytes: int
    bigquery_logical_mb: float
    bigquery_physical_mb: float
    compression_ratio: float
    num_rows: int
    num_partitions: int


@dataclass
class BigQueryJobMetrics:
    """BigQuery job execution metrics."""
    job_id: str
    job_type: str
    state: str
    creation_time: str
    start_time: str
    end_time: str
    total_slot_ms: int
    total_bytes_processed: int
    total_bytes_billed: int
    query_cost_usd: float
    num_dml_affected_rows: int


@dataclass
class CostMetrics:
    """Detailed cost breakdown for all GCP services."""
    total_cost_usd: float
    cloud_storage_cost_usd: float
    bigquery_processing_cost_usd: float
    bigquery_storage_cost_usd: float
    compute_cost_usd: float
    network_cost_usd: float
    cost_breakdown: Dict[str, Any]
    pricing_region: str
    pricing_timestamp: str


@dataclass
class BenchmarkResults:
    """Complete benchmark results for one engine."""
    engine_name: str
    test_timestamp: str
    data_generation: PerformanceMetrics
    data_load: PerformanceMetrics
    storage_metrics: StorageMetrics
    bigquery_jobs: List[BigQueryJobMetrics]
    cost_metrics: CostMetrics
    total_cost_usd: float


class MetricsCollector:
    """Comprehensive metrics collection system."""
    
    def __init__(self, region: str = "us-central1"):
        self.config = gcp_config
        self.bigquery_client = self.config.get_bigquery_client()
        self.storage_client = self.config.get_storage_client()
        self.pricing_calculator = GCPPricingCalculator(region)
        self.results_dir = "results"
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Resource monitoring
        self.process = psutil.Process()
        self.monitoring_active = False
        self.cpu_samples = []
        self.memory_samples = []
    
    def start_monitoring(self):
        """Start system resource monitoring."""
        self.monitoring_active = True
        self.cpu_samples = []
        self.memory_samples = []
        self._collect_resource_sample()
    
    def stop_monitoring(self) -> PerformanceMetrics:
        """Stop monitoring and return performance metrics."""
        self.monitoring_active = False
        self._collect_resource_sample()  # Final sample
        
        if not self.cpu_samples:
            return None
        
        return PerformanceMetrics(
            execution_time_seconds=0,  # Set by caller
            cpu_percent_avg=sum(self.cpu_samples) / len(self.cpu_samples),
            cpu_percent_max=max(self.cpu_samples),
            memory_mb_avg=sum(self.memory_samples) / len(self.memory_samples),
            memory_mb_max=max(self.memory_samples),
            memory_mb_peak=max(self.memory_samples),
            start_time="",  # Set by caller
            end_time=""     # Set by caller
        )
    
    def _collect_resource_sample(self):
        """Collect a single resource utilization sample."""
        try:
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            self.cpu_samples.append(cpu_percent)
            self.memory_samples.append(memory_mb)
        except Exception as e:
            logger.warning(f"Failed to collect resource sample: {e}")
    
    def measure_execution_time(self, func, *args, **kwargs):
        """Measure execution time and system resources for a function."""
        start_time = time.time()
        start_datetime = datetime.now().isoformat()
        
        self.start_monitoring()
        
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            logger.error(f"Function execution failed: {e}")
            result = None
            success = False
        
        end_time = time.time()
        end_datetime = datetime.now().isoformat()
        execution_time = end_time - start_time
        
        perf_metrics = self.stop_monitoring()
        if perf_metrics:
            perf_metrics.execution_time_seconds = execution_time
            perf_metrics.start_time = start_datetime
            perf_metrics.end_time = end_datetime
        
        return result, perf_metrics, success
    
    def get_gcs_file_metrics(self, bucket_name: str, blob_name: str) -> Dict[str, Any]:
        """Get GCS file storage metrics."""
        try:
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if not blob.exists():
                raise NotFound(f"GCS file not found: gs://{bucket_name}/{blob_name}")
            
            blob.reload()  # Get latest metadata
            
            return {
                "size_bytes": blob.size,
                "size_mb": blob.size / 1024 / 1024,
                "content_type": blob.content_type,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "etag": blob.etag
            }
        except Exception as e:
            logger.error(f"Failed to get GCS metrics: {e}")
            return {}
    
    def get_bigquery_table_metrics(self, dataset_id: str, table_id: str) -> StorageMetrics:
        """Get comprehensive BigQuery table storage metrics."""
        try:
            table_ref = self.bigquery_client.dataset(dataset_id).table(table_id)
            table = self.bigquery_client.get_table(table_ref)
            
            # Calculate compression ratio
            logical_bytes = int(table.num_bytes) if table.num_bytes else 0
            # Use _properties to access internal fields
            physical_bytes = 0
            if hasattr(table, '_properties') and table._properties:
                physical_bytes = int(table._properties.get('numTotalPhysicalBytes', 0))
            
            compression_ratio = physical_bytes / logical_bytes if logical_bytes > 0 else 0
            
            # Count partitions if table is partitioned
            num_partitions = 0
            if table.time_partitioning:
                try:
                    # Query to count partitions
                    query = f"""
                    SELECT COUNT(*) as partition_count
                    FROM `{self.config.project_id}.{dataset_id}.INFORMATION_SCHEMA.PARTITIONS`
                    WHERE table_name = '{table_id}'
                    """
                    query_job = self.bigquery_client.query(query)
                    results = list(query_job)
                    num_partitions = results[0].partition_count if results else 0
                except Exception as e:
                    logger.warning(f"Could not count partitions: {e}")
            
            return StorageMetrics(
                raw_csv_bytes=0,  # Set separately
                raw_csv_mb=0,     # Set separately  
                bigquery_logical_bytes=logical_bytes,
                bigquery_physical_bytes=physical_bytes,
                bigquery_logical_mb=logical_bytes / 1024 / 1024,
                bigquery_physical_mb=physical_bytes / 1024 / 1024,
                compression_ratio=compression_ratio,
                num_rows=int(table.num_rows) if table.num_rows else 0,
                num_partitions=num_partitions
            )
            
        except Exception as e:
            logger.error(f"Failed to get BigQuery table metrics: {e}")
            return None
    
    def get_recent_bigquery_jobs(self, max_results: int = 10) -> List[BigQueryJobMetrics]:
        """Get recent BigQuery job metrics."""
        job_metrics = []
        
        try:
            jobs = self.bigquery_client.list_jobs(
                project=self.config.project_id,
                max_results=max_results
            )
            
            for job in jobs:
                # Get detailed job info
                job_details = self.bigquery_client.get_job(job.job_id, location=job.location)
                
                # Calculate cost (rough estimate: $5 per TB processed)
                bytes_processed = 0
                bytes_billed = 0
                slot_ms = 0
                
                if hasattr(job_details, 'query') and job_details.query:
                    stats = job_details.query
                    if hasattr(stats, 'total_bytes_processed'):
                        bytes_processed = int(stats.total_bytes_processed or 0)
                    if hasattr(stats, 'total_bytes_billed'):
                        bytes_billed = int(stats.total_bytes_billed or 0)
                    if hasattr(stats, 'slot_millis'):
                        slot_ms = int(stats.slot_millis or 0)
                
                # Cost calculation: $5 per TB for on-demand queries
                query_cost = (bytes_billed / (1024**4)) * 5.0  # TB to USD
                
                # Get DML affected rows for load jobs
                dml_rows = 0
                if hasattr(job_details, 'query') and job_details.query:
                    if hasattr(job_details.query, 'num_dml_affected_rows'):
                        dml_rows = int(job_details.query.num_dml_affected_rows or 0)
                
                job_metrics.append(BigQueryJobMetrics(
                    job_id=job.job_id,
                    job_type=job.job_type,
                    state=job.state,
                    creation_time=job.created.isoformat(),
                    start_time=job.started.isoformat() if job.started else "",
                    end_time=job.ended.isoformat() if job.ended else "",
                    total_slot_ms=slot_ms,
                    total_bytes_processed=bytes_processed,
                    total_bytes_billed=bytes_billed,
                    query_cost_usd=query_cost,
                    num_dml_affected_rows=dml_rows
                ))
                
        except Exception as e:
            logger.error(f"Failed to get BigQuery job metrics: {e}")
        
        return job_metrics
    
    def calculate_comprehensive_costs(self, 
                                    performance_metrics: PerformanceMetrics,
                                    storage_metrics: StorageMetrics,
                                    bigquery_jobs: List[BigQueryJobMetrics]) -> CostMetrics:
        """Calculate comprehensive costs using real-time GCP pricing."""
        logger.info("Calculating comprehensive costs with real-time pricing...")
        
        # Update pricing rates
        self.pricing_calculator.update_pricing_from_api()
        
        # Calculate total bytes processed from BigQuery jobs
        total_bytes_processed = sum(job.total_bytes_processed for job in bigquery_jobs)
        total_slot_ms = sum(job.total_slot_ms for job in bigquery_jobs)
        
        # Calculate comprehensive pipeline cost
        pipeline_costs = self.pricing_calculator.calculate_comprehensive_pipeline_cost(
            execution_time_seconds=performance_metrics.execution_time_seconds,
            memory_mb_peak=performance_metrics.memory_mb_peak,
            csv_size_bytes=storage_metrics.raw_csv_bytes,
            bigquery_logical_bytes=storage_metrics.bigquery_logical_bytes,
            bigquery_physical_bytes=storage_metrics.bigquery_physical_bytes,
            bigquery_bytes_processed=total_bytes_processed,
            slot_milliseconds=total_slot_ms
        )
        
        # Create cost metrics object
        cost_metrics = CostMetrics(
            total_cost_usd=pipeline_costs["total_pipeline_cost_usd"],
            cloud_storage_cost_usd=pipeline_costs["cost_breakdown"]["cloud_storage_usd"],
            bigquery_processing_cost_usd=pipeline_costs["cost_breakdown"]["bigquery_processing_usd"],
            bigquery_storage_cost_usd=pipeline_costs["cost_breakdown"]["bigquery_storage_usd"],
            compute_cost_usd=pipeline_costs["cost_breakdown"]["compute_processing_usd"],
            network_cost_usd=pipeline_costs["cost_breakdown"]["network_usd"],
            cost_breakdown=pipeline_costs["detailed_costs"],
            pricing_region=pipeline_costs["region"],
            pricing_timestamp=pipeline_costs["pricing_timestamp"]
        )
        
        return cost_metrics
    
    def save_metrics_to_json(self, metrics: BenchmarkResults, filename: str):
        """Save metrics to JSON file."""
        filepath = os.path.join(self.results_dir, filename)
        
        # Convert to dictionary for JSON serialization
        metrics_dict = asdict(metrics)
        
        with open(filepath, 'w') as f:
            json.dump(metrics_dict, f, indent=2, default=str)
        
        logger.info(f"Metrics saved to {filepath}")
    
    def save_metrics_to_csv(self, metrics: BenchmarkResults, filename: str):
        """Save metrics to CSV file."""
        filepath = os.path.join(self.results_dir, filename)
        
        # Flatten metrics into rows
        rows = []
        
        # Performance metrics
        for metric_type in ['data_generation', 'data_load']:
            perf_metrics = getattr(metrics, metric_type)
            if perf_metrics:
                rows.append({
                    'engine': metrics.engine_name,
                    'timestamp': metrics.test_timestamp,
                    'metric_type': 'performance',
                    'metric_category': metric_type,
                    'metric_name': 'execution_time_seconds',
                    'metric_value': perf_metrics.execution_time_seconds,
                    'unit': 'seconds'
                })
                rows.append({
                    'engine': metrics.engine_name,
                    'timestamp': metrics.test_timestamp,
                    'metric_type': 'performance',
                    'metric_category': metric_type,
                    'metric_name': 'memory_mb_peak',
                    'metric_value': perf_metrics.memory_mb_peak,
                    'unit': 'MB'
                })
        
        # Storage metrics
        if metrics.storage_metrics:
            storage = metrics.storage_metrics
            storage_metrics_map = {
                'raw_csv_mb': ('CSV', 'MB'),
                'bigquery_logical_mb': ('BigQuery_Logical', 'MB'), 
                'bigquery_physical_mb': ('BigQuery_Physical', 'MB'),
                'compression_ratio': ('Compression_Ratio', 'ratio'),
                'num_rows': ('Row_Count', 'count'),
                'num_partitions': ('Partition_Count', 'count')
            }
            
            for field, (name, unit) in storage_metrics_map.items():
                value = getattr(storage, field)
                rows.append({
                    'engine': metrics.engine_name,
                    'timestamp': metrics.test_timestamp,
                    'metric_type': 'storage',
                    'metric_category': 'table_metrics',
                    'metric_name': name,
                    'metric_value': value,
                    'unit': unit
                })
        
        # Cost metrics - detailed breakdown
        cost_breakdown_metrics = {
            'total_cost_usd': ('Total_Pipeline_Cost', 'USD'),
            'cloud_storage_cost_usd': ('Cloud_Storage_Cost', 'USD'),
            'bigquery_processing_cost_usd': ('BigQuery_Processing_Cost', 'USD'),
            'bigquery_storage_cost_usd': ('BigQuery_Storage_Cost', 'USD'),
            'compute_cost_usd': ('Compute_Processing_Cost', 'USD'),
            'network_cost_usd': ('Network_Cost', 'USD')
        }
        
        for field, (name, unit) in cost_breakdown_metrics.items():
            value = getattr(metrics.cost_metrics, field)
            rows.append({
                'engine': metrics.engine_name,
                'timestamp': metrics.test_timestamp,
                'metric_type': 'cost',
                'metric_category': 'cost_breakdown',
                'metric_name': name,
                'metric_value': value,
                'unit': unit
            })
        
        # Add pricing metadata
        rows.append({
            'engine': metrics.engine_name,
            'timestamp': metrics.test_timestamp,
            'metric_type': 'metadata',
            'metric_category': 'pricing',
            'metric_name': 'pricing_region',
            'metric_value': metrics.cost_metrics.pricing_region,
            'unit': 'region'
        })
        
        rows.append({
            'engine': metrics.engine_name,
            'timestamp': metrics.test_timestamp,
            'metric_type': 'metadata',
            'metric_category': 'pricing',
            'metric_name': 'pricing_timestamp',
            'metric_value': metrics.cost_metrics.pricing_timestamp,
            'unit': 'timestamp'
        })
        
        # Save to CSV
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)
        
        logger.info(f"CSV metrics saved to {filepath}")
    
    def collect_end_to_end_metrics(self, engine_name: str = "BigQuery_Native") -> BenchmarkResults:
        """Collect comprehensive end-to-end metrics for current state."""
        timestamp = datetime.now().isoformat()
        
        logger.info(f"Collecting end-to-end metrics for {engine_name}")
        
        # Get storage metrics for staging table
        staging_metrics = self.get_bigquery_table_metrics('healthcare_benchmark', 'stg_healthcare_hospital_data')
        
        # Get GCS file metrics
        gcs_metrics = self.get_gcs_file_metrics(
            self.config.bucket_name,
            'raw/hospital_cost_sample_100rows_20250909_092637.csv'
        )
        
        # Update storage metrics with GCS data
        if staging_metrics and gcs_metrics:
            staging_metrics.raw_csv_bytes = gcs_metrics.get('size_bytes', 0)
            staging_metrics.raw_csv_mb = gcs_metrics.get('size_mb', 0)
        
        # Get recent BigQuery jobs
        recent_jobs = self.get_recent_bigquery_jobs(10)
        
        # Create placeholder performance metrics (would be populated during actual runs)
        placeholder_perf = PerformanceMetrics(
            execution_time_seconds=0,
            cpu_percent_avg=0,
            cpu_percent_max=0, 
            memory_mb_avg=0,
            memory_mb_max=0,
            memory_mb_peak=100,  # Reasonable default for cost calculations
            start_time=timestamp,
            end_time=timestamp
        )
        
        # Calculate comprehensive costs
        cost_metrics = self.calculate_comprehensive_costs(
            placeholder_perf, staging_metrics, recent_jobs
        )
        
        return BenchmarkResults(
            engine_name=engine_name,
            test_timestamp=timestamp,
            data_generation=placeholder_perf,
            data_load=placeholder_perf,
            storage_metrics=staging_metrics,
            bigquery_jobs=recent_jobs[:5],  # Keep top 5 most recent
            cost_metrics=cost_metrics,
            total_cost_usd=cost_metrics.total_cost_usd
        )


def main():
    """Example usage of metrics collection."""
    collector = MetricsCollector()
    
    # Collect current state metrics
    metrics = collector.collect_end_to_end_metrics("BigQuery_Native_Current_State")
    
    # Save metrics
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    collector.save_metrics_to_json(metrics, f"bigquery_metrics_{timestamp_str}.json")
    collector.save_metrics_to_csv(metrics, f"bigquery_metrics_{timestamp_str}.csv")
    
    print(f"✅ Metrics collected and saved for {metrics.engine_name}")
    print(f"📊 Total cost: ${metrics.total_cost_usd:.6f}")
    print(f"💾 Storage: {metrics.storage_metrics.bigquery_logical_mb:.2f}MB logical, {metrics.storage_metrics.bigquery_physical_mb:.2f}MB physical")
    print(f"📁 Rows: {metrics.storage_metrics.num_rows:,} records")


if __name__ == "__main__":
    main()