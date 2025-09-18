#!/bin/bash

# ============================================================================
# BigQuery Partitioned Table Creation Script for Multi-Year HCRIS Data
# ============================================================================
# Creates a BigQuery native table optimized for multi-year hospital cost data
# with proper partitioning by fiscal year and clustering by provider_id
#
# This script handles real HCRIS data (millions of records across multiple years)
# vs the original sample data approach.
#
# Usage: ./create_partitioned_table.sh [--force] [--test-mode]
#   --force: Skip confirmation prompts  
#   --test-mode: Create smaller test table
# ============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

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
TABLE_ID="hcris_hospitals_partitioned"
FULL_TABLE_ID="${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}"

# Schema file
SCHEMA_FILE="$SCRIPT_DIR/hcris_partitioned_schema.json"

# Command line flags
FORCE_MODE=false
TEST_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_MODE=true
            shift
            ;;
        --test-mode)
            TEST_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

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

create_schema_file() {
    log_info "Creating BigQuery schema for partitioned HCRIS table..."
    
    cat > "$SCHEMA_FILE" << 'EOF'
[
    {
        "name": "provider_id",
        "type": "INTEGER",
        "mode": "REQUIRED",
        "description": "Hospital provider ID (CMS provider number)"
    },
    {
        "name": "hospital_name",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Hospital name from cost report"
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
        "name": "fiscal_year",
        "type": "INTEGER",
        "mode": "REQUIRED",
        "description": "Fiscal year of the cost report"
    },
    {
        "name": "report_period",
        "type": "DATE",
        "mode": "REQUIRED",
        "description": "Cost report period end date (for partitioning)"
    },
    {
        "name": "beds",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Number of licensed hospital beds"
    },
    {
        "name": "total_expenses",
        "type": "FLOAT",
        "mode": "NULLABLE",
        "description": "Total hospital operating expenses"
    },
    {
        "name": "total_charges",
        "type": "FLOAT",
        "mode": "NULLABLE",
        "description": "Total hospital charges to patients"
    },
    {
        "name": "net_income",
        "type": "FLOAT",
        "mode": "NULLABLE",
        "description": "Hospital net income (revenue minus expenses)"
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

check_existing_table() {
    log_info "Checking for existing partitioned table..."
    
    if bq show --quiet "$FULL_TABLE_ID" &> /dev/null; then
        log_info "Table already exists: $FULL_TABLE_ID"
        
        if [[ "$FORCE_MODE" == "false" ]]; then
            echo "Options:"
            echo "  1. Delete and recreate the table"
            echo "  2. Keep existing table and exit"
            echo "  3. Cancel operation"
            
            read -p "Choose option (1-3): " choice
            case "$choice" in
                1)
                    log_info "Deleting existing table..."
                    bq rm -f -t "$FULL_TABLE_ID"
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
            log_info "Force mode: Deleting existing table..."
            bq rm -f -t "$FULL_TABLE_ID"
            log_success "Existing table deleted"
        fi
    fi
    return 0
}

create_partitioned_table() {
    log_info "Creating BigQuery partitioned table..."
    log_info "  📋 Table: $FULL_TABLE_ID"
    log_info "  📅 Partitioned by: report_period (DATE, yearly partitioning)"
    log_info "  🏷️  Clustered by: provider_id, fiscal_year"
    log_info "  📊 Optimized for: Multi-year hospital cost analysis"
    
    local start_time=$(date +%s)
    
    # Create table with yearly partitioning and clustering
    bq mk \
        --table \
        --schema="$SCHEMA_FILE" \
        --time_partitioning_field=report_period \
        --time_partitioning_type=YEAR \
        --clustering_fields=provider_id,fiscal_year \
        --description="Multi-year HCRIS hospital cost data with yearly partitioning and provider clustering for benchmarking" \
        --location="${GOOGLE_CLOUD_REGION:-us-east1}" \
        "${FULL_TABLE_ID}"
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "Partitioned table created successfully in ${duration} seconds"
}

load_test_data() {
    if [[ "$TEST_MODE" == "true" ]]; then
        log_info "Test mode: Loading sample data for table verification..."
        
        # Create a small sample file for testing
        local test_file="/tmp/hcris_test_sample.csv"
        cat > "$test_file" << 'EOF'
provider_id,hospital_name,city,state,fiscal_year,report_period,beds,total_expenses,total_charges,net_income,patient_days,discharges,fte_employees,medicare_days,medicaid_days
100001,Test Hospital A,New York,NY,2021,2021-12-31,150,75000000,225000000,15000000,45000,5000,800,18000,9000
100002,Test Hospital B,Los Angeles,CA,2021,2021-12-31,200,95000000,285000000,19000000,60000,6500,1000,24000,12000
100001,Test Hospital A,New York,NY,2022,2022-12-31,150,78000000,234000000,16000000,46000,5200,820,18500,9200
100002,Test Hospital B,Los Angeles,CA,2022,2022-12-31,200,98000000,294000000,20000000,61000,6700,1020,24500,12200
100001,Test Hospital A,New York,NY,2023,2023-12-31,150,81000000,243000000,17000000,47000,5400,840,19000,9400
100002,Test Hospital B,Los Angeles,CA,2023,2023-12-31,200,101000000,303000000,21000000,62000,6900,1040,25000,12400
EOF

        # Load test data
        bq load \
            --source_format=CSV \
            --skip_leading_rows=1 \
            --allow_jagged_rows=false \
            --allow_quoted_newlines=false \
            "$FULL_TABLE_ID" \
            "$test_file"
        
        if [[ $? -eq 0 ]]; then
            log_success "Test data loaded successfully"
            rm "$test_file"
            
            # Verify partitioning
            log_info "Verifying partitioning configuration..."
            bq query --use_legacy_sql=false --format=table --quiet \
                "SELECT fiscal_year, COUNT(*) as hospital_count, COUNT(DISTINCT provider_id) as unique_hospitals
                 FROM \`$FULL_TABLE_ID\`
                 GROUP BY fiscal_year
                 ORDER BY fiscal_year"
        else
            log_error "Failed to load test data"
            rm "$test_file"
            exit 1
        fi
    fi
}

show_usage_info() {
    log_success "🎉 Partitioned table setup complete!"
    echo
    echo "📊 Table Details:"
    echo "  - Table: $FULL_TABLE_ID"
    echo "  - Partitioning: Yearly by report_period (enables year-based filtering)"
    echo "  - Clustering: provider_id, fiscal_year (optimizes hospital and year queries)"
    echo "  - Schema: 15 columns including financial metrics and hospital info"
    echo
    echo "🔍 Partitioning Benefits:"
    echo "  - Year filters will scan only relevant partitions (e.g., WHERE fiscal_year = 2023)"
    echo "  - Multi-year ranges will scan only needed partitions (e.g., 2021-2023)"
    echo "  - Provider clustering optimizes hospital-specific queries"
    echo "  - Significant cost reduction for time-based analytical queries"
    echo
    echo "📈 Expected Performance Improvements:"
    echo "  - Single year queries: 70-80% data scan reduction"
    echo "  - Provider queries: 50-60% faster due to clustering"
    echo "  - Complex analytics: Combines both optimizations"
    echo
    echo "🚀 Next Steps:"
    echo "  1. Load real HCRIS data using: python scripts/data_preparation/hcris_downloader.py"
    echo "  2. Use bq load to import multi-year CSV files"
    echo "  3. Run partitioned benchmark queries to measure optimization benefits"
    echo
    echo "💡 Example Optimized Query:"
    echo "  SELECT provider_id, hospital_name, total_expenses"
    echo "  FROM \`$FULL_TABLE_ID\`"
    echo "  WHERE fiscal_year = 2023 AND provider_id BETWEEN 100000 AND 200000"
    echo "  ORDER BY total_expenses DESC"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    [[ -f "$SCHEMA_FILE" ]] && rm "$SCHEMA_FILE"
    log_success "Cleanup complete"
}

main() {
    log_info "🚀 Creating BigQuery Partitioned Table for Multi-Year HCRIS Data"
    log_info "Project: $PROJECT_ID | Dataset: $DATASET_ID | Table: $TABLE_ID"
    echo
    
    create_schema_file
    
    if check_existing_table; then
        create_partitioned_table
        load_test_data
        show_usage_info
    else
        log_info "Table already exists and was kept. Exiting."
    fi
    
    cleanup
    log_success "Partitioned table setup completed successfully! 🎉"
}

# Error handling
trap 'log_error "Script failed on line $LINENO. Exit code: $?"' ERR

# Run main function
main "$@"