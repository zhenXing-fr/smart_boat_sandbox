#!/bin/bash

# This script starts the vessel sailing data producer

set -e

# Check if services are running
if ! docker ps | grep -q "zookeeper"; then
  echo "Starting infrastructure services..."
  cd "$(dirname "$0")/.."
  
  # Check if network exists
  if ! docker network ls | grep -q "maritime-network"; then
    echo "Creating maritime-network..."
    docker network create maritime-network
  fi
  
  # Start infrastructure
  docker-compose -f docker/docker-compose.yml up -d
  
  # Wait for services to be ready
  echo "Waiting for Kafka to be ready..."
  while ! docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --list >/dev/null 2>&1; do
    echo "Waiting for Kafka to be ready..."
    sleep 2
  done
  
  echo "Waiting for Schema Registry to be ready..."
  while ! curl -s http://localhost:8081/subjects >/dev/null 2>&1; do
    echo "Waiting for Schema Registry to be ready..."
    sleep 2
  done
  
  echo "Infrastructure is ready!"
else
  echo "Infrastructure services are already running."
fi

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

# Check for dependencies
if ! python -c "import maritime_rl" >/dev/null 2>&1; then
  echo "Installing dependencies..."
  uv pip install -e .
fi

# Create required topics if they don't exist
echo "Checking Kafka topics..."
docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic vessel_sailing_data --partitions 3 --replication-factor 1
docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic processed_sailing_data --partitions 3 --replication-factor 1
docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic data_quality_alerts --partitions 1 --replication-factor 1

# Check command line arguments
VESSELS=${1:-3}
INTERVAL=${2:-0.5}
ITERATIONS=${3:-0}
SLEEP=${4:-1.0}

echo "Starting sailing data producer with $VESSELS vessels..."
echo "Press Ctrl+C to stop"

# Start the producer
python -m src.maritime_rl.producers.sailing_producer \
  --vessels $VESSELS \
  --interval $INTERVAL \
  --iterations $ITERATIONS \
  --sleep $SLEEP \
  --bootstrap-servers localhost:9093 \
  --schema-registry-url http://localhost:8081 