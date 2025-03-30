#!/bin/bash

# This script starts Airflow services for scheduling the maritime data pipeline

set -e

# Create required directories
mkdir -p dags logs plugins

# Set Airflow UID
export AIRFLOW_UID=$(id -u)

# Create symbolic links for DAGs
if [ ! -d "dags/maritime-rl" ]; then
  echo "Creating symlink for maritime-rl DAGs..."
  mkdir -p dags
  ln -sf $(pwd)/dags dags/maritime-rl
fi

# Check if Kafka services are running
if ! docker network ls | grep -q maritime-network; then
  echo "Creating maritime-network..."
  docker network create maritime-network
fi

if ! docker-compose -f docker/docker-compose.yml ps | grep -q "Up"; then
  echo "Starting Kafka and other services with Docker Compose..."
  docker-compose -f docker/docker-compose.yml up -d
  
  # Wait for Kafka to be ready
  echo "Waiting for Kafka to be ready..."
  sleep 10
fi

# Start Airflow services
echo "Starting Airflow services..."
docker-compose -f docker/docker-compose-airflow.yml up -d

echo "Airflow services started. Access the web UI at http://localhost:8090"
echo "Username: airflow"
echo "Password: airflow" 