#!/usr/bin/env python3
"""
Simple CLI for CSV Pipeline Runner

Usage:
    python run_pipeline.py path/to/your/file.csv
    python run_pipeline.py --generate-sample  # Use built-in sample generation
"""

import sys
import os
import argparse
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from pipeline_runner import CSVPipelineRunner
from data_preparation.data_prepare import HospitalDataPreparer


def main():
    parser = argparse.ArgumentParser(
        description="Run complete CSV-to-Analytics pipeline with comprehensive metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py data/my_hospital_data.csv
  python run_pipeline.py --generate-sample
  python run_pipeline.py --generate-sample --rows 200
        """
    )
    
    parser.add_argument(
        'csv_file', 
        nargs='?',
        help='Path to CSV file to process'
    )
    
    parser.add_argument(
        '--generate-sample',
        action='store_true',
        help='Generate sample data instead of using existing CSV'
    )
    
    parser.add_argument(
        '--rows',
        type=int,
        default=100,
        help='Number of sample rows to generate (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Initialize pipeline runner
    runner = CSVPipelineRunner()
    
    if args.generate_sample:
        print(f"🏗️ Generating {args.rows} sample hospital records...")
        
        # Generate sample data
        preparer = HospitalDataPreparer()
        gcs_uri = preparer.prepare_sample_data(args.rows)
        
        # Get the local file path
        import re
        match = re.search(r'hospital_cost_sample_.*\.csv', gcs_uri)
        if match:
            csv_file = f"data/raw/{match.group()}"
        else:
            print("❌ Could not determine local file path")
            sys.exit(1)
            
    elif args.csv_file:
        csv_file = args.csv_file
        if not os.path.exists(csv_file):
            print(f"❌ File not found: {csv_file}")
            sys.exit(1)
    else:
        # Try to find existing sample file
        data_dir = Path("data/raw")
        if data_dir.exists():
            csv_files = list(data_dir.glob("hospital_cost_sample_*.csv"))
            if csv_files:
                csv_file = str(csv_files[-1])  # Use most recent
                print(f"📁 Using existing sample file: {csv_file}")
            else:
                print("❌ No CSV file provided and no sample files found.")
                print("Use: python run_pipeline.py --generate-sample")
                sys.exit(1)
        else:
            print("❌ No CSV file provided. Use --generate-sample or provide file path.")
            sys.exit(1)
    
    print(f"🚀 Running complete pipeline on: {csv_file}")
    print("=" * 80)
    
    # Run pipeline
    try:
        benchmark_results, summary_report = runner.run_complete_pipeline(csv_file)
        
        print("\n" + "=" * 80)
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
        # Print key results
        total_time = (
            benchmark_results.data_generation.execution_time_seconds +
            benchmark_results.data_load.execution_time_seconds
        )
        
        print(f"⏱️  Total Execution Time: {total_time:.2f} seconds")
        print(f"📊 Records Processed: {benchmark_results.storage_metrics.num_rows}")
        print(f"🏆 Staging Table: Ready for BigQuery/Spark benchmarking")
        print(f"💾 Storage Efficiency: {benchmark_results.storage_metrics.compression_ratio:.2f}x compression")
        print(f"💰 Estimated Cost: ${benchmark_results.total_cost_usd:.6f}")
        
        print(f"\n📋 Detailed reports saved in results/ directory:")
        print(f"   - Complete summary: results/pipeline_summary_*.md")
        print(f"   - JSON metrics: results/csv_pipeline_*.json") 
        print(f"   - CSV metrics: results/csv_pipeline_*.csv")
        
        print(f"\n🔍 Quick insights:")
        print(f"   - Fastest phase: CSV Upload ({benchmark_results.data_generation.execution_time_seconds:.2f}s)")
        print(f"   - Memory peak: {benchmark_results.data_load.memory_mb_peak:.1f}MB")
        print(f"   - Data partitions: {benchmark_results.storage_metrics.num_partitions} (by report_period)")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()