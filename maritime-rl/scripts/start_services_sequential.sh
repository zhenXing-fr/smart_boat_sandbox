#!/bin/bash

# Set script to exit on error
set -e

# Color variables
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to display status messages
function log_status {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warning {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function log_error {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for service to be healthy
wait_for_service() {
    local service=$1
    local max_attempts=$2
    local attempt=1
    
    log_status "Waiting for $service to be healthy..."
    
    while [ $attempt -le $max_attempts ]; do
        if AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml ps $service | grep -q "(healthy)"; then
            log_status "$service is healthy!"
            return 0
        fi
        
        log_warning "Attempt $attempt/$max_attempts: $service is not healthy yet, waiting 10 seconds..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    log_error "$service is not healthy after $max_attempts attempts"
    return 1
}

# Create maritime-network if it doesn't exist
if ! docker network ls | grep -q maritime-network; then
    log_status "Creating maritime-network..."
    docker network create maritime-network
fi

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

log_status "Starting services one by one..."

# 1. Start Zookeeper
log_status "1. Starting Zookeeper..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d zookeeper
wait_for_service zookeeper 12

# 2. Start Kafka after Zookeeper is healthy
log_status "2. Starting Kafka..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d kafka
wait_for_service kafka 15

# 3. Start Schema Registry after Kafka is healthy
log_status "3. Starting Schema Registry..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d schema-registry
wait_for_service schema-registry 12

# 4. Start Kafka UI after Schema Registry is healthy
log_status "4. Starting Kafka UI..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d kafka-ui

# 5. Start TimescaleDB
log_status "5. Starting TimescaleDB..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d timescaledb
log_status "Waiting for TimescaleDB to initialize (this may take a while)..."
wait_for_service timescaledb 20

# Check if TimescaleDB is still not healthy
if ! AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml ps timescaledb | grep -q "(healthy)"; then
    log_warning "TimescaleDB is still not reporting as healthy. Attempting to manually verify..."
    if docker exec -it timescaledb pg_isready -U maritime -d maritime; then
        log_status "TimescaleDB is actually responding, proceeding with startup sequence..."
    else
        log_error "TimescaleDB is not responding. Showing recent logs:"
        docker logs timescaledb --tail 50
        log_warning "You may need to fix issues with TimescaleDB before proceeding."
        read -p "Do you want to continue anyway? (y/n): " continue_choice
        if [[ "$continue_choice" != "y" ]]; then
            log_error "Exiting script. Try fixing TimescaleDB issues first."
            exit 1
        fi
    fi
fi

# 5b. Start pgAdmin
log_status "5b. Starting pgAdmin..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d pgadmin
log_status "Waiting for pgAdmin to initialize..."
wait_for_service pgadmin 15

# 6. Start Airflow Postgres
log_status "6. Starting Airflow Postgres..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d airflow-postgres
wait_for_service airflow-postgres 12

# 7. Run Airflow initialization
log_status "7. Initializing Airflow..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up --no-deps airflow-init

# 8. Start Airflow services
log_status "8. Starting Airflow webserver and scheduler..."
AIRFLOW_UID=${AIRFLOW_UID} docker-compose -f docker/docker-compose.yml up -d airflow-webserver airflow-scheduler

log_status "All services started in the proper order!"
log_status "Services are available at:"
echo -e "${GREEN}- Kafka UI:${NC} http://localhost:8080"
echo -e "${GREEN}- Schema Registry:${NC} http://localhost:8081"
echo -e "${GREEN}- Airflow UI:${NC} http://localhost:8090 (username: admin, password: maritime_admin)"
echo -e "${GREEN}- TimescaleDB:${NC} localhost:5432 (username: maritime, password: password, database: maritime)"
echo -e "${GREEN}- pgAdmin:${NC} http://localhost:5050 (email: admin@maritime.com, password: maritime_admin)"
echo ""
log_status "You can now run data producers and the visualization dashboard." 