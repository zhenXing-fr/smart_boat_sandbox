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

log_warning "This script will stop and remove the TimescaleDB container and its volume."
read -p "Are you sure you want to proceed? (y/n): " proceed

if [[ "$proceed" != "y" ]]; then
    log_status "Operation canceled."
    exit 0
fi

log_status "Stopping TimescaleDB container..."
docker-compose -f docker/docker-compose.yml stop timescaledb

log_status "Removing TimescaleDB container..."
docker-compose -f docker/docker-compose.yml rm -f timescaledb

log_status "Removing TimescaleDB volume..."
docker volume rm timescaledb-data || {
    log_error "Failed to remove volume, it might be in use."
    log_warning "Try running: docker volume rm -f timescaledb-data"
}

log_status "Checking for TimescaleDB PostGIS image..."
if ! docker images | grep -q "timescale/timescaledb-postgis"; then
    log_status "Pulling TimescaleDB PostGIS image..."
    docker pull timescale/timescaledb-postgis:latest-pg15
fi

log_status "TimescaleDB has been reset."
log_status "Run the start_services_sequential.sh script to start TimescaleDB again." 