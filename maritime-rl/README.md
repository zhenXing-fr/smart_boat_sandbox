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

## Features

- **Real-time data processing**: Process vessel telemetry data through Kafka streams
- **Data quality checks**: Validation, anomaly detection, and quality metrics
- **Time-series database**: Efficient storage of historical sailing data in TimescaleDB
- **Reinforcement learning**: RL models for optimizing routes based on multiple factors
- **Interactive visualization**: Real-time dashboard for route monitoring and analysis
- **Container-based deployment**: Docker and Docker Compose for easy setup

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

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Project Structure

```
maritime-rl/
├── src/                   # Source code
│   └── maritime/          # Main package
│       ├── data/          # Data processing utilities
│       ├── producers/     # Kafka producers
│       ├── processors/    # Kafka stream processors
│       ├── schemas/       # Avro schemas
│       └── visualization/ # Dashboard and visualization
├── docker/                # Docker configuration
│   ├── docker-compose.yml         # Main services
│   └── init-db.sql                # Database initialization
├── scripts/               # Helper scripts
│   └── start_services_sequences.sh   # Launch all services in sequences
├── dags/                  # Airflow DAGs
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore file
├── pyproject.toml         # Project dependencies and configuration
└── README.md              # This file
```

## Infrastructure

The project uses several services that run in Docker containers:

### Starting the Infrastructure

1. Start all services:
   ```bash
   ./script/start_services_sequential.sh
   ```

   This will start:
   - Zookeeper
   - Kafka
   - Schema Registry
   - Kafka UI
   - TimescaleDB
   - Airflow-postgres
   - Airflow-scheduler
   - Airflow-webserver

### Accessing the Services

After startup, the following services are available:

- **Kafka UI**: http://localhost:8080
- **Schema Registry**: http://localhost:8081
- **Airflow UI**: http://localhost:8090 (username: admin, password: maritime_admin)
- **pgAdmin**: http://localhost:5050 (email: admin@maritime.com, password: maritime_admin)
- **TimescaleDB**: 
  - Host: localhost:5432
  - Username: maritime
  - Password: password
  - Database: maritime
- **Airflow**:
  - Username: admin
  - Password: maritime_admin

Note run below script if airflow init fail
```
docker exec -it airflow-webserver airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@maritime.com \
  --password maritime_admin
```

## Running the Data Pipeline

### 1. Manual Data Producer Start

Run the sailing data producer to generate synthetic vessel data:

```bash
# Run the producer with default settings
python -m src.maritime.producers.sailing_producer

# Run with custom parameters
python -m src.maritime.producers.sailing_producer \
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

### 3. Data Processing

Run the Kafka Streams processor:

```bash
python -m src.maritime.processors.sailing_processor \
  --bootstrap-servers localhost:9093 \
  --schema-registry-url http://localhost:8081 \
  --input-topic vessel_sailing_data \
  --output-topic processed_sailing_data
```

### 4. Pipeline Orchestration with Airflow

Start Airflow services:

```bash
./scripts/start_airflow.sh
```

Access the Airflow UI at http://localhost:8090 (username: airflow, password: airflow)

The project includes the following DAGs:
- **maritime_data_pipeline**: Runs every 15 minutes to process new sailing data
- **maritime_model_training**: Runs daily to train the RL model

### 5. Visualization Dashboard

Start the dashboard:

```bash
./scripts/start_dashboard.sh
```

Access the dashboard at http://localhost:5000

## Monitoring and Debugging

### Viewing Kafka Data

#### Through Kafka UI

1. Go to http://localhost:8080
2. Navigate to Topics → vessel_sailing_data or processed_sailing_data
3. Click on "Messages" to view the data

#### Using Command Line

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

Connect to TimescaleDB and run queries:

```bash
# Use the psql script to connect to TimescaleDB
./scripts/psql.sh

# Inside psql, run queries like:
SELECT * FROM vessel_telemetry LIMIT 10;
SELECT * FROM data_quality_metrics LIMIT 10;
```

## Reinforcement Learning Details

The project uses Proximal Policy Optimization (PPO) to optimize vessel routes based on:

- **State space**: Vessel position, heading, speed, weather conditions, hazards
- **Action space**: Speed and heading adjustments
- **Reward function**: Optimizing for fuel efficiency, safety, and timely arrival

Models are trained automatically through the Airflow pipeline and used for route predictions in the dashboard.

## Next Steps

Now that your infrastructure is running, here are the recommended next steps:

### 1. Generate Test Data

Start producing synthetic vessel data to test the system:

```bash
# Start the vessel data producer with 3 vessels
python -m src.maritime.producers.sailing_producer --vessels 3 --iterations 100
```

### 2. Process Data Through Kafka Streams

Start the Kafka processor to apply quality gates and transformations:

```bash
python -m src.maritime.processors.sailing_processor
```

### 3. Explore Data with pgAdmin

After running the data producers:

1. Login to pgAdmin (http://localhost:5050)
2. Connect to TimescaleDB
3. Explore vessel_telemetry table to see the data
4. Try running some analytics queries:

```sql
-- View recent vessel data
SELECT * FROM vessel_telemetry ORDER BY timestamp DESC LIMIT 100;

-- Aggregate fuel consumption by vessel
SELECT vessel_id, 
       AVG(fuel_consumption) as avg_fuel,
       SUM(fuel_consumption) as total_fuel
FROM vessel_telemetry
GROUP BY vessel_id;
```

### 4. Configure Airflow DAGs

1. Access Airflow UI (http://localhost:8090)
2. Enable the DAGs:
   - maritime_data_pipeline
   - maritime_model_training
3. Monitor the DAG runs to ensure they're processing data

### 5. Visualize Results

Start the visualization dashboard:

```bash
./scripts/start_dashboard.sh
```

Access the dashboard at http://localhost:5000 to see the vessel routes and performance metrics.

### 6. Extend the Model

Consider the following enhancements:

1. Add more environmental data sources
2. Implement more sophisticated quality gates
3. Experiment with different RL models and parameters
4. Add additional visualizations to the dashboard

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 