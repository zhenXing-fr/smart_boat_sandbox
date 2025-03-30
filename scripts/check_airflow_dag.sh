#!/bin/bash
# Script to check if Airflow DAGs can import the kafka module

echo "Checking Airflow DAG compatibility..."

# Check if Airflow is running
AIRFLOW_WEBSERVER=$(docker ps | grep airflow-webserver | awk '{print $1}')

if [ -z "$AIRFLOW_WEBSERVER" ]; then
    echo "ERROR: Airflow webserver is not running!"
    echo "Please start the services first."
    exit 1
fi

# Check if kafka-python is installed
echo "Checking if kafka-python is installed..."
if ! docker exec $AIRFLOW_WEBSERVER pip freeze | grep -q kafka-python; then
    echo "WARNING: kafka-python is not installed in Airflow webserver container."
    echo "Installing now..."
    docker exec $AIRFLOW_WEBSERVER pip install kafka-python==2.1.4
else
    echo "kafka-python is installed."
fi

# Create a test file to check imports
echo "Creating a test file to check imports..."
TEST_FILE_CONTENT="
import os
import sys

try:
    import kafka
    print('SUCCESS: kafka module can be imported!')
except ImportError as e:
    print(f'ERROR: {e}')
    sys.exit(1)

print('All required modules are available!')
"

# Copy test file to Airflow webserver
echo "$TEST_FILE_CONTENT" > /tmp/airflow_test.py
docker cp /tmp/airflow_test.py $AIRFLOW_WEBSERVER:/opt/airflow/airflow_test.py

# Run the test
echo "Testing module imports in Airflow environment..."
docker exec $AIRFLOW_WEBSERVER python /opt/airflow/airflow_test.py

if [ $? -eq 0 ]; then
    echo "✅ Airflow environment is properly configured for DAGs."
    echo "You can now enable and trigger the maritime DAGs in the Airflow UI:"
    echo "http://localhost:8090"
else
    echo "❌ There are issues with the Airflow environment."
    echo "Please check the output above for details."
fi

# Clean up
rm -f /tmp/airflow_test.py
docker exec $AIRFLOW_WEBSERVER rm -f /opt/airflow/airflow_test.py 