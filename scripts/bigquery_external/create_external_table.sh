#!/bin/bash

# ============================================================================
# BigQuery External Table Creation Script
# ============================================================================
# Creates an external table pointing directly to CSV files in Google Cloud Storage
# for BigQuery vs External Table performance comparison
#
# Usage: ./create_external_table.sh [--force]
#   --force: Skip confirmation prompts
# ============================================================================

set -euo pipefail  # Exit on any error, undefined variable, or pipe failure

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCHEMA_FILE="$SCRIPT_DIR/external_table_schema.json"

# Load environment variables
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    source "$PROJECT_ROOT/.env"
else
    echo "❌ Error: .env file not found in project root"
    exit 1
fi

# BigQuery configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
DATASET_ID="${BIGQUERY_DATASET}"
EXTERNAL_TABLE_ID="ext_healthcare_hospital_data"
FULL_EXTERNAL_TABLE_ID="${DATASET_ID}.${EXTERNAL_TABLE_ID}"
GCS_BUCKET="${GCS_BUCKET_NAME}"
GCS_SOURCE_PATTERN="gs://${GCS_BUCKET}/raw/*.csv"

# Force flag
FORCE_MODE=false
if [[ "${1:-}" == "--force" ]]; then
    FORCE_MODE=true
fi

# Logging functions
log_info() {
    echo "ℹ️  $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo "✅ $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo "❌ $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

log_warning() {
    echo "⚠️  $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Validation functions
validate_environment() {
    log_info "Validating environment and dependencies..."
    
    # Check required tools
    local required_tools=("bq" "gsutil" "gcloud")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "Required tool '$tool' is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check required environment variables
    local required_vars=("GOOGLE_CLOUD_PROJECT" "BIGQUERY_DATASET" "GCS_BUCKET_NAME")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_error "Required environment variable '$var' is not set"
            exit 1
        fi
    done
    
    # Verify schema file exists
    if [[ ! -f "$SCHEMA_FILE" ]]; then
        log_error "Schema file not found: $SCHEMA_FILE"
        exit 1
    fi
    
    log_success "Environment validation passed"
}

check_gcs_files() {
    log_info "Checking GCS source files..."
    
    # List files matching the pattern
    local file_count
    file_count=$(gsutil ls "$GCS_SOURCE_PATTERN" 2>/dev/null | wc -l || echo "0")
    
    if [[ "$file_count" -eq 0 ]]; then
        log_error "No CSV files found at: $GCS_SOURCE_PATTERN"
        log_error "Run the data preparation pipeline first to upload CSV files to GCS"
        exit 1
    fi
    
    log_success "Found $file_count CSV files in GCS"
    
    # Show file details
    log_info "CSV files found:"
    gsutil ls -l "$GCS_SOURCE_PATTERN" | head -5
    if [[ "$file_count" -gt 5 ]]; then
        log_info "... and $((file_count - 5)) more files"
    fi
}

check_existing_table() {
    log_info "Checking for existing external table..."
    
    if bq show --quiet "$FULL_EXTERNAL_TABLE_ID" &> /dev/null; then
        log_warning "External table already exists: $FULL_EXTERNAL_TABLE_ID"
        
        if [[ "$FORCE_MODE" == "false" ]]; then
            echo "Options:"
            echo "  1. Delete and recreate the table"
            echo "  2. Keep existing table and exit"
            echo "  3. Cancel operation"
            
            read -p "Choose option (1-3): " choice
            case "$choice" in
                1)
                    log_info "Deleting existing external table..."
                    bq rm -f -t "$FULL_EXTERNAL_TABLE_ID"
                    log_success "Existing table deleted"
                    ;;
                2)
                    log_info "Keeping existing table. Use --force to override."
                    return 1
                    ;;
                *)
                    log_info "Operation cancelled"
                    exit 0
                    ;;
            esac
        else
            log_info "Force mode: Deleting existing external table..."
            bq rm -f -t "$FULL_EXTERNAL_TABLE_ID"
            log_success "Existing table deleted"
        fi
    fi
    return 0
}

create_external_table() {
    log_info "Creating BigQuery external table..."
    log_info "  📋 Table: $FULL_EXTERNAL_TABLE_ID"
    log_info "  📁 Source: $GCS_SOURCE_PATTERN"
    log_info "  📊 Format: CSV with header"
    
    # Create external table using bq mk
    local start_time
    start_time=$(date +%s)
    
    # Create external table definition
    local temp_def_file="/tmp/external_table_def.json"
    cat > "$temp_def_file" << EOF
{
  "sourceFormat": "CSV",
  "sourceUris": ["$GCS_SOURCE_PATTERN"],
  "csvOptions": {
    "skipLeadingRows": 1
  },
  "schema": {
    "fields": $(cat "$SCHEMA_FILE")
  }
}
EOF
    
    bq mk \
        --external_table_definition="$temp_def_file" \
        --description="External table for healthcare hospital data - queries CSV files directly from GCS" \
        "$FULL_EXTERNAL_TABLE_ID"
    
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "External table created successfully in ${duration} seconds"
}

verify_external_table() {
    log_info "Verifying external table..."
    
    # Get table information
    local table_info
    table_info=$(bq show --format=json "$FULL_EXTERNAL_TABLE_ID")
    
    # Extract key metrics using basic text processing
    local table_type
    table_type=$(echo "$table_info" | grep -o '"type"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    
    log_success "External table verification complete:"
    log_info "  📊 Table type: $table_type"
    log_info "  📁 Source files: $GCS_SOURCE_PATTERN"
    
    # Test query to count records
    log_info "Testing external table with sample query..."
    local record_count
    record_count=$(bq query --use_legacy_sql=false --format=csv --quiet \
        "SELECT COUNT(*) FROM \`$FULL_EXTERNAL_TABLE_ID\`" | tail -n 1)
    
    log_success "External table contains $record_count records"
    
    # Show sample data
    log_info "Sample data preview:"
    bq query --use_legacy_sql=false --format=prettyjson --quiet \
        "SELECT provider_id, hospital_name, city, state, beds, total_expenses 
         FROM \`$FULL_EXTERNAL_TABLE_ID\` 
         LIMIT 5" | head -20
}

show_usage_info() {
    log_success "🎉 External table setup complete!"
    echo
    echo "📊 Table Details:"
    echo "  - External Table: $FULL_EXTERNAL_TABLE_ID"
    echo "  - Data Source: GCS CSV files at $GCS_SOURCE_PATTERN"
    echo "  - Query Method: Direct CSV file scanning (no data ingestion)"
    echo
    echo "🔍 Key Differences from Native Table:"
    echo "  - No data storage costs (queries scan CSV files directly)"
    echo "  - Higher query latency (file scanning overhead)"
    echo "  - No partitioning/clustering optimizations"
    echo "  - Network I/O costs for data transfer"
    echo
    echo "🚀 Next Steps:"
    echo "  1. Run benchmark queries against external table"
    echo "  2. Compare performance with native table"
    echo "  3. Analyze cost differences (processing vs storage)"
    echo
    echo "💡 Example Query:"
    echo "  bq query --use_legacy_sql=false \\"
    echo "    \"SELECT COUNT(*) FROM \\\`$FULL_EXTERNAL_TABLE_ID\\\` WHERE beds > 50\""
}

cleanup() {
    log_info "Cleaning up temporary files..."
    [ -f "/tmp/external_table_def.json" ] && rm "/tmp/external_table_def.json"
    log_success "Cleanup complete"
}

# Main execution
main() {
    log_info "🚀 Starting BigQuery External Table Creation"
    log_info "Project: $PROJECT_ID | Dataset: $DATASET_ID | External Table: $EXTERNAL_TABLE_ID"
    echo
    
    validate_environment
    check_gcs_files
    
    if check_existing_table; then
        create_external_table
        verify_external_table
        show_usage_info
    else
        log_info "External table already exists and was kept. Exiting."
    fi
    
    cleanup
    log_success "External table setup completed successfully! 🎉"
}

# Error handling
trap 'log_error "Script failed on line $LINENO. Exit code: $?"' ERR

# Run main function
main "$@"