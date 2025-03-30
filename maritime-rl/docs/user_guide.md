# Maritime Route Optimization System
## User Guide

This document provides step-by-step instructions for starting, running, and using the maritime route optimization system.

## Table of Contents
1. [System Overview](#system-overview)
2. [Starting the Infrastructure](#starting-the-infrastructure)
3. [Running the Demo](#running-the-demo)
4. [Accessing Components](#accessing-components)
5. [Working with Airflow](#working-with-airflow)
6. [Exploring Data](#exploring-data)
7. [Using the Dashboard](#using-the-dashboard)
8. [Monitoring Kafka](#monitoring-kafka)
9. [Advanced Usage](#advanced-usage)
10. [Troubleshooting](#troubleshooting)

## System Overview

The maritime route optimization system uses reinforcement learning to optimize vessel routes for fuel efficiency and safety. The system consists of:

- **Data Generation**: Simulates vessel sailing data
- **Kafka Pipeline**: Handles data streaming
- **TimescaleDB**: Stores time-series telemetry data
- **Airflow**: Orchestrates data processing and model training
- **RL Model**: Optimizes routes based on weather and vessel parameters
- **Dashboard**: Visualizes vessel data and optimized routes

## Starting the Infrastructure

1. Start all required services in sequence:

```bash
./maritime-rl/scripts/start_services_sequential.sh
```

This script will start:
- Zookeeper
- Kafka
- Schema Registry
- TimescaleDB
- pgAdmin
- Airflow (postgres, webserver, scheduler)

The script verifies the health of each service before proceeding to the next.

## Running the Demo

After starting the infrastructure, run the demo script:

```bash
./maritime-rl/scripts/run_demo.sh
```

This script will:
1. Generate vessel test data (3 vessels, 100 iterations)
2. Process data through Kafka Streams
3. Set up database connections
4. Verify data in TimescaleDB
5. Configure Airflow DAGs
6. Start the visualization dashboard

## Accessing Components

The system consists of several components, each accessible through a web interface:

- **Kafka UI**: http://localhost:8080
- **Schema Registry**: http://localhost:8081
- **pgAdmin**: http://localhost:5050 (admin@maritime.com / maritime_admin)
- **Airflow**: http://localhost:8090 (admin / maritime_admin)
- **Dashboard**: http://localhost:5500

## Working with Airflow

1. Login to Airflow at http://localhost:8090:
   - Username: `admin`
   - Password: `maritime_admin`

2. Enable the following DAGs:
   - `maritime_data_pipeline` - Processes vessel data
   - `maritime_model_training` - Trains the RL model

3. Click the "play" button next to each DAG to trigger them manually.

4. Monitor DAG runs to ensure they complete successfully.

## Exploring Data

1. Login to pgAdmin at http://localhost:5050:
   - Email: `admin@maritime.com`
   - Password: `maritime_admin`

2. Add a new server connection:
   - Name: TimescaleDB
   - Host: timescaledb
   - Port: 5432
   - Username: maritime
   - Password: password

3. Browse the `vessel_telemetry` table to explore the data.

4. Run sample queries:

```sql
-- Get latest positions for all vessels
SELECT DISTINCT ON (vessel_id)
    vessel_id,
    timestamp,
    ST_AsText(position) as position,
    speed,
    heading,
    fuel_consumption
FROM vessel_telemetry
ORDER BY vessel_id, timestamp DESC;

-- Calculate average fuel consumption per vessel
SELECT 
    vessel_id,
    AVG(fuel_consumption) as avg_fuel,
    COUNT(*) as data_points
FROM vessel_telemetry
GROUP BY vessel_id;
```

## Using the Dashboard

The dashboard provides visualization of vessel data and routes:

1. Access the dashboard at http://localhost:5500

2. Main features:
   - **Map View**: Shows vessel locations and routes
   - **Vessel List**: Displays all active vessels
   - **Telemetry Data**: Real-time vessel metrics
   - **Performance Charts**: Fuel consumption and data quality
   - **Route Optimization**: Comparison of standard vs. optimized routes

3. Dashboard interactions:
   - Click on a vessel to see its details
   - Toggle between standard and optimized routes
   - View performance metrics and fuel consumption charts
   - See real-time updates as new data arrives

## Monitoring Kafka

To monitor Kafka topics in real time:

```bash
./scripts/monitor_kafka.py --topics vessel_sailing_data processed_sailing_data
```

This will display messages from both topics in a colorized format, showing the data flowing through the system.

## Advanced Usage

### Generating Additional Data

Generate more vessel data with different parameters:

```bash
python -m src.maritime.producers.sailing_producer --vessels 5 --iterations 200 --sleep 1
```

Parameters:
- `--vessels`: Number of vessels to simulate
- `--iterations`: Number of data points to generate
- `--sleep`: Delay between data points (seconds)

### Customizing the RL Model

The RL model parameters can be adjusted in the Airflow DAG configuration:

1. In Airflow, go to the `maritime_model_training` DAG
2. Click on the "Code" button to view the DAG definition
3. Modify parameters like learning rate, discount factor, etc.
4. Trigger the DAG to train with new parameters

## Troubleshooting

### Common Issues

1. **Services not starting**: 
   - Check the Docker logs: `docker logs <container_name>`
   - Verify all previous services are healthy before starting new ones

2. **No data in TimescaleDB**:
   - Check Kafka topics: `./scripts/monitor_kafka.py --topics vessel_sailing_data`
   - Verify the processor is running: `docker logs sailing_processor`

3. **Dashboard not showing data**:
   - Ensure TimescaleDB has data: check with pgAdmin
   - Verify the dashboard is connecting to the correct database

4. **Airflow DAGs failing**:
   - Check Airflow logs in the UI
   - Verify connections to Kafka and TimescaleDB

### Restarting Components

If you need to restart individual components:

```bash
# Restart Airflow
docker restart airflow-webserver airflow-scheduler

# Restart TimescaleDB
docker restart timescaledb

# Restart Kafka
docker restart kafka schema-registry
```

For a full system restart, stop all containers and run the sequential startup script again:

```bash
cd ./maritime-rl/docker && docker-compose down
./maritime-rl/scripts/start_services_sequential.sh
```
