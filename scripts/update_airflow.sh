#!/bin/bash
# Script to update Airflow container with latest requirements

echo "Updating Airflow container with latest requirements..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MARITIME_DIR="${PROJECT_ROOT}/maritime-rl"

# Copy requirements.txt to airflow container
echo "Copying requirements.txt to Airflow container..."
docker cp "${MARITIME_DIR}/requirements.txt" airflow-webserver:/tmp/requirements.txt

# Install requirements in airflow container
echo "Installing requirements in Airflow container..."
docker exec -it airflow-webserver pip install -r /tmp/requirements.txt

# Copy updated DAG files to airflow container
echo "Copying updated DAG files to Airflow container..."
docker exec -it airflow-webserver mkdir -p /opt/airflow/dags
docker cp "${MARITIME_DIR}/dags/" airflow-webserver:/opt/airflow/

echo "Airflow update completed. Restart your DAGs in the Airflow UI." 