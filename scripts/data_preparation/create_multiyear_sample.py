#!/usr/bin/env python3
"""
Multi-Year Sample Data Generator
================================
Creates sample hospital data across multiple years to test partitioning benefits
without needing to download real HCRIS data.

This generates realistic multi-year data that:
1. Matches existing staging table schema exactly
2. Creates yearly partitions when loaded
3. Demonstrates partition pruning benefits
4. Uses realistic hospital financial data patterns

Usage:
    python create_multiyear_sample.py [--years 2021,2022,2023] [--hospitals 1000]
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse
import random
from typing import List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import gcp_config
from google.cloud import storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MultiYearSampleGenerator:
    """Generates multi-year sample hospital data for partitioning tests."""
    
    def __init__(self):
        self.config = gcp_config
        self.processed_data_dir = Path("data/processed/multiyear")
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Hospital names and locations for realistic data
        self.hospital_names = [
            "General Hospital", "Medical Center", "Regional Medical", "Community Hospital",
            "Memorial Hospital", "University Hospital", "Baptist Medical", "Methodist Hospital",
            "Presbyterian Hospital", "Catholic Health", "Veterans Medical", "Children's Hospital",
            "Cancer Center", "Heart Institute", "Orthopedic Hospital", "Rehabilitation Center"
        ]
        
        self.cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", 
            "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
            "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis", "Seattle",
            "Denver", "Washington", "Boston", "Nashville", "Baltimore", "Louisville",
            "Portland", "Oklahoma City", "Milwaukee", "Las Vegas", "Albuquerque", "Tucson"
        ]
        
        self.states = [
            "NY", "CA", "IL", "TX", "AZ", "PA", "FL", "OH", "NC", "WA", 
            "CO", "MA", "TN", "MD", "KY", "GA", "MI", "VA", "NJ", "CT",
            "OR", "OK", "WI", "NV", "NM", "IN", "MN", "UT", "ID", "ME"
        ]
    
    def generate_hospitals_for_year(self, year: int, num_hospitals: int) -> pd.DataFrame:
        """Generate hospital data for a specific year."""
        logger.info(f"Generating {num_hospitals} hospitals for year {year}")
        
        hospitals = []
        
        for i in range(num_hospitals):
            # Create consistent provider IDs across years (100000-999999 range)
            provider_id = 100000 + i
            
            # Hospital details (consistent across years for same provider)
            random.seed(provider_id)  # Consistent details for same hospital
            city = random.choice(self.cities)
            state = random.choice(self.states)
            hospital_name = f"{city} {random.choice(self.hospital_names)}"
            
            # Bed count (slightly varies year to year)
            base_beds = int(np.random.lognormal(mean=4.5, sigma=0.8))
            base_beds = max(25, min(base_beds, 1200))
            
            # Add yearly variation (±5%)
            yearly_variation = np.random.uniform(0.95, 1.05)
            beds_number = max(25, int(base_beds * yearly_variation))
            
            # Financial data with yearly trends
            # Base costs increase ~3-5% per year + inflation
            inflation_factor = (1.035) ** (year - 2021)  # 3.5% annual increase
            yearly_factor = np.random.uniform(0.95, 1.15)  # ±15% year-over-year variation
            
            # Base financial calculations
            base_cost_per_bed = np.random.normal(500000, 100000)
            total_expenses = max(1000000, beds_number * base_cost_per_bed * inflation_factor * yearly_factor)
            
            # Charges are typically 3-5x costs
            charge_multiplier = np.random.uniform(2.5, 5.5)
            total_charges = total_expenses * charge_multiplier
            
            # Net income varies significantly by year and efficiency
            revenue = total_charges * np.random.uniform(0.3, 0.7)  # Payer mix effect
            other_revenue = total_expenses * np.random.uniform(0.05, 0.15)
            net_income = revenue + other_revenue - total_expenses
            
            # Add COVID-19 impact for 2020-2022
            if year in [2020, 2021, 2022]:
                covid_impact = np.random.uniform(0.85, 0.95)  # 5-15% revenue decrease
                net_income *= covid_impact
                total_expenses *= np.random.uniform(1.05, 1.15)  # Increased costs
            
            # Calculate derived metrics
            patient_days = int(beds_number * np.random.uniform(200, 350))
            discharges = int(beds_number * np.random.uniform(15, 45))
            fte_employees = int(beds_number * np.random.uniform(3, 8))
            medicare_days = int(patient_days * np.random.uniform(0.3, 0.5))
            medicaid_days = int(patient_days * np.random.uniform(0.15, 0.25))
            
            hospital_record = {
                'provider_id': provider_id,
                'hospital_name': hospital_name,
                'city': city,
                'state': state,
                'beds_number': beds_number,
                'report_period': f"{year}-12-31",
                'total_expenses': round(total_expenses, 2),
                'total_charges': round(total_charges, 2),
                'net_income': round(net_income, 2),
                'patient_days': patient_days,
                'discharges': discharges,
                'fte_employees': fte_employees,
                'medicare_days': medicare_days,
                'medicaid_days': medicaid_days
            }
            
            hospitals.append(hospital_record)
        
        df = pd.DataFrame(hospitals)
        
        # Ensure proper data types (match existing schema exactly)
        df['provider_id'] = df['provider_id'].astype(int)
        df['beds_number'] = df['beds_number'].astype(int)
        df['total_expenses'] = df['total_expenses'].astype(float)
        df['total_charges'] = df['total_charges'].astype(float)
        df['net_income'] = df['net_income'].astype(float)
        df['patient_days'] = df['patient_days'].astype(int)
        df['discharges'] = df['discharges'].astype(int)
        df['fte_employees'] = df['fte_employees'].astype(int)
        df['medicare_days'] = df['medicare_days'].astype(int)
        df['medicaid_days'] = df['medicaid_days'].astype(int)
        df['report_period'] = pd.to_datetime(df['report_period'])
        
        logger.info(f"Generated {len(df)} hospitals for year {year}")
        logger.info(f"Expense range: ${df['total_expenses'].min():,.0f} - ${df['total_expenses'].max():,.0f}")
        logger.info(f"Bed range: {df['beds_number'].min()} - {df['beds_number'].max()}")
        
        return df
    
    def save_year_data(self, df: pd.DataFrame, year: int) -> Path:
        """Save year data to CSV."""
        filename = self.processed_data_dir / f"multiyear_hospitals_{year}.csv"
        df.to_csv(filename, index=False)
        logger.info(f"Saved {year} data to: {filename}")
        return filename
    
    def upload_to_gcs(self, local_path: Path) -> str:
        """Upload to GCS temporary storage."""
        try:
            client = storage.Client(project=self.config.project_id)
            bucket = client.bucket(self.config.bucket_name)
            
            # Store in multiyear subfolder for easy cleanup
            gcs_path = f"raw/multiyear/{local_path.name}"
            blob = bucket.blob(gcs_path)
            
            blob.upload_from_filename(str(local_path))
            gcs_uri = f"gs://{self.config.bucket_name}/{gcs_path}"
            
            logger.info(f"✅ Uploaded to GCS: {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {str(e)}")
            raise
    
    def generate_multiyear_data(self, years: List[int], hospitals_per_year: int) -> List[Path]:
        """Generate multi-year hospital data."""
        logger.info(f"Generating multi-year data for years: {years}")
        logger.info(f"Hospitals per year: {hospitals_per_year}")
        
        files = []
        
        for year in years:
            logger.info(f"\n--- Processing Year {year} ---")
            
            # Generate data
            df = self.generate_hospitals_for_year(year, hospitals_per_year)
            
            # Save locally
            csv_path = self.save_year_data(df, year)
            files.append(csv_path)
            
            # Upload to GCS
            try:
                gcs_uri = self.upload_to_gcs(csv_path)
                logger.info(f"Year {year}: {len(df)} hospitals → {gcs_uri}")
            except Exception as e:
                logger.warning(f"GCS upload failed for year {year}: {str(e)}")
        
        return files
    
    def show_loading_commands(self, years: List[int]) -> None:
        """Show commands to load the multi-year data."""
        print(f"\n{'='*60}")
        print("📊 MULTI-YEAR DATA LOADING COMMANDS")
        print(f"{'='*60}")
        print("1. Backup current table (optional):")
        print(f"bq cp healthcare_benchmark.stg_healthcare_hospital_data healthcare_benchmark.stg_backup_$(date +%Y%m%d)")
        print()
        print("2. Clear existing data:")
        print(f'bq query --use_legacy_sql=false "DELETE FROM healthcare_benchmark.stg_healthcare_hospital_data WHERE 1=1"')
        print()
        print("3. Load multi-year data (creates yearly partitions):")
        for year in years:
            print(f"bq load --source_format=CSV --skip_leading_rows=1 \\")
            print(f"  healthcare_benchmark.stg_healthcare_hospital_data \\")
            print(f"  gs://{self.config.bucket_name}/raw/multiyear/multiyear_hospitals_{year}.csv")
        print()
        print("4. Verify partitioning:")
        print('bq query --use_legacy_sql=false "SELECT EXTRACT(YEAR FROM report_period) as year, COUNT(*) as hospitals FROM healthcare_benchmark.stg_healthcare_hospital_data GROUP BY year ORDER BY year"')
        print()
        print("5. Test partition pruning:")
        print('bq query --use_legacy_sql=false "SELECT COUNT(*) FROM healthcare_benchmark.stg_healthcare_hospital_data WHERE EXTRACT(YEAR FROM report_period) = 2023"')
        print(f"\n{'='*60}")
    
    def show_cleanup_commands(self, years: List[int]) -> None:
        """Show cleanup commands."""
        print(f"\n{'='*60}")
        print("🧹 CLEANUP COMMANDS")
        print(f"{'='*60}")
        print("After testing, clean up temporary GCS files:")
        print()
        print("# Delete entire multiyear folder:")
        print(f"gsutil -m rm -r gs://{self.config.bucket_name}/raw/multiyear/")
        print()
        print("# Or delete individual files:")
        for year in years:
            print(f"gsutil rm gs://{self.config.bucket_name}/raw/multiyear/multiyear_hospitals_{year}.csv")
        print()
        print("# Verify cleanup:")
        print(f"gsutil ls gs://{self.config.bucket_name}/raw/multiyear/")
        print("(should show: BucketNotFoundException)")
        print(f"\n{'='*60}")
    
    def show_external_table_commands(self) -> None:
        """Show external table update commands."""
        print(f"\n{'='*60}")
        print("🔗 EXTERNAL TABLE UPDATE (Optional)")
        print(f"{'='*60}")
        print("To test external table with multi-year data:")
        print()
        print("1. Update external table:")
        print("# (You'll need to modify the external table script to accept custom patterns)")
        print(f"# Point to: gs://{self.config.bucket_name}/raw/multiyear/*.csv")
        print()
        print("2. Restore after testing:")
        print(f"# Point back to: gs://{self.config.bucket_name}/raw/*.csv")
        print(f"\n{'='*60}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate multi-year sample hospital data")
    parser.add_argument("--years", default="2021,2022,2023", help="Comma-separated years")
    parser.add_argument("--hospitals", type=int, default=1000, help="Hospitals per year")
    parser.add_argument("--test-mode", action="store_true", help="Generate smaller dataset for testing")
    
    args = parser.parse_args()
    
    years = [int(y.strip()) for y in args.years.split(",")]
    hospitals_per_year = 100 if args.test_mode else args.hospitals
    
    generator = MultiYearSampleGenerator()
    
    try:
        logger.info(f"🚀 Starting multi-year sample data generation")
        logger.info(f"Years: {years}")
        logger.info(f"Hospitals per year: {hospitals_per_year}")
        logger.info(f"Total hospitals: {len(years) * hospitals_per_year:,}")
        
        files = generator.generate_multiyear_data(years, hospitals_per_year)
        
        print(f"\n{'='*60}")
        print("🎉 MULTI-YEAR SAMPLE DATA COMPLETE!")
        print(f"{'='*60}")
        
        total_hospitals = 0
        for i, (year, file_path) in enumerate(zip(years, files)):
            df = pd.read_csv(file_path)
            total_hospitals += len(df)
            print(f"✅ {year}: {len(df):,} hospitals ({file_path.name})")
        
        print(f"\n📊 Total: {total_hospitals:,} hospital records across {len(years)} years")
        print(f"📈 Expected partitions: {len(years)} yearly partitions")
        print(f"🔍 Partition pruning benefit: {100 - (100/len(years)):.0f}% data reduction with year filters")
        
        # Show all commands
        generator.show_loading_commands(years)
        generator.show_external_table_commands()
        generator.show_cleanup_commands(years)
        
    except Exception as e:
        logger.error(f"Multi-year generation failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())