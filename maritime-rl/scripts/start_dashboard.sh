#!/bin/bash

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
  echo "Virtual environment is not activated. Activating..."
  if [ -d ".venv" ]; then
    source .venv/bin/activate
  else
    echo "Virtual environment .venv not found. Please create it first."
    exit 1
  fi
fi

# Check dependencies
if ! python -c "import flask" >/dev/null 2>&1; then
  echo "Installing Flask and other visualization dependencies..."
  pip install flask pandas psycopg2-binary matplotlib
fi

# Check if TimescaleDB is running
if ! docker ps | grep -q "timescaledb"; then
  echo "Note: TimescaleDB is not running. Dashboard will use mock data."
fi

# Check if Kafka is running
if ! docker ps | grep -q "kafka"; then
  echo "Note: Kafka is not running. Dashboard will use mock data."
fi

# Start the dashboard
echo "Starting Maritime Route Optimization Dashboard..."
echo "Access the dashboard at http://localhost:5000"
echo "Press Ctrl+C to stop"

# Set the PYTHONPATH to include the src directory
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run the dashboard
python -m src.maritime_rl.visualization.dashboard 