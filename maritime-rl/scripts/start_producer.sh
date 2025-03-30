#!/bin/bash

# This script starts the vessel sailing data producer

set -e

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
  echo "Creating .env file from .env.example..."
  cp .env.example .env
fi

# Check if Docker Compose is running
if ! docker-compose -f docker/docker-compose.yml ps | grep -q "Up"; then
  echo "Starting Kafka and dependencies with Docker Compose..."
  docker-compose -f docker/docker-compose.yml up -d
  
  # Wait for Kafka to be ready
  echo "Waiting for Kafka to be ready..."
  sleep 10
fi

# Run the sailing data producer
echo "Starting sailing data producer..."
python -m src.maritime_rl.producers.sailing_producer "$@" 