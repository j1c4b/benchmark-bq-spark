#!/bin/bash

#####################################################################
# BigQuery Load Script - Option 1: Shell Script with bq load
#
# Loads hospital cost data from GCS to BigQuery staging table
# using native bq command line tool
#####################################################################

# Script configuration
SCRIPT_NAME="BigQuery Load Script"
SCRIPT_VERSION="1.0"
LOG_PREFIX="[BQ-LOAD]"

# Load environment variables
if [ -f "../../.env" ]; then
    source ../../.env
else
    echo "$LOG_PREFIX ERROR: .env file not found"
    exit 1
fi

# Configuration from environment
PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
DATASET_ID="${BIGQUERY_DATASET}"
TABLE_ID="stg_healthcare_hospital_data"
BUCKET_NAME="${GCS_BUCKET_NAME}"

# BigQuery configuration
FULL_TABLE_ID="${PROJECT_ID}.${DATASET_ID}.${TABLE_ID}"
SCHEMA_FILE="schema_hospital_data.json"

# GCS path (we'll find the latest file)
GCS_BASE_PATH="gs://${BUCKET_NAME}/raw/"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#####################################################################
# Functions
#####################################################################

log_info() {
    echo -e "${BLUE}$LOG_PREFIX INFO:${NC} $1"
}

log_success() {
    echo -e "${GREEN}$LOG_PREFIX SUCCESS:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}$LOG_PREFIX WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}$LOG_PREFIX ERROR:${NC} $1"
}

print_header() {
    echo "=========================================================="
    echo "🚀 $SCRIPT_NAME v$SCRIPT_VERSION"
    echo "=========================================================="
    echo "📊 Loading hospital data to BigQuery staging table"
    echo "🎯 Target: $FULL_TABLE_ID"
    echo "☁️  Source: $GCS_BASE_PATH"
    echo "=========================================================="
}

validate_environment() {
    log_info "Validating environment and dependencies..."
    
    # Check if bq command is available
    if ! command -v bq &> /dev/null; then
        log_error "bq command not found. Please install Google Cloud SDK."
        exit 1
    fi
    
    # Check if authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "No active gcloud authentication found. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Verify project configuration
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
        log_warning "Current gcloud project ($CURRENT_PROJECT) != configured project ($PROJECT_ID)"
        log_info "Setting project to $PROJECT_ID"
        gcloud config set project "$PROJECT_ID"
    fi
    
    # Check required environment variables
    if [ -z "$PROJECT_ID" ] || [ -z "$DATASET_ID" ] || [ -z "$BUCKET_NAME" ]; then
        log_error "Missing required environment variables. Check .env file."
        exit 1
    fi
    
    log_success "Environment validation passed"
}

create_schema_file() {
    log_info "Creating BigQuery schema file..."
    
    cat > "$SCHEMA_FILE" << 'EOF'
[
    {
        "name": "provider_id",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "Hospital provider ID (6-digit CMS identifier)"
    },
    {
        "name": "hospital_name",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Hospital name"
    },
    {
        "name": "city",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Hospital city"
    },
    {
        "name": "state",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Hospital state (2-letter code)"
    },
    {
        "name": "beds",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Number of hospital beds"
    },
    {
        "name": "reporting_period_end",
        "type": "DATE",
        "mode": "NULLABLE",
        "description": "End date of reporting period"
    },
    {
        "name": "total_expenses",
        "type": "FLOAT",
        "mode": "NULLABLE",
        "description": "Total hospital expenses for reporting period"
    },
    {
        "name": "total_charges",
        "type": "FLOAT",
        "mode": "NULLABLE",
        "description": "Total hospital charges for reporting period"
    },
    {
        "name": "net_income",
        "type": "FLOAT",
        "mode": "NULLABLE",
        "description": "Net income for reporting period"
    },
    {
        "name": "patient_days",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Total patient days"
    },
    {
        "name": "discharges",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Total patient discharges"
    },
    {
        "name": "fte_employees",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Full-time equivalent employees"
    },
    {
        "name": "medicare_days",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Medicare patient days"
    },
    {
        "name": "medicaid_days",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Medicaid patient days"
    }
]
EOF
    
    log_success "Schema file created: $SCHEMA_FILE"
}

find_latest_data_file() {
    log_info "Finding latest hospital data file in GCS..."
    
    # Find the latest hospital cost sample file
    LATEST_FILE=$(gsutil ls "$GCS_BASE_PATH" | grep "hospital_cost_sample.*\.csv" | sort | tail -n 1)
    
    if [ -z "$LATEST_FILE" ]; then
        log_error "No hospital data files found in $GCS_BASE_PATH"
        exit 1
    fi
    
    log_success "Found latest file: $LATEST_FILE"
    echo "$LATEST_FILE"
}

create_optimized_table() {
    log_info "Creating optimized BigQuery table with partitioning and clustering..."
    
    # Check if table already exists
    if bq show "$FULL_TABLE_ID" &>/dev/null; then
        log_warning "Table $FULL_TABLE_ID already exists"
        read -p "Do you want to replace it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deleting existing table..."
            bq rm -f "$FULL_TABLE_ID"
            log_success "Existing table deleted"
        else
            log_error "Load cancelled by user"
            exit 1
        fi
    fi
    
    # Create table with partitioning and clustering
    log_info "Creating table with:"
    log_info "  📅 Partitioned by: reporting_period_end (DATE)"
    log_info "  🏷️  Clustered by: provider_id"
    
    bq mk \
        --table \
        --schema="$SCHEMA_FILE" \
        --time_partitioning_field=reporting_period_end \
        --time_partitioning_type=DAY \
        --clustering_fields=provider_id \
        --description="Staging table for hospital cost report data with optimized partitioning and clustering" \
        "${DATASET_ID}.${TABLE_ID}"
    
    if [ $? -eq 0 ]; then
        log_success "Optimized table created successfully"
        
        # Show table details
        log_info "Table configuration:"
        bq show --format=prettyjson "$FULL_TABLE_ID" | \
            grep -E '"timePartitioning"|"clustering"|"type"|"field"' | \
            head -10
    else
        log_error "Failed to create table"
        exit 1
    fi
}

load_data_to_bigquery() {
    local source_file="$1"
    
    log_info "Starting BigQuery load operation..."
    log_info "Source: $source_file"
    log_info "Target: $FULL_TABLE_ID (partitioned table)"
    
    # Start timing
    START_TIME=$(date +%s)
    
    # Execute bq load command (append to pre-created table)
    bq load \
        --source_format=CSV \
        --skip_leading_rows=1 \
        --replace=false \
        --project_id="$PROJECT_ID" \
        "$FULL_TABLE_ID" \
        "$source_file"
    
    # Check exit status
    if [ $? -eq 0 ]; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        log_success "Data loaded successfully in ${DURATION} seconds"
        log_info "Data automatically distributed across partitions by reporting_period_end"
    else
        log_error "BigQuery load failed"
        exit 1
    fi
}

verify_load() {
    log_info "Verifying data load..."
    
    # Get table info
    ROW_COUNT=$(bq query --use_legacy_sql=false --format=csv --quiet \
        "SELECT COUNT(*) as row_count FROM \`$FULL_TABLE_ID\`" | tail -n +2)
    
    TABLE_SIZE=$(bq show --format=prettyjson "$FULL_TABLE_ID" | \
        grep -o '"numBytes": "[^"]*"' | cut -d'"' -f4)
    
    log_success "Table verification complete:"
    log_info "  📊 Rows loaded: $ROW_COUNT"
    log_info "  💾 Table size: $TABLE_SIZE bytes"
    
    # Show sample data
    log_info "Sample data preview:"
    bq query --use_legacy_sql=false --format=table --quiet \
        "SELECT provider_id, hospital_name, city, state, beds, total_expenses 
         FROM \`$FULL_TABLE_ID\` 
         LIMIT 5"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    [ -f "$SCHEMA_FILE" ] && rm "$SCHEMA_FILE"
    log_success "Cleanup complete"
}

print_summary() {
    echo "=========================================================="
    echo "📋 BigQuery Load Summary"
    echo "=========================================================="
    echo "✅ Table: $FULL_TABLE_ID"
    echo "✅ Schema: 14 columns defined"
    echo "✅ Method: bq load command (shell script)"
    echo "✅ Format: CSV with header row"
    echo "✅ Status: Load completed successfully"
    echo "=========================================================="
    echo "🎯 Next steps:"
    echo "   - Implement Python API load (Option 2)"
    echo "   - Implement Transfer Service (Option 3)"
    echo "   - Compare performance metrics"
    echo "=========================================================="
}

#####################################################################
# Main execution
#####################################################################

main() {
    print_header
    
    # Validate environment and dependencies
    validate_environment
    
    # Create schema file
    create_schema_file
    
    # Find the latest data file
    SOURCE_FILE=$(find_latest_data_file)
    
    # Create optimized table with partitioning and clustering
    create_optimized_table
    
    # Load data to BigQuery
    load_data_to_bigquery "$SOURCE_FILE"
    
    # Verify the load
    verify_load
    
    # Clean up
    cleanup
    
    # Print summary
    print_summary
}

# Handle script termination
trap cleanup EXIT

# Run main function
main "$@"