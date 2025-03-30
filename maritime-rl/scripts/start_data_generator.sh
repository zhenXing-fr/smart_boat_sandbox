#!/bin/bash
# Start the vessel data generator in the background

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if Kafka is running
echo "Checking Kafka connection..."
KAFKA_RUNNING=false
for i in {1..5}; do
    if nc -z localhost 9093; then
        KAFKA_RUNNING=true
        break
    fi
    echo "Waiting for Kafka to be available... (attempt $i)"
    sleep 2
done

if [ "$KAFKA_RUNNING" = false ]; then
    echo "Error: Kafka is not available at localhost:9093"
    echo "Make sure the Docker environment is running"
    exit 1
fi

# Create topics if they don't exist
echo "Creating Kafka topics if they don't exist..."
python3 -c '
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

try:
    admin = KafkaAdminClient(bootstrap_servers="localhost:9093")
    topics = admin.list_topics()
    print(f"Current topics: {topics}")
    
    for topic in ["vessel_sailing_data", "processed_sailing_data"]:
        if topic not in topics:
            admin.create_topics([NewTopic(name=topic, num_partitions=3, replication_factor=1)])
            print(f"Created {topic}")
    
except Exception as e:
    print(f"Error: {e}")
'

# Start the data generator in continuous mode
echo "Starting vessel data generator..."
nohup python3 scripts/generate_vessel_data.py --continue --delay 1 > logs/data_generator.log 2>&1 &
GENERATOR_PID=$!

echo "Data generator started with PID: $GENERATOR_PID"
echo "PID $GENERATOR_PID" > logs/data_generator.pid
echo "Logs available in logs/data_generator.log" 