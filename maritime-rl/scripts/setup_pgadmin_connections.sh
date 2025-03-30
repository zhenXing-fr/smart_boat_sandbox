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

# Check if pgAdmin is running
if ! docker ps | grep -q pgadmin; then
    log_error "pgAdmin is not running. Please start it first using start_services_sequential.sh"
    exit 1
fi

log_status "pgAdmin is running, but automatic connection setup is not available."
log_status "Please set up connections manually:"
log_status "1. Open pgAdmin at http://localhost:5050"
log_status "2. Login with email: admin@maritime.com and password: maritime_admin"
log_status "3. Right-click on Servers and select Create > Server..."
log_status "4. For TimescaleDB, use these settings:"
echo -e "   ${GREEN}Name:${NC} TimescaleDB"
echo -e "   ${GREEN}Host:${NC} timescaledb"
echo -e "   ${GREEN}Port:${NC} 5432"
echo -e "   ${GREEN}Maintenance DB:${NC} maritime"
echo -e "   ${GREEN}Username:${NC} maritime"
echo -e "   ${GREEN}Password:${NC} password"
log_status "5. For Airflow Postgres, use these settings:"
echo -e "   ${GREEN}Name:${NC} Airflow Postgres"
echo -e "   ${GREEN}Host:${NC} airflow-postgres"
echo -e "   ${GREEN}Port:${NC} 5432"
echo -e "   ${GREEN}Maintenance DB:${NC} airflow"
echo -e "   ${GREEN}Username:${NC} airflow"
echo -e "   ${GREEN}Password:${NC} airflow"
log_status "Your connections should be saved in the pgAdmin volume and persist across restarts." 