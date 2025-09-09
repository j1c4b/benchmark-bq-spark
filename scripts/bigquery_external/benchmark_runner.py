#!/usr/bin/env python3
"""
BigQuery Native vs External Table Benchmark Runner
==================================================
Executes identical analytical queries against both native and external tables
and compares performance metrics, costs, and results.

Usage:
    python benchmark_runner.py [--iterations 3] [--output results/comparison.json]
"""

import time
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    """Query execution result with performance metrics."""
    query_name: str
    table_type: str  # 'native' or 'external'
    execution_time: float
    records_returned: int
    bytes_processed: int
    bytes_billed: int
    slot_ms: int
    success: bool
    error_message: str = ""

@dataclass
class BenchmarkComparison:
    """Complete benchmark comparison results."""
    timestamp: str
    native_results: List[QueryResult]
    external_results: List[QueryResult]
    performance_summary: Dict[str, Any]
    cost_analysis: Dict[str, Any]

class BigQueryBenchmarkRunner:
    """Runs performance benchmarks between native and external BigQuery tables."""
    
    def __init__(self):
        self.queries = {
            "Query_1_Original": self._get_query_1(),
            "Query_2_Year_Filtered": self._get_query_2(), 
            "Query_3_Multi_Filtered": self._get_query_3()
        }
        
        # Table references
        self.native_table = "benchmark-bq-spark.healthcare_benchmark.stg_healthcare_hospital_data"
        self.external_table = "benchmark-bq-spark.healthcare_benchmark.ext_healthcare_hospital_data"
    
    def _get_query_1(self) -> Tuple[str, str]:
        """Original analytics query for both tables."""
        native_query = """
        WITH yearly_summary AS (
          SELECT
            provider_id,
            EXTRACT(YEAR FROM report_period) AS report_year,
            SUM(total_expenses) AS total_expenses,
            AVG(total_charges) AS avg_charges,
            SUM(net_income) AS total_net_income
          FROM
            `{table_name}`
          WHERE
            beds_number > 50
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
        LIMIT 100
        """
        
        external_query = native_query.replace("beds_number > 50", "beds > 50").replace("report_period", "reporting_period_end")
        
        return native_query, external_query
    
    def _get_query_2(self) -> Tuple[str, str]:
        """Year-filtered query for both tables."""
        native_query = """
        WITH yearly_summary AS (
          SELECT
            provider_id,
            EXTRACT(YEAR FROM report_period) AS report_year,
            SUM(total_expenses) AS total_expenses,
            AVG(total_charges) AS avg_charges,
            SUM(net_income) AS total_net_income
          FROM
            `{table_name}`
          WHERE
            beds_number > 50
            AND EXTRACT(YEAR FROM report_period) = 2023
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
        LIMIT 100
        """
        
        external_query = native_query.replace("beds_number > 50", "beds > 50").replace("report_period", "reporting_period_end")
        
        return native_query, external_query
    
    def _get_query_3(self) -> Tuple[str, str]:
        """Multi-filtered query for both tables."""
        native_query = """
        WITH yearly_summary AS (
          SELECT
            provider_id,
            EXTRACT(YEAR FROM report_period) AS report_year,
            SUM(total_expenses) AS total_expenses,
            AVG(total_charges) AS avg_charges,
            SUM(net_income) AS total_net_income
          FROM
            `{table_name}`
          WHERE
            beds_number > 50
            AND EXTRACT(YEAR FROM report_period) = 2023
            AND provider_id >= 100020 AND provider_id <= 100040
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
        LIMIT 100
        """
        
        external_query = native_query.replace("beds_number > 50", "beds > 50").replace("report_period", "reporting_period_end")
        
        return native_query, external_query
    
    def execute_query(self, query: str, table_name: str, query_name: str, table_type: str) -> QueryResult:
        """Execute a single query and capture performance metrics."""
        formatted_query = query.format(table_name=table_name)
        
        logger.info(f"Executing {query_name} on {table_type} table...")
        
        start_time = time.time()
        
        try:
            # Execute query using bq command line tool
            cmd = [
                'bq', 'query',
                '--use_legacy_sql=false',
                '--format=json',
                '--max_rows=100',
                formatted_query
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                # Parse results
                query_output = json.loads(result.stdout)
                records_returned = len(query_output) if query_output else 0
                
                # Get job metrics (simplified - would need BigQuery API for full metrics)
                bytes_processed = 0  # Would need job ID to get this
                bytes_billed = 0     # Would need job ID to get this
                slot_ms = 0          # Would need job ID to get this
                
                return QueryResult(
                    query_name=query_name,
                    table_type=table_type,
                    execution_time=execution_time,
                    records_returned=records_returned,
                    bytes_processed=bytes_processed,
                    bytes_billed=bytes_billed,
                    slot_ms=slot_ms,
                    success=True
                )
            else:
                logger.error(f"Query failed: {result.stderr}")
                return QueryResult(
                    query_name=query_name,
                    table_type=table_type,
                    execution_time=execution_time,
                    records_returned=0,
                    bytes_processed=0,
                    bytes_billed=0,
                    slot_ms=0,
                    success=False,
                    error_message=result.stderr
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query execution failed: {str(e)}")
            return QueryResult(
                query_name=query_name,
                table_type=table_type,
                execution_time=execution_time,
                records_returned=0,
                bytes_processed=0,
                bytes_billed=0,
                slot_ms=0,
                success=False,
                error_message=str(e)
            )
    
    def run_benchmark(self, iterations: int = 1) -> BenchmarkComparison:
        """Run complete benchmark comparison."""
        logger.info(f"Starting benchmark with {iterations} iteration(s)")
        
        native_results = []
        external_results = []
        
        for iteration in range(iterations):
            logger.info(f"Iteration {iteration + 1}/{iterations}")
            
            for query_name, (native_query, external_query) in self.queries.items():
                # Execute on native table
                native_result = self.execute_query(
                    native_query, self.native_table, query_name, "native"
                )
                native_results.append(native_result)
                
                # Small delay between queries
                time.sleep(1)
                
                # Execute on external table
                external_result = self.execute_query(
                    external_query, self.external_table, query_name, "external" 
                )
                external_results.append(external_result)
                
                # Delay between query types
                time.sleep(1)
        
        # Calculate performance summary
        performance_summary = self._calculate_performance_summary(native_results, external_results)
        cost_analysis = self._calculate_cost_analysis(native_results, external_results)
        
        return BenchmarkComparison(
            timestamp=datetime.now().isoformat(),
            native_results=native_results,
            external_results=external_results,
            performance_summary=performance_summary,
            cost_analysis=cost_analysis
        )
    
    def _calculate_performance_summary(self, native_results: List[QueryResult], 
                                     external_results: List[QueryResult]) -> Dict[str, Any]:
        """Calculate performance comparison summary."""
        summary = {}
        
        # Group results by query name
        native_by_query = {}
        external_by_query = {}
        
        for result in native_results:
            if result.success:
                if result.query_name not in native_by_query:
                    native_by_query[result.query_name] = []
                native_by_query[result.query_name].append(result)
        
        for result in external_results:
            if result.success:
                if result.query_name not in external_by_query:
                    external_by_query[result.query_name] = []
                external_by_query[result.query_name].append(result)
        
        # Calculate averages for each query
        for query_name in native_by_query.keys():
            if query_name in external_by_query:
                native_avg_time = sum(r.execution_time for r in native_by_query[query_name]) / len(native_by_query[query_name])
                external_avg_time = sum(r.execution_time for r in external_by_query[query_name]) / len(external_by_query[query_name])
                
                performance_diff = ((external_avg_time - native_avg_time) / native_avg_time) * 100
                
                summary[query_name] = {
                    "native_avg_time": round(native_avg_time, 3),
                    "external_avg_time": round(external_avg_time, 3),
                    "performance_difference_pct": round(performance_diff, 1),
                    "external_slower": external_avg_time > native_avg_time
                }
        
        return summary
    
    def _calculate_cost_analysis(self, native_results: List[QueryResult], 
                               external_results: List[QueryResult]) -> Dict[str, Any]:
        """Calculate cost comparison (simplified)."""
        return {
            "note": "Cost analysis requires BigQuery job metrics API integration",
            "native_table_approach": {
                "benefits": ["Partitioning reduces scan cost", "Clustering optimizes queries"],
                "costs": ["Storage costs", "Processing costs"]
            },
            "external_table_approach": {
                "benefits": ["Lower storage costs", "Pay-per-scan model"],
                "costs": ["Network egress", "No optimization benefits"]
            }
        }
    
    def save_results(self, comparison: BenchmarkComparison, output_file: str):
        """Save benchmark results to file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(asdict(comparison), f, indent=2)
        
        logger.info(f"Results saved to {output_file}")
    
    def print_summary(self, comparison: BenchmarkComparison):
        """Print benchmark summary to console."""
        print("\n" + "="*80)
        print("🚀 BigQuery Native vs External Table Benchmark Results")
        print("="*80)
        
        print(f"\n📊 Performance Summary:")
        for query_name, metrics in comparison.performance_summary.items():
            native_time = metrics["native_avg_time"]
            external_time = metrics["external_avg_time"]
            diff_pct = metrics["performance_difference_pct"]
            
            status = "🔴" if diff_pct > 10 else "🟡" if diff_pct > 0 else "🟢"
            print(f"  {status} {query_name}:")
            print(f"    Native: {native_time}s | External: {external_time}s | Diff: {diff_pct:+.1f}%")
        
        print(f"\n📈 Key Findings:")
        native_count = len([r for r in comparison.native_results if r.success])
        external_count = len([r for r in comparison.external_results if r.success])
        print(f"  ✅ Native table queries: {native_count} successful")
        print(f"  ✅ External table queries: {external_count} successful")
        
        # Calculate overall performance difference
        all_native_times = [r.execution_time for r in comparison.native_results if r.success]
        all_external_times = [r.execution_time for r in comparison.external_results if r.success]
        
        if all_native_times and all_external_times:
            avg_native = sum(all_native_times) / len(all_native_times)
            avg_external = sum(all_external_times) / len(all_external_times)
            overall_diff = ((avg_external - avg_native) / avg_native) * 100
            
            print(f"  📊 Overall performance difference: {overall_diff:+.1f}%")
            if overall_diff > 0:
                print(f"  💡 External tables are {overall_diff:.1f}% slower on average")
            else:
                print(f"  💡 External tables are {abs(overall_diff):.1f}% faster on average")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="BigQuery Native vs External Table Benchmark")
    parser.add_argument("--iterations", type=int, default=1, help="Number of benchmark iterations")
    parser.add_argument("--output", default="results/native_vs_external_comparison.json", help="Output file path")
    
    args = parser.parse_args()
    
    runner = BigQueryBenchmarkRunner()
    
    try:
        comparison = runner.run_benchmark(iterations=args.iterations)
        runner.print_summary(comparison)
        runner.save_results(comparison, args.output)
        
    except Exception as e:
        logger.error(f"Benchmark failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())