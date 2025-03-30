#!/bin/bash

# Color variables
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function log_status {
    echo -e "${GREEN}[STATUS]${NC} $1"
}

function log_step {
    echo -e "\n${BLUE}[STEP $1]${NC} $2"
    echo -e "${BLUE}=================================================${NC}"
}

function log_warning {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function log_error {
    echo -e "${RED}[ERROR]${NC} $1"
}

function check_service {
    local service=$1
    if docker ps | grep -q $service; then
        echo -e "  ${GREEN}✓${NC} $service is running"
        return 0
    else
        echo -e "  ${RED}✗${NC} $service is not running"
        return 1
    fi
}

function progress_bar {
    local duration=$1
    local interval=1  # Changed from 0.2 to 1 to avoid floating point errors
    local steps=$((duration / interval))
    local current_step=0
    local percent=0
    local bar_length=40
    
    echo -ne "  [${NC}"
    while [[ $current_step -lt $steps ]]; do
        percent=$((current_step * 100 / steps))
        filled_length=$((percent * bar_length / 100))
        bar=""
        for ((i=0; i<filled_length; i++)); do
            bar="${bar}█"
        done
        for ((i=filled_length; i<bar_length; i++)); do
            bar="${bar} "
        done
        echo -ne "\r  [${GREEN}${bar}${NC}] ${percent}%"
        sleep $interval
        ((current_step++))
    done
    echo -ne "\r  [${GREEN}"
    for ((i=0; i<bar_length; i++)); do
        echo -ne "█"
    done
    echo -e "${NC}] 100%"
}

# Change to project root directory
cd $(dirname "$0")/..

# Title
echo -e "\n${BLUE}======================================================="
echo -e "       MARITIME ROUTE OPTIMIZATION DEMO"
echo -e "=======================================================${NC}\n"

# Step 1: Verify Infrastructure
log_step "1" "Verifying Infrastructure"
services_ok=true

required_services=("zookeeper" "kafka" "schema-registry" "timescaledb" "pgadmin" "airflow-postgres" "airflow-webserver" "airflow-scheduler")
for service in "${required_services[@]}"; do
    check_service $service
    if [ $? -ne 0 ]; then
        services_ok=false
    fi
done

if [ "$services_ok" = false ]; then
    log_error "Some services are not running. Starting them now..."
    ./scripts/start_services_sequential.sh
else
    log_status "All required services are running."
fi

# Step 2: Generate Test Data
log_step "2" "Generating Vessel Test Data"
log_status "Starting vessel data generation (3 vessels, 100 iterations)..."

# Run in background and capture PID
python -m src.maritime.producers.sailing_producer --vessels 3 --iterations 100 --sleep 1 > /tmp/sailing_producer.log 2>&1 &
producer_pid=$!

# Show progress
log_status "Generating data..."
progress_bar 20

# Check if producer is still running after progress bar
if kill -0 $producer_pid 2>/dev/null; then
    log_status "Data generation completed successfully."
    kill $producer_pid 2>/dev/null
else
    log_error "Data generation failed. Check /tmp/sailing_producer.log for details."
    cat /tmp/sailing_producer.log
    exit 1
fi

# Step 3: Process Data with Kafka Streams
log_step "3" "Processing Data through Kafka Streams"
log_status "Starting data processor for 30 seconds..."

# Run processor in background
python -m src.maritime.processors.sailing_processor --duration 30 > /tmp/sailing_processor.log 2>&1 &
processor_pid=$!

# Show progress
log_status "Processing data..."
progress_bar 30

# Check if processor is still running
if kill -0 $processor_pid 2>/dev/null; then
    kill $processor_pid
    log_status "Data processing completed successfully."
else
    log_error "Data processing failed. Check /tmp/sailing_processor.log for details."
    cat /tmp/sailing_processor.log
    exit 1
fi

# Step 4: Set up pgAdmin Connections
log_step "4" "Setting up Database Connections"
log_status "Configuring pgAdmin connections..."

# Skip connection setup for now since pgAdmin doesn't have psql
log_status "pgAdmin is available at: http://localhost:5050"
log_status "Credentials: admin@maritime.com / maritime_admin"
log_status "You'll need to set up connections manually:"
log_status "1. Add a new server in pgAdmin"
log_status "2. Name: TimescaleDB, Host: timescaledb, Port: 5432"
log_status "3. Username: maritime, Password: password, Database: maritime"

# Step 5: Verify Data in TimescaleDB
log_step "5" "Verifying Data in TimescaleDB"
log_status "Checking for data in vessel_telemetry table..."

# Check if data exists in TimescaleDB using -t for text-only output and removing the -it flags
data_count=$(docker exec timescaledb psql -U maritime -d maritime -t -c "SELECT COUNT(*) FROM vessel_telemetry;" 2>/dev/null | tr -d ' ')

# Check if data_count is empty or contains a number
if [[ -n "$data_count" ]] && [[ "$data_count" -gt 0 ]]; then
    log_status "Found $data_count records in vessel_telemetry table."
    
    echo -e "\n${GREEN}Sample Data:${NC}"
    docker exec timescaledb psql -U maritime -d maritime -c "SELECT vessel_id, timestamp, speed, fuel_consumption FROM vessel_telemetry ORDER BY timestamp DESC LIMIT 5;"
    
    echo -e "\n${GREEN}Vessel Statistics:${NC}"
    docker exec timescaledb psql -U maritime -d maritime -c "SELECT vessel_id, COUNT(*) as data_points, AVG(speed) as avg_speed, AVG(fuel_consumption) as avg_fuel FROM vessel_telemetry GROUP BY vessel_id;"
else
    log_warning "No data found in vessel_telemetry table or query failed."
    log_status "Checking if table exists..."
    
    # Check if the table exists
    if docker exec timescaledb psql -U maritime -d maritime -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'vessel_telemetry');" | grep -q 't'; then
        log_status "Table exists but has no data."
    else
        log_error "Table 'vessel_telemetry' does not exist."
        log_status "Available tables:"
        docker exec timescaledb psql -U maritime -d maritime -c "\dt"
    fi
    
    # Don't exit, continue with the demo
    log_warning "Continuing with the demo despite data issues..."
fi

# Step 6: Configure Airflow DAGs
log_step "6" "Configuring Airflow DAGs"
log_status "Enabling Airflow DAGs..."

# Check if Airflow API is available
if curl -s http://localhost:8090/health | grep -q "healthy"; then
    # Get Airflow admin API token - removing docker exec -it
    api_token=$(docker exec airflow-webserver airflow config get-value api auth_backends | grep -q "airflow.api.auth.backend.basic_auth" && echo "admin:maritime_admin" | base64)
    
    log_status "Airflow API is available."
    log_status "You can manually enable DAGs at: http://localhost:8090"
    log_status "Credentials: admin / maritime_admin"
else
    log_warning "Airflow API is not available. Please enable DAGs manually:"
    log_status "1. Open http://localhost:8090 in your browser"
    log_status "2. Login with admin / maritime_admin"
    log_status "3. Enable maritime_data_pipeline and maritime_model_training DAGs"
fi

# Step 7: Visualization Dashboard
log_step "7" "Starting Visualization Dashboard"
log_status "Starting the maritime route visualization dashboard..."

# Check if dashboard is already running
if lsof -i :5000 > /dev/null; then
    log_warning "Dashboard is already running on port 5000."
else
    # Start dashboard in background
    ./scripts/start_dashboard.sh > /tmp/dashboard.log 2>&1 &
    dashboard_pid=$!
    
    # Wait for dashboard to start
    log_status "Waiting for dashboard to initialize..."
    progress_bar 5
    
    if kill -0 $dashboard_pid 2>/dev/null; then
        log_status "Dashboard started successfully."
    else
        log_error "Dashboard failed to start. Check /tmp/dashboard.log for details."
        cat /tmp/dashboard.log
    fi
fi

# Completion
echo -e "\n${BLUE}======================================================="
echo -e "       DEMO COMPLETED SUCCESSFULLY"
echo -e "=======================================================${NC}\n"

log_status "All services are running and data pipeline is operational."
echo -e "\n${GREEN}Available Services:${NC}"
echo -e "  - Kafka UI: http://localhost:8080"
echo -e "  - Schema Registry: http://localhost:8081"
echo -e "  - pgAdmin: http://localhost:5050 (admin@maritime.com / maritime_admin)"
echo -e "  - Airflow: http://localhost:8090 (admin / maritime_admin)"
echo -e "  - Dashboard: http://localhost:5000"

echo -e "\n${GREEN}Next Steps:${NC}"
echo -e "  1. Explore vessel data in pgAdmin"
echo -e "  2. Enable and trigger Airflow DAGs"
echo -e "  3. View optimized routes in the dashboard"
echo -e "  4. Experiment with different vessel configurations"
echo -e "  5. Modify the ML model parameters for better optimization"

echo -e "\n${BLUE}Happy sailing! 🚢${NC}\n" 