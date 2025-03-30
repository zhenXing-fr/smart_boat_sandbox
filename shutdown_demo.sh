#!/bin/bash
# Script to shut down all Maritime Route Optimization demo components

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARITIME_DIR="${SCRIPT_DIR}/maritime-rl"

echo "=== SHUTTING DOWN MARITIME ROUTE OPTIMIZATION DEMO ==="

# First stop any running demo processes
echo "Stopping any running Python processes..."
pkill -f "python -m src.maritime"

# Kill the dashboard process
echo "Stopping dashboard..."
pkill -f "python -m src.maritime.visualization.dashboard"

# Stop Docker containers
echo "Stopping Docker containers..."
if [ -f "${MARITIME_DIR}/docker-compose.yml" ]; then
    cd "${MARITIME_DIR}" && docker-compose down
else
    # Try from the main directory
    cd "${SCRIPT_DIR}" && docker-compose down
fi

echo "Checking for any remaining containers..."
# Get list of containers with maritime or airflow in their name
CONTAINERS=$(docker ps -a | grep -E 'maritime|airflow|timescale|kafka' | awk '{print $1}')

if [ -n "$CONTAINERS" ]; then
    echo "Stopping remaining containers..."
    docker stop $CONTAINERS
    docker rm $CONTAINERS
fi

# Stop any running data generator
if [ -f "$MARITIME_DIR/logs/data_generator.pid" ]; then
    GENERATOR_PID=$(cat "$MARITIME_DIR/logs/data_generator.pid" | awk '{print $2}')
    if [ -n "$GENERATOR_PID" ]; then
        echo "Stopping data generator (PID: $GENERATOR_PID)..."
        kill -9 $GENERATOR_PID 2>/dev/null || echo "Process already stopped"
        rm "$MARITIME_DIR/logs/data_generator.pid"
    fi
fi

echo "Cleanup complete. All components have been shut down." 