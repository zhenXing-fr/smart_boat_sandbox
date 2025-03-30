#!/bin/bash
# Master script to run the complete Maritime Route Optimization demo

set -e  # Exit on any error

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MARITIME_DIR="$SCRIPT_DIR/maritime-rl"

echo "Starting Maritime Route Optimization Demo..."

# Step 0: Create maritime network if it doesn't exist
docker network inspect maritime-network >/dev/null 2>&1 || docker network create maritime-network
echo "Maritime network is ready"

# Step 1: Build custom Airflow image
echo "Building custom Airflow image with pre-installed dependencies..."
if [ -f "$MARITIME_DIR/scripts/build_airflow_image.sh" ]; then
    bash "$MARITIME_DIR/scripts/build_airflow_image.sh"
else
    echo "Airflow image build script not found - will use standard image"
fi

# Step 2: Start services
echo "Starting services..."
if [ -f "$MARITIME_DIR/scripts/start_services_sequential.sh" ]; then
    echo "Using sequential startup script..."
    bash "$MARITIME_DIR/scripts/start_services_sequential.sh"
else
    echo "Using docker-compose for startup..."
    cd "$MARITIME_DIR/docker" && docker-compose up -d
fi

# Wait for services to be ready
echo "Waiting for services to be fully started..."
sleep 20

# Step 3: Ensure the logs directory exists
echo "Creating logs directory if it doesn't exist..."
mkdir -p "$MARITIME_DIR/logs"

# Step 4: Start the data generator
echo "Starting data generator to produce real data..."
if [ -f "$MARITIME_DIR/scripts/start_data_generator.sh" ]; then
    bash "$MARITIME_DIR/scripts/start_data_generator.sh"
else
    echo "Data generator script not found. Please check the repository structure."
fi

# Step 5: Ensure kafka-python is installed in Airflow containers
echo "Setting up Airflow with kafka-python..."
# The main airflow-init process should have installed kafka-python already
# Let's restart Airflow services to ensure they pick up the changes
echo "Restarting Airflow services to load new dependencies..."
docker restart airflow-webserver airflow-scheduler

# If needed, verify the packages are installed
AIRFLOW_CONTAINERS=$(docker ps | grep airflow | grep -v postgres | awk '{print $1}')
if [ -n "$AIRFLOW_CONTAINERS" ]; then
    for CONTAINER_ID in $AIRFLOW_CONTAINERS; do
        CONTAINER_NAME=$(docker inspect --format='{{.Name}}' $CONTAINER_ID | sed 's/\///')
        echo "Verifying kafka-python in $CONTAINER_NAME..."
        docker exec $CONTAINER_ID python -c "import kafka; print('Kafka module available in', '$CONTAINER_NAME')" || \
        docker exec $CONTAINER_ID pip install kafka-python==2.1.4
    done
else
    echo "No Airflow containers found running. Please check your docker-compose setup."
fi

# Step 6: Update Airflow with latest DAGs
echo "Updating Airflow with latest code..."
if [ -f "$SCRIPT_DIR/scripts/update_airflow.sh" ]; then
    bash "$SCRIPT_DIR/scripts/update_airflow.sh"
fi

# Step 7: Run data generation demo
echo "Running data generation demo..."
if [ -f "$MARITIME_DIR/scripts/run_demo.sh" ]; then
    bash "$MARITIME_DIR/scripts/run_demo.sh"
else
    echo "Demo script not found. Please check the repository structure."
fi

# Step 8: Ensure Kafka topics exist
echo "Ensuring Kafka topics exist..."
pip install kafka-python >/dev/null 2>&1 || echo "kafka-python already installed"
python3 -c '
import time
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

# Wait for Kafka to be ready
time.sleep(5)

try:
    admin_client = KafkaAdminClient(bootstrap_servers="localhost:9093")
    
    # Create required topics if they dont exist
    required_topics = ["vessel_sailing_data", "weather_data", "environmental_data", "processed_sailing_data"]
    existing_topics = admin_client.list_topics()
    
    topics_to_create = []
    for topic in required_topics:
        if topic not in existing_topics:
            topics_to_create.append(NewTopic(name=topic, num_partitions=3, replication_factor=1))
    
    if topics_to_create:
        admin_client.create_topics(new_topics=topics_to_create, validate_only=False)
        print(f"Created topics: {[t.name for t in topics_to_create]}")
    else:
        print("All required topics already exist")
        
except Exception as e:
    print(f"Error setting up Kafka topics: {e}")
'

# Step 9: Trigger Airflow DAGs
echo "Please trigger the following DAGs in Airflow UI (http://localhost:8090):"
echo "  - maritime_data_pipeline"
echo "  - maritime_model_training"
echo ""
echo "Press Enter to continue after triggering the DAGs..."
read -p ""

# Step 10: Start the dashboard
echo "Starting dashboard..."
if [ -f "$MARITIME_DIR/scripts/start_dashboard.sh" ]; then
    # Try to open a new terminal window with the dashboard
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        osascript -e "tell app \"Terminal\" to do script \"cd $MARITIME_DIR && ./scripts/start_dashboard.sh\""
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v gnome-terminal &> /dev/null; then
            gnome-terminal -- bash -c "$MARITIME_DIR/scripts/start_dashboard.sh; exec bash"
        elif command -v xterm &> /dev/null; then
            xterm -e "bash $MARITIME_DIR/scripts/start_dashboard.sh; exec bash" &
        else
            echo "Could not open a new terminal window. Please run the dashboard script manually:"
            echo "  $MARITIME_DIR/scripts/start_dashboard.sh"
        fi
    else
        echo "Please run the dashboard script manually in another terminal:"
        echo "  $MARITIME_DIR/scripts/start_dashboard.sh"
    fi
    
    echo "Dashboard should be available at: http://localhost:5500"
else
    echo "Dashboard script not found. Please start it manually from the maritime-rl directory."
fi

echo "----------------------------------------------------------------"
echo "Maritime Route Optimization Demo Setup Complete!"
echo "----------------------------------------------------------------"
echo "You can access the following services:"
echo ""
echo "Kafka UI:       http://localhost:8080"
echo "Dashboard:      http://localhost:5500"
echo "Airflow:        http://localhost:8090  (admin/maritime_admin)"
echo "pgAdmin:        http://localhost:5050  (admin@maritime.com/maritime_admin)"
echo "TimescaleDB:    localhost:5432         (maritime/password)"
echo ""
echo "To monitor Kafka messages, run:"
echo "  $MARITIME_DIR/scripts/monitor_kafka.py --topics vessel_sailing_data processed_sailing_data"
echo ""
echo "To shut down the demo, run:"
echo "  ./shutdown_demo.sh"
echo "----------------------------------------------------------------" 