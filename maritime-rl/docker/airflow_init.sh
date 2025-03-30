#!/bin/bash
# This script ensures that Airflow containers have kafka-python installed

echo "Waiting for Airflow containers to be ready..."
sleep 10

# Get all Airflow container IDs
AIRFLOW_CONTAINERS=$(docker ps | grep airflow | grep -v postgres | awk '{print $1}')

for CONTAINER_ID in $AIRFLOW_CONTAINERS; do
  CONTAINER_NAME=$(docker inspect --format='{{.Name}}' $CONTAINER_ID | sed 's/\///')
  echo "Installing kafka-python in $CONTAINER_NAME..."
  
  # Install kafka-python in the container
  docker exec $CONTAINER_ID pip install kafka-python==2.1.4
  
  if [ $? -eq 0 ]; then
    echo "Successfully installed kafka-python in $CONTAINER_NAME"
  else
    echo "Failed to install kafka-python in $CONTAINER_NAME"
  fi
done

echo "Checking if DAGs can import kafka module..."
for CONTAINER_ID in $AIRFLOW_CONTAINERS; do
  CONTAINER_NAME=$(docker inspect --format='{{.Name}}' $CONTAINER_ID | sed 's/\///')
  echo "Testing kafka import in $CONTAINER_NAME..."
  
  # Test if kafka module can be imported
  docker exec $CONTAINER_ID python -c "import kafka; print('Kafka module available in', '$CONTAINER_NAME')"
done

echo "Initialization complete. Airflow should now have kafka-python installed." 