"""
Google Cloud Platform Configuration Module

Handles authentication and connection setup for BigQuery and Cloud Storage.
"""

import os
import logging
from typing import Optional
from google.cloud import bigquery, storage
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GCPConfig:
    """Google Cloud Platform configuration and connection manager."""
    
    def __init__(self):
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.region = os.getenv('GOOGLE_CLOUD_REGION', 'us-central1')
        self.bucket_name = os.getenv('GCS_BUCKET_NAME')
        self.dataset_id = os.getenv('BIGQUERY_DATASET', 'healthcare_benchmark')
        self.table_id = os.getenv('BIGQUERY_TABLE', 'hosp_cost_report')
        
        self._credentials = None
        self._bigquery_client = None
        self._storage_client = None
    
    def validate_config(self) -> bool:
        """Validate required configuration parameters."""
        missing_vars = []
        
        if not self.project_id:
            missing_vars.append('GOOGLE_CLOUD_PROJECT')
        if not self.bucket_name:
            missing_vars.append('GCS_BUCKET_NAME')
            
        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            return False
            
        return True
    
    def get_credentials(self):
        """Get Google Cloud credentials."""
        if self._credentials is None:
            try:
                self._credentials, project = default()
                logger.info(f"Successfully loaded credentials for project: {project}")
                
                # Override project_id from credentials if not set in env
                if not self.project_id:
                    self.project_id = project
                    
            except DefaultCredentialsError as e:
                logger.error(f"Failed to load Google Cloud credentials: {e}")
                raise
                
        return self._credentials
    
    def get_bigquery_client(self) -> bigquery.Client:
        """Get BigQuery client instance."""
        if self._bigquery_client is None:
            credentials = self.get_credentials()
            self._bigquery_client = bigquery.Client(
                project=self.project_id,
                credentials=credentials
            )
            logger.info(f"BigQuery client created for project: {self.project_id}")
            
        return self._bigquery_client
    
    def get_storage_client(self) -> storage.Client:
        """Get Google Cloud Storage client instance."""
        if self._storage_client is None:
            credentials = self.get_credentials()
            self._storage_client = storage.Client(
                project=self.project_id,
                credentials=credentials
            )
            logger.info(f"Storage client created for project: {self.project_id}")
            
        return self._storage_client
    
    def get_full_table_id(self) -> str:
        """Get fully qualified BigQuery table ID."""
        return f"{self.project_id}.{self.dataset_id}.{self.table_id}"
    
    def get_bucket_uri(self, path: Optional[str] = None) -> str:
        """Get GCS bucket URI with optional path."""
        base_uri = f"gs://{self.bucket_name}"
        if path:
            return f"{base_uri}/{path.lstrip('/')}"
        return base_uri


# Global configuration instance
gcp_config = GCPConfig()