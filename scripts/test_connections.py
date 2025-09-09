#!/usr/bin/env python3
"""
GCP Connection Test Script

Tests BigQuery and Google Cloud Storage connections to ensure proper authentication
and access to required services.
"""

import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add scripts directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import gcp_config
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound, Forbidden
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionTester:
    """Test GCP service connections."""
    
    def __init__(self):
        self.config = gcp_config
        self.test_results = []
    
    def log_test_result(self, test_name: str, success: bool, message: str = "", details: Dict[str, Any] = None):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now()
        }
        self.test_results.append(result)
        
        log_msg = f"{status} {test_name}"
        if message:
            log_msg += f": {message}"
            
        if success:
            logger.info(log_msg)
        else:
            logger.error(log_msg)
            if details:
                logger.error(f"Details: {details}")
    
    def test_configuration(self) -> bool:
        """Test configuration validation."""
        try:
            is_valid = self.config.validate_config()
            if is_valid:
                self.log_test_result(
                    "Configuration Validation", 
                    True, 
                    "All required environment variables are set"
                )
            else:
                self.log_test_result(
                    "Configuration Validation", 
                    False, 
                    "Missing required environment variables"
                )
            return is_valid
        except Exception as e:
            self.log_test_result(
                "Configuration Validation", 
                False, 
                str(e)
            )
            return False
    
    def test_credentials(self) -> bool:
        """Test Google Cloud authentication."""
        try:
            credentials = self.config.get_credentials()
            self.log_test_result(
                "GCP Authentication", 
                True, 
                f"Successfully authenticated for project: {self.config.project_id}",
                {"project_id": self.config.project_id}
            )
            return True
        except Exception as e:
            self.log_test_result(
                "GCP Authentication", 
                False, 
                f"Authentication failed: {str(e)}"
            )
            return False
    
    def test_bigquery_connection(self) -> bool:
        """Test BigQuery connection and basic operations."""
        try:
            client = self.config.get_bigquery_client()
            
            # Test basic query
            query = "SELECT 1 as test_value, 'connection_test' as test_message"
            query_job = client.query(query)
            results = list(query_job)
            
            if results and results[0].test_value == 1:
                self.log_test_result(
                    "BigQuery Connection", 
                    True, 
                    "Successfully executed test query",
                    {"project": self.config.project_id, "query_job_id": query_job.job_id}
                )
                return True
            else:
                self.log_test_result(
                    "BigQuery Connection", 
                    False, 
                    "Test query returned unexpected results"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "BigQuery Connection", 
                False, 
                f"BigQuery connection failed: {str(e)}"
            )
            return False
    
    def test_bigquery_dataset_access(self) -> bool:
        """Test access to BigQuery dataset."""
        try:
            client = self.config.get_bigquery_client()
            dataset_id = f"{self.config.project_id}.{self.config.dataset_id}"
            
            try:
                dataset = client.get_dataset(dataset_id)
                self.log_test_result(
                    "BigQuery Dataset Access", 
                    True, 
                    f"Dataset '{dataset_id}' exists and is accessible",
                    {"dataset_id": dataset_id, "location": dataset.location}
                )
                return True
            except NotFound:
                self.log_test_result(
                    "BigQuery Dataset Access", 
                    False, 
                    f"Dataset '{dataset_id}' not found - will need to be created",
                    {"dataset_id": dataset_id}
                )
                return False
            except Forbidden:
                self.log_test_result(
                    "BigQuery Dataset Access", 
                    False, 
                    f"Access denied to dataset '{dataset_id}' - check permissions"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "BigQuery Dataset Access", 
                False, 
                f"Dataset access test failed: {str(e)}"
            )
            return False
    
    def test_storage_connection(self) -> bool:
        """Test Google Cloud Storage connection."""
        try:
            client = self.config.get_storage_client()
            
            # Test by listing buckets (this requires minimal permissions)
            buckets = list(client.list_buckets(max_results=1))
            
            self.log_test_result(
                "Google Cloud Storage Connection", 
                True, 
                "Successfully connected to Cloud Storage",
                {"project": self.config.project_id}
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Google Cloud Storage Connection", 
                False, 
                f"Storage connection failed: {str(e)}"
            )
            return False
    
    def test_bucket_access(self) -> bool:
        """Test access to specified GCS bucket."""
        try:
            client = self.config.get_storage_client()
            
            try:
                bucket = client.get_bucket(self.config.bucket_name)
                self.log_test_result(
                    "GCS Bucket Access", 
                    True, 
                    f"Bucket '{self.config.bucket_name}' exists and is accessible",
                    {
                        "bucket_name": self.config.bucket_name, 
                        "location": bucket.location,
                        "storage_class": bucket.storage_class
                    }
                )
                return True
            except NotFound:
                self.log_test_result(
                    "GCS Bucket Access", 
                    False, 
                    f"Bucket '{self.config.bucket_name}' not found - will need to be created"
                )
                return False
            except Forbidden:
                self.log_test_result(
                    "GCS Bucket Access", 
                    False, 
                    f"Access denied to bucket '{self.config.bucket_name}' - check permissions"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "GCS Bucket Access", 
                False, 
                f"Bucket access test failed: {str(e)}"
            )
            return False
    
    def run_all_tests(self) -> bool:
        """Run all connection tests."""
        logger.info("=" * 60)
        logger.info("🚀 Starting GCP Connection Tests")
        logger.info("=" * 60)
        
        tests = [
            self.test_configuration,
            self.test_credentials,
            self.test_bigquery_connection,
            self.test_bigquery_dataset_access,
            self.test_storage_connection,
            self.test_bucket_access
        ]
        
        all_passed = True
        
        for test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"Unexpected error in {test_func.__name__}: {e}")
                all_passed = False
        
        # Print summary
        self.print_summary()
        
        return all_passed
    
    def print_summary(self):
        """Print test results summary."""
        logger.info("=" * 60)
        logger.info("📊 Test Results Summary")
        logger.info("=" * 60)
        
        passed = sum(1 for r in self.test_results if r['success'])
        failed = len(self.test_results) - passed
        
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            logger.info(f"{status} {result['test']}")
            if result['message']:
                logger.info(f"   └─ {result['message']}")
        
        logger.info("-" * 60)
        logger.info(f"📈 Results: {passed} passed, {failed} failed")
        
        if failed > 0:
            logger.info("🔧 Next steps to fix failures:")
            logger.info("   1. Update .env file with your GCP project details")
            logger.info("   2. Ensure you're authenticated with 'gcloud auth application-default login'")
            logger.info("   3. Create required BigQuery dataset and GCS bucket")
            logger.info("   4. Verify IAM permissions for BigQuery and Storage")
        else:
            logger.info("🎉 All tests passed! GCP connection is ready for benchmarking.")


def main():
    """Main function."""
    tester = ConnectionTester()
    success = tester.run_all_tests()
    
    if not success:
        sys.exit(1)
    
    print("\n🎯 Connection test completed successfully!")
    print("You can now proceed with the benchmarking implementation.")


if __name__ == "__main__":
    main()