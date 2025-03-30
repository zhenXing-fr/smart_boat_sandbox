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

# Check if AIRFLOW_UID is set
if [ -z "$AIRFLOW_UID" ]; then
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        export AIRFLOW_UID=$(id -u)
        log_status "Set AIRFLOW_UID to $AIRFLOW_UID"
    else
        # On macOS, set to a default value that works
        export AIRFLOW_UID=50000
        log_status "Set AIRFLOW_UID to default value of 50000 for macOS"
    fi
fi

# Export AIRFLOW_UID to ensure it's available for all docker-compose commands
export AIRFLOW_UID

# Create necessary directories for Airflow if they don't exist
mkdir -p docker/airflow/logs docker/airflow/plugins

# Change to project root
cd $(dirname "$0")/..

log_status "Stopping Airflow services..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml stop airflow-webserver airflow-scheduler airflow-init

log_status "Removing Airflow containers..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml rm -f airflow-webserver airflow-scheduler airflow-init

log_status "Starting Airflow initialization..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up --no-deps airflow-init

# Check if initialization was successful
if [ $? -eq 0 ]; then
    log_status "Starting Airflow webserver and scheduler..."
    AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d airflow-webserver airflow-scheduler
    
    log_status "Airflow services restarted successfully!"
    log_status "Airflow UI is available at: http://localhost:8090 (username: admin, password: maritime_admin)"
else
    log_error "Airflow initialization failed. Check the logs for details."
    exit 1
fi 