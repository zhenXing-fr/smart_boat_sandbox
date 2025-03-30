#!/bin/bash

# Color variables
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function log_status {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warning {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function log_error {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if TimescaleDB is running
if ! docker ps | grep -q timescaledb; then
    log_error "TimescaleDB is not running. Please start it first using start_services_sequential.sh"
    exit 1
fi

log_status "Checking database tables in TimescaleDB..."

# Get list of tables
tables=$(docker exec timescaledb psql -U maritime -d maritime -t -c "\dt" 2>/dev/null)

if [ -z "$tables" ]; then
    log_warning "No tables found in TimescaleDB. Checking if initialization script ran correctly."
    
    # Check if init-db.sql exists
    if [ ! -f "./docker/init-db.sql" ]; then
        log_error "init-db.sql not found in docker directory."
        exit 1
    fi
    
    log_status "Running initialization script manually..."
    docker exec timescaledb psql -U maritime -d maritime -f /docker-entrypoint-initdb.d/init-db.sql
    
    # Check again
    tables=$(docker exec timescaledb psql -U maritime -d maritime -t -c "\dt" 2>/dev/null)
    
    if [ -z "$tables" ]; then
        log_error "Failed to create tables. Please check init-db.sql for errors."
        exit 1
    fi
fi

log_status "Tables in TimescaleDB:"
echo "$tables"

# Check for vessel_telemetry table specifically
if echo "$tables" | grep -q "vessel_telemetry"; then
    log_status "Found vessel_telemetry table. Database is ready for the demo."
else
    log_warning "vessel_telemetry table not found. The demo may not work correctly."
fi 