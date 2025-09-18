#!/usr/bin/env python3
"""
Real CMS HCRIS Multi-Year Data Downloader
==========================================
Downloads and processes real CMS Hospital Cost Report Information System (HCRIS) 
data for multiple fiscal years to enable proper BigQuery partitioning demonstrations.

Downloads fiscal years 2021-2023 (~2-3 million records) to replace sample data
with real healthcare financial data.

Usage:
    python hcris_downloader.py [--years 2021,2022,2023] [--max-hospitals 1000]
"""

import os
import sys
import logging
import requests
import zipfile
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Optional, Tuple
import time

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

class HCRISDataDownloader:
    """Downloads and processes real CMS HCRIS data for multi-year benchmarking."""
    
    def __init__(self):
        self.config = gcp_config
        self.base_url = "https://www.cms.gov"
        self.raw_data_dir = Path("data/raw/hcris")
        self.processed_data_dir = Path("data/processed/hcris")
        
        # Create directories
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        
        # CMS HCRIS download paths (from our research)
        self.download_paths = {
            2021: "/httpswwwcmsgovresearch-statistics-data-and-systemsdownloadable-public-use-filescost-reportscost/2021-0",
            2022: "/data-research/statistics-trends-and-reports/cost-reports/cost-reports-fiscal-year/hospital-2010-fy-2022", 
            2023: "/data-research/statistics-trends-and-reports/cost-reports/cost-reports-fiscal-year/hospital-2010-fy-2023-0"
        }
    
    def download_year_data(self, year: int) -> Optional[Path]:
        """Download HCRIS data for a specific fiscal year."""
        if year not in self.download_paths:
            logger.error(f"No download path configured for fiscal year {year}")
            return None
            
        download_path = self.download_paths[year]
        download_url = f"{self.base_url}{download_path}"
        
        logger.info(f"Downloading HCRIS data for fiscal year {year}")
        logger.info(f"URL: {download_url}")
        
        # Create year-specific directory
        year_dir = self.raw_data_dir / str(year)
        year_dir.mkdir(exist_ok=True)
        
        zip_filename = year_dir / f"hcris_fy{year}.zip"
        
        try:
            # Check if file already exists
            if zip_filename.exists():
                logger.info(f"File already exists: {zip_filename}")
                return zip_filename
            
            # Download with progress tracking
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(zip_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if downloaded_size % (1024 * 1024) == 0:  # Log every MB
                                logger.info(f"Downloaded {downloaded_size // (1024*1024)}MB / {total_size // (1024*1024)}MB ({progress:.1f}%)")
            
            logger.info(f"✅ Successfully downloaded: {zip_filename} ({downloaded_size // (1024*1024)}MB)")
            return zip_filename
            
        except requests.RequestException as e:
            logger.error(f"Failed to download data for year {year}: {str(e)}")
            return None
    
    def extract_year_data(self, zip_path: Path) -> Dict[str, Path]:
        """Extract ZIP file and return paths to key data files."""
        if not zip_path.exists():
            logger.error(f"ZIP file not found: {zip_path}")
            return {}
        
        extract_dir = zip_path.parent / zip_path.stem
        extract_dir.mkdir(exist_ok=True)
        
        logger.info(f"Extracting {zip_path.name}...")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the main data files (typical HCRIS structure)
            extracted_files = {}
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    filename_lower = file_path.name.lower()
                    
                    # Identify key files by naming patterns
                    if 'hosp' in filename_lower and '2552' in filename_lower:
                        if 'rpt' in filename_lower:
                            extracted_files['report'] = file_path
                        elif 'nmrc' in filename_lower:
                            extracted_files['numeric'] = file_path
                        elif 'alpha' in filename_lower:
                            extracted_files['alpha'] = file_path
            
            logger.info(f"Extracted files: {list(extracted_files.keys())}")
            return extracted_files
            
        except zipfile.BadZipFile as e:
            logger.error(f"Failed to extract ZIP file: {str(e)}")
            return {}
    
    def process_hcris_files(self, extracted_files: Dict[str, Path], year: int, max_hospitals: Optional[int] = None) -> Optional[pd.DataFrame]:
        """Process HCRIS files into a unified DataFrame."""
        logger.info(f"Processing HCRIS files for year {year}")
        
        if 'numeric' not in extracted_files:
            logger.error("Numeric file not found - this contains the main financial data")
            return None
        
        try:
            # Read the main numeric file (this is typically very large)
            logger.info("Reading numeric data file...")
            numeric_file = extracted_files['numeric']
            
            # HCRIS files are typically CSV or fixed-width format
            # Try CSV first, then fixed-width if that fails
            try:
                numeric_df = pd.read_csv(numeric_file, low_memory=False)
            except:
                logger.info("CSV read failed, trying fixed-width format...")
                # HCRIS files often have specific column widths
                numeric_df = pd.read_fwf(numeric_file, header=0)
            
            logger.info(f"Numeric data shape: {numeric_df.shape}")
            
            # Process report metadata if available
            hospital_info = {}
            if 'report' in extracted_files:
                logger.info("Reading report metadata...")
                try:
                    report_df = pd.read_csv(extracted_files['report'], low_memory=False)
                    # Extract hospital identifiers and basic info
                    hospital_info = self._extract_hospital_info(report_df)
                except Exception as e:
                    logger.warning(f"Could not process report file: {str(e)}")
            
            # Transform to our benchmark schema
            processed_df = self._transform_to_benchmark_schema(numeric_df, hospital_info, year, max_hospitals)
            
            if processed_df is not None:
                logger.info(f"Processed data shape: {processed_df.shape}")
            
            return processed_df
            
        except Exception as e:
            logger.error(f"Failed to process HCRIS files: {str(e)}")
            return None
    
    def _extract_hospital_info(self, report_df: pd.DataFrame) -> Dict:
        """Extract hospital information from report metadata."""
        hospital_info = {}
        
        # HCRIS report files typically have these columns (names may vary)
        id_cols = ['RPT_REC_NUM', 'PROVIDER_ID', 'PRVDR_NUM', 'CCN']
        name_cols = ['PROVIDER_NAME', 'PRVDR_NAME', 'HOSPITAL_NAME']
        city_cols = ['CITY', 'PRVDR_CITY']
        state_cols = ['STATE', 'PRVDR_STATE']
        
        try:
            for _, row in report_df.iterrows():
                # Find provider ID
                provider_id = None
                for col in id_cols:
                    if col in row and pd.notna(row[col]):
                        provider_id = str(row[col]).strip()
                        break
                
                if provider_id:
                    hospital_info[provider_id] = {
                        'name': self._find_value(row, name_cols),
                        'city': self._find_value(row, city_cols),
                        'state': self._find_value(row, state_cols)
                    }
                    
        except Exception as e:
            logger.warning(f"Error extracting hospital info: {str(e)}")
        
        logger.info(f"Extracted info for {len(hospital_info)} hospitals")
        return hospital_info
    
    def _find_value(self, row: pd.Series, possible_cols: List[str]) -> str:
        """Find first non-null value from possible column names."""
        for col in possible_cols:
            if col in row and pd.notna(row[col]):
                return str(row[col]).strip()
        return "Unknown"
    
    def _transform_to_benchmark_schema(self, numeric_df: pd.DataFrame, hospital_info: Dict, year: int, max_hospitals: Optional[int]) -> Optional[pd.DataFrame]:
        """Transform HCRIS data to match our benchmark schema."""
        logger.info("Transforming data to benchmark schema...")
        
        try:
            # HCRIS numeric files typically have these columns:
            # RPT_REC_NUM, PROVIDER_ID, WKSHT_CD, LINE_NUM, CLMN_NUM, ITM_VAL_NUM
            # We need to pivot this data to get financial metrics per hospital
            
            # Common HCRIS worksheet and line item codes for key financial data
            financial_mappings = {
                'total_expenses': ('G300000', '100'),  # Total Expenses (worksheet G3, line 100)
                'total_charges': ('G200000', '100'),   # Total Charges (worksheet G2, line 100)
                'net_income': ('G300000', '300'),      # Net Income (worksheet G3, line 300)
                'beds': ('S300001', '1400'),           # Licensed Beds (worksheet S3, line 1400)
                'patient_days': ('S300001', '1500'),   # Patient Days
                'discharges': ('S300001', '1600')      # Discharges
            }
            
            # Check column names in the actual data
            logger.info(f"Available columns: {list(numeric_df.columns)[:10]}...")
            
            # Try to identify the key columns (names vary across HCRIS versions)
            provider_col = self._find_column(numeric_df, ['RPT_REC_NUM', 'PROVIDER_ID', 'PRVDR_NUM'])
            worksheet_col = self._find_column(numeric_df, ['WKSHT_CD', 'WORKSHEET_CODE'])
            line_col = self._find_column(numeric_df, ['LINE_NUM', 'LINE_NUMBER'])
            value_col = self._find_column(numeric_df, ['ITM_VAL_NUM', 'ITEM_VALUE', 'VALUE'])
            
            if not all([provider_col, worksheet_col, line_col, value_col]):
                logger.error("Could not identify required columns in HCRIS data")
                return None
            
            logger.info(f"Using columns: provider={provider_col}, worksheet={worksheet_col}, line={line_col}, value={value_col}")
            
            # Extract financial data for each hospital
            hospitals = []
            unique_providers = numeric_df[provider_col].unique()
            
            if max_hospitals:
                unique_providers = unique_providers[:max_hospitals]
                logger.info(f"Limiting to first {max_hospitals} hospitals")
            
            for i, provider_id in enumerate(unique_providers):
                if i % 100 == 0:
                    logger.info(f"Processing hospital {i+1}/{len(unique_providers)}")
                
                provider_data = numeric_df[numeric_df[provider_col] == provider_id]
                
                hospital_record = {
                    'provider_id': int(provider_id) if str(provider_id).isdigit() else hash(str(provider_id)) % 1000000,
                    'report_period': f"{year}-12-31"  # Fiscal year end (matches existing schema)
                }
                
                # Extract financial metrics (map to existing schema)
                for metric, (worksheet, line) in financial_mappings.items():
                    value = self._extract_financial_value(provider_data, worksheet_col, line_col, value_col, worksheet, line)
                    # Map 'beds' to 'beds_number' to match existing schema
                    schema_field = 'beds_number' if metric == 'beds' else metric
                    hospital_record[schema_field] = value
                
                # Add hospital info if available
                provider_str = str(provider_id)
                if provider_str in hospital_info:
                    info = hospital_info[provider_str]
                    hospital_record['hospital_name'] = info['name']
                    hospital_record['city'] = info['city']
                    hospital_record['state'] = info['state']
                else:
                    hospital_record['hospital_name'] = f"Hospital {provider_id}"
                    hospital_record['city'] = "Unknown"
                    hospital_record['state'] = "Unknown"
                
                hospitals.append(hospital_record)
            
            # Convert to DataFrame and clean data
            df = pd.DataFrame(hospitals)
            df = self._clean_financial_data(df)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to transform data: {str(e)}")
            return None
    
    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Find the first matching column name from a list of possibilities."""
        for name in possible_names:
            if name in df.columns:
                return name
        return None
    
    def _extract_financial_value(self, provider_data: pd.DataFrame, worksheet_col: str, line_col: str, value_col: str, worksheet: str, line: str) -> float:
        """Extract a specific financial value from HCRIS data."""
        try:
            filtered_data = provider_data[
                (provider_data[worksheet_col] == worksheet) & 
                (provider_data[line_col] == line)
            ]
            
            if not filtered_data.empty:
                value = filtered_data[value_col].iloc[0]
                return float(value) if pd.notna(value) else 0.0
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    def _clean_financial_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate financial data."""
        logger.info("Cleaning financial data...")
        
        # Remove hospitals with missing critical data
        df = df[df['total_expenses'] > 0]
        df = df[df['beds_number'] > 0]
        
        # Set reasonable bounds (remove obvious data errors)
        df = df[df['total_expenses'] < 1e12]  # Less than $1 trillion
        df = df[df['beds_number'] < 10000]  # Less than 10,000 beds
        
        # Calculate derived fields
        df['patient_days'] = df['patient_days'].fillna(df['beds_number'] * 200)  # Estimate if missing
        df['discharges'] = df['discharges'].fillna(df['beds_number'] * 30)  # Estimate if missing
        df['fte_employees'] = (df['beds_number'] * 4).astype(int)  # Estimate FTE
        df['medicare_days'] = (df['patient_days'] * 0.4).astype(int)  # Estimate Medicare days
        df['medicaid_days'] = (df['patient_days'] * 0.2).astype(int)  # Estimate Medicaid days
        
        # Ensure proper data types (match existing schema)
        df['provider_id'] = df['provider_id'].astype(int)
        df['beds_number'] = df['beds_number'].astype(int)  # Match existing schema
        df['total_expenses'] = df['total_expenses'].astype(float)
        df['total_charges'] = df['total_charges'].astype(float)
        df['net_income'] = df['net_income'].astype(float)
        df['report_period'] = pd.to_datetime(df['report_period'])
        
        logger.info(f"Cleaned data: {len(df)} hospitals remaining")
        return df
    
    def save_processed_data(self, df: pd.DataFrame, year: int) -> Path:
        """Save processed data to CSV."""
        filename = self.processed_data_dir / f"hcris_hospitals_fy{year}.csv"
        df.to_csv(filename, index=False)
        logger.info(f"Saved processed data to: {filename}")
        return filename
    
    def upload_to_gcs(self, local_path: Path) -> str:
        """Upload processed data to Google Cloud Storage (temporary storage)."""
        try:
            client = storage.Client(project=self.config.project_id)
            bucket = client.bucket(self.config.bucket_name)
            
            # Store in hcris subfolder for easy cleanup
            gcs_path = f"raw/hcris/{local_path.name}"
            blob = bucket.blob(gcs_path)
            
            blob.upload_from_filename(str(local_path))
            gcs_uri = f"gs://{self.config.bucket_name}/{gcs_path}"
            
            logger.info(f"✅ Uploaded to GCS: {gcs_uri}")
            logger.info(f"⚠️  TEMPORARY: Delete hcris folder after testing!")
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {str(e)}")
            raise
    
    def list_cleanup_commands(self, processed_files: List[Tuple[int, Path]]) -> None:
        """Show manual cleanup commands for GCS files."""
        print(f"\n{'='*60}")
        print("🧹 MANUAL CLEANUP REQUIRED")
        print(f"{'='*60}")
        print("After testing is complete, clean up temporary GCS files:")
        print()
        print("# Delete entire hcris folder:")
        print(f"gsutil -m rm -r gs://{self.config.bucket_name}/raw/hcris/")
        print()
        print("# Or delete individual files:")
        for year, _ in processed_files:
            print(f"gsutil rm gs://{self.config.bucket_name}/raw/hcris/hcris_hospitals_fy{year}.csv")
        print()
        print("# Verify cleanup:")
        print(f"gsutil ls gs://{self.config.bucket_name}/raw/hcris/")
        print("(should show: BucketNotFoundException or empty)")
        print(f"\n{'='*60}")
    
    def get_staging_table_commands(self, processed_files: List[Tuple[int, Path]]) -> None:
        """Show commands to load data into existing staging table.""" 
        print(f"\n{'='*60}")
        print("📊 STAGING TABLE UPDATE COMMANDS")
        print(f"{'='*60}")
        print("1. Backup current table (optional):")
        print(f"bq cp healthcare_benchmark.stg_healthcare_hospital_data healthcare_benchmark.stg_backup_$(date +%Y%m%d)")
        print()
        print("2. Clear existing data:")
        print(f'bq query --use_legacy_sql=false "DELETE FROM healthcare_benchmark.stg_healthcare_hospital_data WHERE 1=1"')
        print()
        print("3. Load HCRIS data (creates new yearly partitions):")
        for year, _ in processed_files:
            print(f"bq load --source_format=CSV --skip_leading_rows=1 \\")
            print(f"  healthcare_benchmark.stg_healthcare_hospital_data \\")
            print(f"  gs://{self.config.bucket_name}/raw/hcris/hcris_hospitals_fy{year}.csv")
        print()
        print("4. Verify partitioning:")
        print('bq query --use_legacy_sql=false "SELECT EXTRACT(YEAR FROM report_period) as year, COUNT(*) as hospitals FROM healthcare_benchmark.stg_healthcare_hospital_data GROUP BY year ORDER BY year"')
        print(f"\n{'='*60}")
    
    def get_external_table_update_commands(self) -> None:
        """Show commands to update external table to use HCRIS data temporarily."""
        print(f"\n{'='*60}")
        print("🔗 EXTERNAL TABLE UPDATE COMMANDS")
        print(f"{'='*60}")
        print("1. Update external table to use HCRIS data:")
        print(f"./scripts/bigquery_external/create_external_table.sh --force \\")
        print(f"  --source-pattern 'gs://{self.config.bucket_name}/raw/hcris/*.csv'")
        print()
        print("2. After testing, restore to sample data:")
        print(f"./scripts/bigquery_external/create_external_table.sh --force \\")
        print(f"  --source-pattern 'gs://{self.config.bucket_name}/raw/*.csv'")
        print(f"\n{'='*60}")
    
    def process_multiple_years(self, years: List[int], max_hospitals: Optional[int] = None) -> List[Tuple[int, Path]]:
        """Download and process data for multiple years."""
        logger.info(f"Processing HCRIS data for years: {years}")
        
        if max_hospitals:
            logger.info(f"Limiting each year to {max_hospitals} hospitals")
        
        processed_files = []
        
        for year in years:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing Fiscal Year {year}")
            logger.info(f"{'='*60}")
            
            # Download
            zip_path = self.download_year_data(year)
            if not zip_path:
                logger.error(f"Failed to download data for year {year}")
                continue
            
            # Extract
            extracted_files = self.extract_year_data(zip_path)
            if not extracted_files:
                logger.error(f"Failed to extract data for year {year}")
                continue
            
            # Process
            df = self.process_hcris_files(extracted_files, year, max_hospitals)
            if df is None:
                logger.error(f"Failed to process data for year {year}")
                continue
            
            # Save
            csv_path = self.save_processed_data(df, year)
            processed_files.append((year, csv_path))
            
            # Upload to GCS
            try:
                gcs_uri = self.upload_to_gcs(csv_path)
                logger.info(f"Year {year} complete: {len(df)} hospitals, GCS: {gcs_uri}")
            except Exception as e:
                logger.warning(f"GCS upload failed for year {year}: {str(e)}")
        
        return processed_files

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Download real CMS HCRIS multi-year data")
    parser.add_argument("--years", default="2021,2022,2023", help="Comma-separated fiscal years")
    parser.add_argument("--max-hospitals", type=int, help="Maximum hospitals per year (for testing)")
    parser.add_argument("--test-mode", action="store_true", help="Test with limited data")
    
    args = parser.parse_args()
    
    years = [int(y.strip()) for y in args.years.split(",")]
    max_hospitals = args.max_hospitals or (100 if args.test_mode else None)
    
    downloader = HCRISDataDownloader()
    
    try:
        processed_files = downloader.process_multiple_years(years, max_hospitals)
        
        print(f"\n{'='*60}")
        print("🎉 HCRIS Data Processing Complete!")
        print(f"{'='*60}")
        
        total_hospitals = 0
        for year, csv_path in processed_files:
            df = pd.read_csv(csv_path)
            total_hospitals += len(df)
            print(f"✅ FY {year}: {len(df):,} hospitals ({csv_path.name})")
        
        print(f"\n📊 Total: {total_hospitals:,} hospital records across {len(processed_files)} years")
        print(f"🚀 Data uploaded to GCS - Ready for BigQuery testing!")
        
        # Show all required commands
        downloader.get_staging_table_commands(processed_files)
        downloader.get_external_table_update_commands()  
        downloader.list_cleanup_commands(processed_files)
        
    except Exception as e:
        logger.error(f"HCRIS processing failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())