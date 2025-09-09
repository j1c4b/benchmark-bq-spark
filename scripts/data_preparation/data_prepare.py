#!/usr/bin/env python3
"""
Hospital Cost Report Data Preparation Script

Downloads, processes, and uploads sample hospital cost report data for benchmarking.
For initial testing, generates realistic sample data based on HCRIS structure.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import gcp_config
from google.cloud import storage
import requests
from io import StringIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HospitalDataPreparer:
    """Prepares hospital cost report data for benchmarking."""
    
    def __init__(self):
        self.config = gcp_config
        self.raw_data_dir = "data/raw"
        self.processed_data_dir = "data/processed"
        
        # Ensure directories exist
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)
    
    def generate_sample_data(self, num_rows: int = 100) -> pd.DataFrame:
        """
        Generate realistic sample hospital cost report data for testing.
        
        Args:
            num_rows: Number of hospital records to generate
            
        Returns:
            DataFrame with sample hospital cost data
        """
        logger.info(f"Generating {num_rows} rows of sample hospital cost data")
        
        # Set random seed for reproducibility
        np.random.seed(42)
        random.seed(42)
        
        # Generate realistic hospital data
        hospitals = []
        
        # Common hospital names and locations
        hospital_names = [
            "General", "Medical Center", "Regional", "Community", "Memorial", 
            "University", "St. Mary's", "Methodist", "Baptist", "Presbyterian"
        ]
        
        cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
            "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
            "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis",
            "Seattle", "Denver", "Boston", "Nashville", "Baltimore", "Louisville"
        ]
        
        states = [
            "NY", "CA", "IL", "TX", "AZ", "PA", "FL", "OH", "NC", "WA", 
            "CO", "MA", "TN", "MD", "KY", "GA", "MI", "VA", "NJ", "CT"
        ]
        
        for i in range(num_rows):
            # Generate provider ID (integer format)
            provider_id = 100000 + i
            
            # Hospital details
            city = random.choice(cities)
            state = random.choice(states)
            hospital_name = f"{city} {random.choice(hospital_names)}"
            
            # Bed count (realistic distribution)
            beds_number = int(np.random.lognormal(mean=4.5, sigma=0.8))
            beds_number = max(25, min(beds_number, 1200))  # Cap between 25-1200 beds
            
            # Financial data (correlated with bed count)
            base_cost_per_bed = np.random.normal(500000, 100000)  # $500k per bed average
            total_expenses = max(1000000, beds_number * base_cost_per_bed * np.random.normal(1.0, 0.3))
            
            # Charges are typically 3-5x costs
            charge_multiplier = np.random.uniform(2.5, 5.5)
            total_charges = total_expenses * charge_multiplier
            
            # Net income (can be negative for some hospitals)
            revenue = total_charges * np.random.uniform(0.3, 0.7)  # Payer mix effect
            other_revenue = total_expenses * np.random.uniform(0.05, 0.15)
            net_income = revenue + other_revenue - total_expenses
            
            # Report period (recent years)
            year = random.choice([2021, 2022, 2023, 2024])
            report_period = datetime(year, 12, 31)
            
            hospitals.append({
                'provider_id': provider_id,
                'hospital_name': hospital_name,
                'city': city,
                'state': state,
                'beds_number': beds_number,
                'report_period': report_period,
                'total_expenses': round(total_expenses, 2),
                'total_charges': round(total_charges, 2),
                'net_income': round(net_income, 2),
                'patient_days': int(beds_number * np.random.uniform(200, 350)),  # Occupancy rate
                'discharges': int(beds_number * np.random.uniform(15, 45)),      # Turnover
                'fte_employees': int(beds_number * np.random.uniform(3, 8)),     # Staff ratio
                'medicare_days': int(beds_number * np.random.uniform(80, 200)),  # Medicare utilization
                'medicaid_days': int(beds_number * np.random.uniform(30, 120)),  # Medicaid utilization
            })
        
        df = pd.DataFrame(hospitals)
        
        logger.info(f"Generated sample data: {len(df)} hospitals")
        logger.info(f"Bed count range: {df['beds_number'].min()}-{df['beds_number'].max()}")
        logger.info(f"Expense range: ${df['total_expenses'].min():,.0f} - ${df['total_expenses'].max():,.0f}")
        
        return df
    
    def save_to_csv(self, df: pd.DataFrame, filename: str, use_raw_dir: bool = True) -> str:
        """Save DataFrame to CSV file."""
        directory = self.raw_data_dir if use_raw_dir else self.processed_data_dir
        filepath = os.path.join(directory, filename)
        df.to_csv(filepath, index=False)
        logger.info(f"Saved data to {filepath}")
        return filepath
    
    def upload_to_gcs(self, local_filepath: str, gcs_path: str) -> str:
        """Upload file to Google Cloud Storage."""
        try:
            storage_client = self.config.get_storage_client()
            bucket = storage_client.bucket(self.config.bucket_name)
            
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(local_filepath)
            
            gcs_uri = f"gs://{self.config.bucket_name}/{gcs_path}"
            logger.info(f"Successfully uploaded {local_filepath} to {gcs_uri}")
            
            return gcs_uri
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            raise
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate the prepared data."""
        logger.info("Validating prepared data...")
        
        # Check required columns
        required_columns = [
            'provider_id', 'report_period', 'total_expenses', 
            'total_charges', 'net_income', 'beds_number'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check data quality
        if df['provider_id'].duplicated().any():
            logger.error("Duplicate provider IDs found")
            return False
        
        if df['beds_number'].min() <= 0:
            logger.error("Invalid bed counts found")
            return False
        
        if df['total_expenses'].isna().any():
            logger.error("Missing expense data found")
            return False
        
        logger.info("Data validation passed")
        return True
    
    def prepare_sample_data(self, num_rows: int = 100) -> str:
        """
        Complete workflow: generate, validate, save, and upload sample data.
        
        Args:
            num_rows: Number of sample records to generate
            
        Returns:
            GCS URI of uploaded file
        """
        logger.info("=" * 60)
        logger.info("🏥 Starting Hospital Data Preparation")
        logger.info("=" * 60)
        
        # Generate sample data
        df = self.generate_sample_data(num_rows)
        
        # Validate data
        if not self.validate_data(df):
            raise ValueError("Data validation failed")
        
        # Save to local CSV in raw directory (since this is newly generated data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hospital_cost_sample_{num_rows}rows_{timestamp}.csv"
        local_filepath = self.save_to_csv(df, filename, use_raw_dir=True)
        
        # Upload to GCS
        gcs_path = f"raw/{filename}"
        gcs_uri = self.upload_to_gcs(local_filepath, gcs_path)
        
        # Display summary
        logger.info("=" * 60)
        logger.info("📊 Data Preparation Summary")
        logger.info("=" * 60)
        logger.info(f"✅ Records generated: {len(df)}")
        logger.info(f"✅ Local file: {local_filepath}")
        logger.info(f"✅ GCS location: {gcs_uri}")
        logger.info(f"✅ File size: {os.path.getsize(local_filepath):,} bytes")
        
        # Data preview
        logger.info("\n📋 Data Preview:")
        logger.info(f"\n{df.head()}")
        
        logger.info("\n📈 Data Statistics:")
        logger.info(f"Average beds: {df['beds_number'].mean():.1f}")
        logger.info(f"Average expenses: ${df['total_expenses'].mean():,.0f}")
        logger.info(f"Hospitals with >50 beds: {len(df[df['beds_number'] > 50])}")
        
        return gcs_uri


def main():
    """Main function for testing."""
    try:
        preparer = HospitalDataPreparer()
        
        # Generate and upload 100 rows of sample data
        gcs_uri = preparer.prepare_sample_data(num_rows=100)
        
        print(f"\n🎉 Success! Sample data available at:")
        print(f"📁 {gcs_uri}")
        print(f"\n🚀 Ready for BigQuery and Spark benchmarking!")
        
    except Exception as e:
        logger.error(f"Data preparation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()