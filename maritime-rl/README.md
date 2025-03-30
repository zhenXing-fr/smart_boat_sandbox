# Maritime Route Optimization

A reinforcement learning system for optimizing maritime vessel routes based on real-time sailing data, weather conditions, and environmental factors.

## Project Overview

This project implements a complete data pipeline for maritime route optimization:
- Data generation for vessel telemetry, weather, and environmental conditions
- Kafka producers with Avro schema validation
- Kafka Streams for data processing and transformation
- TimescaleDB storage for time-series data
- Reinforcement learning models for route optimization
- Airflow for pipeline orchestration

## Setup Instructions

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd maritime-rl
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   # Using venv
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Or using uv (faster)
   pip install uv
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install the project in development mode
   uv pip install -e .
   
   # Install development dependencies
   uv pip install -e ".[dev]"
   
   # Install visualization dependencies
   uv pip install -e ".[viz]"
   ```

3. Create an environment file:
   ```bash
   cp .env.example .env
   ```

## Starting the Infrastructure

The project uses several services that run in Docker containers:

1. Start all services:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

This will start:
- Zookeeper
- Kafka
- Schema Registry
- Kafka UI
- TimescaleDB

> **Note:** Sometimes services may start in the wrong order, causing some to fail. If only Zookeeper starts successfully, try starting each service individually:
> ```bash
> docker-compose -f docker/docker-compose.yml up -d zookeeper
> docker-compose -f docker/docker-compose.yml up -d kafka
> docker-compose -f docker/docker-compose.yml up -d schema-registry
> docker-compose -f docker/docker-compose.yml up -d kafka-ui
> docker-compose -f docker/docker-compose.yml up -d timescaledb
> ```

### Accessing the Services

- **Kafka UI**: http://localhost:8080 (for monitoring Kafka topics, producers, consumers, and messages)
- **Schema Registry**: http://localhost:8081 (for Avro schemas)
- **TimescaleDB**: 
  - Host: localhost:5432
  - Username: maritime
  - Password: password
  - Database: maritime

## Running the Data Pipeline

### 1. Data Producers

The sailing data producer generates synthetic vessel data and publishes it to Kafka:

```bash
# Run the producer with default settings
python -m src.maritime_rl.producers.sailing_producer

# Run with custom parameters
python -m src.maritime_rl.producers.sailing_producer \
  --vessels 3 \
  --interval 0.5 \
  --iterations 10 \
  --sleep 1.0 \
  --bootstrap-servers localhost:9093 \
  --schema-registry-url http://localhost:8081
```

Parameters:
- `--vessels`: Number of vessels to simulate
- `--interval`: Time interval in hours between data points
- `--iterations`: Number of iterations to run (default: infinite)
- `--sleep`: Sleep interval between iterations in seconds
- `--bootstrap-servers`: Kafka bootstrap servers
- `--schema-registry-url`: Schema Registry URL
- `--topic`: Kafka topic name (default: vessel_sailing_data)
- `--seed`: Random seed for reproducibility

### 2. Data Processing with Kafka Streams

The Kafka Streams processor reads data from Kafka, applies quality gates and enrichment, and publishes processed data to a new topic:

```bash
# Run the processor with default settings
python -m src.maritime_rl.processors.sailing_processor

# Run with custom parameters
python -m src.maritime_rl.processors.sailing_processor \
  --bootstrap-servers localhost:9093 \
  --schema-registry-url http://localhost:8081 \
  --input-topic vessel_sailing_data \
  --output-topic processed_sailing_data \
  --duration 600
```

Parameters:
- `--bootstrap-servers`: Kafka bootstrap servers
- `--schema-registry-url`: Schema Registry URL
- `--input-topic`: Input topic name (default: vessel_sailing_data)
- `--output-topic`: Output topic name (default: processed_sailing_data)
- `--consumer-group`: Consumer group ID (default: sailing-processor)
- `--duration`: Duration to run in seconds (default: indefinite)

### 3. Pipeline Orchestration with Airflow

The project includes Airflow DAGs to orchestrate the entire data pipeline:

```bash
# Start Airflow services
./scripts/start_airflow.sh
```

Access the Airflow UI at http://localhost:8090 (username: airflow, password: airflow)

The following DAGs are available:
- **maritime_data_pipeline**: Runs every 15 minutes to process new sailing data
- **maritime_model_training**: Runs daily to train the RL model

#### Quality Gates

The data processing pipeline includes quality gates that validate and ensure data quality:

1. **Basic validation** in Kafka processor: Checks for valid data types, ranges, and required fields
2. **Quality metrics** calculation: Each record is assigned a quality score
3. **Anomaly detection**: Identifies outliers and suspicious patterns
4. **Branching**: Valid data continues through the pipeline, while invalid data is sent to an error topic

### 4. Data Visualization Dashboard

The project includes a real-time dashboard to visualize vessel data, routes, and performance metrics:

```bash
# Start the visualization dashboard
./scripts/start_dashboard.sh
```

Access the dashboard at http://localhost:5000

The dashboard provides:
- Real-time vessel tracking on an interactive map
- Optimized vs. actual routes visualization
- Data quality metrics and trends
- Fuel consumption analysis
- Performance statistics

The dashboard can work with real data from TimescaleDB or with mock data if the database is not available.

### Using the Convenience Scripts

Convenience scripts are provided to start the various components:

```bash
# Start Kafka and other infrastructure services
./scripts/start_producer.sh

# Start Airflow for pipeline orchestration
./scripts/start_airflow.sh

# Start the visualization dashboard
./scripts/start_dashboard.sh
```

## Checking the Data

### Through Kafka UI

1. Go to http://localhost:8080
2. Navigate to Topics → vessel_sailing_data or processed_sailing_data
3. Click on "Messages" to view the data

### Using Command Line

```bash
# View a list of topics
docker exec -it docker-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list

# Consume messages from a topic
docker exec -it docker-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic vessel_sailing_data \
  --from-beginning
```

### Checking Schemas

```bash
# List all registered schemas
curl -s http://localhost:8081/subjects | jq

# View a specific schema
curl -s http://localhost:8081/subjects/vessel_sailing_data-value/versions/1 | jq
```

### Exploring TimescaleDB

```bash
# Use the psql script to connect to TimescaleDB
./scripts/psql.sh

# Inside psql, run queries like:
SELECT * FROM vessel_telemetry LIMIT 10;
SELECT * FROM data_quality_metrics LIMIT 10;
```

## Project Structure

```
maritime-rl/
├── helm/            # Kubernetes helm charts
├── data/            # Data files
├── dags/            # Airflow DAGs
├── src/             # Source code
│   ├── maritime_rl/
│   │   ├── schemas/     # Avro schemas
│   │   ├── producers/   # Kafka producers
│   │   ├── processors/  # Kafka Streams processors
│   │   ├── features/    # Feature engineering
│   │   ├── models/      # ML models
│   │   └── visualization/ # Visualizations
├── tests/           # Unit and integration tests
├── docker/          # Docker configurations
├── scripts/         # Utility scripts
└── ...
```

## Troubleshooting

### Only Zookeeper Starts

If only Zookeeper starts when running `docker-compose up -d`, try starting services one by one as shown above.

### Import Errors

If you encounter import errors when running the producers, ensure:
1. You've installed all dependencies: `uv pip install -e .`
2. Your virtual environment is activated

### Connection Issues

If producers can't connect to Kafka:
1. Ensure Kafka is running: `docker ps | grep kafka`
2. Check if you're using the correct bootstrap servers (default is localhost:9093 for external connections)
3. Verify network connectivity: `telnet localhost 9093`

### Airflow Problems

If Airflow services don't start correctly:
1. Check the logs: `docker-compose -f docker/docker-compose-airflow.yml logs`
2. Ensure the Airflow UID is set correctly: `export AIRFLOW_UID=$(id -u)`
3. Make sure the maritime-network Docker network exists: `docker network create maritime-network`

### Dashboard Issues

If the dashboard shows mock data instead of real data:
1. Ensure TimescaleDB is running and populated with data
2. Check the dashboard logs for connection errors
3. Try running some producers and processors to generate real data
4. If you're only interested in the UI, the mock data provides a good representation

## Next Steps

- Expand quality gates with more sophisticated validation rules
- Implement additional Kafka Streams processors for different data types
- Develop the RL environment and training pipeline
- Create visualizations for route predictions 