#!/bin/bash
# Wrapper script to start the Maritime Route Optimization Dashboard

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MARITIME_DIR="${PROJECT_ROOT}/maritime-rl"

echo "Starting Maritime Route Optimization Dashboard from ${MARITIME_DIR}..."

if [ ! -f "${MARITIME_DIR}/scripts/start_dashboard.sh" ]; then
    echo "Error: Dashboard script not found at ${MARITIME_DIR}/scripts/start_dashboard.sh"
    exit 1
fi

# Change to the maritime-rl directory and run the dashboard
cd "${MARITIME_DIR}" && ./scripts/start_dashboard.sh 