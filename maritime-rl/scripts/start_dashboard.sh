#!/bin/bash
# Start the Maritime Route Optimization Dashboard with real data configuration

echo "Starting Maritime Route Optimization Dashboard..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if running inside Docker or locally
if [ -f "/.dockerenv" ]; then
    # Running inside Docker
    export DB_HOST="timescaledb"
    export KAFKA_BOOTSTRAP_SERVERS="kafka:9092"
    echo "Running in Docker environment - connecting to service names"
else
    # Running locally
    export DB_HOST="localhost"
    export KAFKA_BOOTSTRAP_SERVERS="localhost:9093"
    echo "Running in local environment - connecting to localhost"
fi

# Database connection
export DB_PORT="5432"
export DB_USER="maritime"
export DB_PASSWORD="password"
export DB_NAME="maritime"
export PROCESSED_TOPIC="processed_sailing_data"

# Set to true to allow mock data when DB is unavailable
# Set to false in production to see real data only
export USE_MOCK_DATA="false"

# Start the dashboard application
cd "$PROJECT_ROOT"
python -m src.maritime.visualization.dashboard
