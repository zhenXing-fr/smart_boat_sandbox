#!/bin/bash
# Build custom Airflow image with kafka-python pre-installed

set -e

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/docker"

echo "Building custom Airflow image with kafka-python..."
cd "$DOCKER_DIR"

# Build the custom Airflow image
docker build -t maritime-airflow:latest -f Dockerfile.airflow .

echo "Custom Airflow image built successfully!"
echo "You can now start the environment with:"
echo "cd $DOCKER_DIR && docker-compose up -d" 