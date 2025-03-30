# Maritime Route Optimization

A reinforcement learning system for optimizing maritime vessel routes based on real-time sailing data, weather conditions, and environmental factors.

## Project Overview

This project implements a complete data pipeline for maritime route optimization:
- Data generation for vessel telemetry, weather, and environmental conditions
- Kafka producers with Avro schema validation
- TimescaleDB storage for time-series data
- Reinforcement learning models for route optimization

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

## Running the Data Producers

### Sailing Data Producer

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

### Using the Convenience Script

A convenience script is provided to start the infrastructure and run the producer:

```bash
./scripts/start_producer.sh
```

## Checking the Data

### Through Kafka UI

1. Go to http://localhost:8080
2. Navigate to Topics → vessel_sailing_data
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

## Project Structure

```
maritime-rl/
├── helm/            # Kubernetes helm charts
├── data/            # Data files
├── src/             # Source code
│   ├── maritime_rl/
│   │   ├── schemas/     # Avro schemas
│   │   ├── producers/   # Kafka producers
│   │   ├── data/        # Data generators
│   │   └── ...
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

## Next Steps

- Implement Kafka consumers to read data from topics
- Set up TimescaleDB tables for data storage
- Develop feature engineering pipeline
- Create reinforcement learning environment and models 