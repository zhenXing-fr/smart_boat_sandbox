# Maritime Route Optimization Exercise: Reinforcement Learning for Vessel Navigation

## Overview
This exercise simulates a maritime route optimization system using reinforcement learning. The system processes historical sailing data, weather conditions, and environmental hazards to optimize vessel routes for fuel efficiency and safety.

## Architecture Components

```mermaid
graph TB
    subgraph "Data Sources"
        HD[Historical Sailing Data] -->|"CSV/JSON"| K1[Kafka Producer]
        WD[Weather Data API] -->|"REST API"| K2[Kafka Producer]
        ED[Environmental Data] -->|"REST API"| K3[Kafka Producer]
    end

    subgraph "Data Processing"
        K1 & K2 & K3 -->|"Avro Schema"| KR[Kafka Topics]
        KR -->|"Validation"| KS[Kafka Streams]
        KS -->|"Anomaly Detection"| AD[Quality Gates]
    end

    subgraph "Storage"
        AD -->|"Time-series"| TSDB[TimescaleDB]
        AD -->|"Processed Events"| PT[Kafka Processed Topics]
    end

    subgraph "ML Pipeline"
        TSDB & PT -->|"Feature Engineering"| FE[Feature Store]
        FE -->|"Training Data"| RL[Reinforcement Learning]
        RL -->|"Model"| RM[Route Model]
    end

    subgraph "Orchestration"
        AF[Airflow DAGs] -->|"Schedule"| KS
        AF -->|"Train"| RL
        AF -->|"Deploy"| RM
    end

    subgraph "Visualization"
        RM -->|"Route Predictions"| VIZ[Streamlit Dashboard]
        VIZ -->|"Real-time"| MAP[Interactive Map]
    end
```

## Project Structure
```
maritime-rl/
├── helm/
│   ├── kafka/
│   ├── timescaledb/
│   ├── airflow/
│   └── argocd/
├── data/
│   ├── historical/
│   ├── weather/
│   └── environmental/
├── src/
│   ├── maritime_rl/
│   │   ├── schemas/
│   │   ├── producers/
│   │   ├── processors/
│   │   ├── features/
│   │   ├── models/
│   │   └── visualization/
├── tests/
└── docker/
```

## Data Schemas

### 1. Historical Sailing Data
```json
{
  "type": "record",
  "name": "SailingRecord",
  "fields": [
    {"name": "vessel_id", "type": "string"},
    {"name": "timestamp", "type": "long"},
    {"name": "position", "type": {
      "type": "record",
      "name": "Position",
      "fields": [
        {"name": "latitude", "type": "double"},
        {"name": "longitude", "type": "double"}
      ]
    }},
    {"name": "speed", "type": "double"},
    {"name": "heading", "type": "double"},
    {"name": "fuel_consumption", "type": "double"},
    {"name": "weather_conditions", "type": {
      "type": "record",
      "name": "Weather",
      "fields": [
        {"name": "wind_speed", "type": "double"},
        {"name": "wave_height", "type": "double"},
        {"name": "current_speed", "type": "double"}
      ]
    }}
  ]
}
```

### 2. Weather Data
```json
{
  "type": "record",
  "name": "WeatherData",
  "fields": [
    {"name": "timestamp", "type": "long"},
    {"name": "location", "type": {
      "type": "record",
      "name": "Location",
      "fields": [
        {"name": "latitude", "type": "double"},
        {"name": "longitude", "type": "double"}
      ]
    }},
    {"name": "forecast", "type": {
      "type": "array",
      "items": {
        "type": "record",
        "name": "ForecastPoint",
        "fields": [
          {"name": "time", "type": "long"},
          {"name": "wind_speed", "type": "double"},
          {"name": "wind_direction", "type": "double"},
          {"name": "wave_height", "type": "double"},
          {"name": "current_speed", "type": "double"},
          {"name": "current_direction", "type": "double"}
        ]
      }
    }}
  ]
}
```

### 3. Environmental Data
```json
{
  "type": "record",
  "name": "EnvironmentalData",
  "fields": [
    {"name": "timestamp", "type": "long"},
    {"name": "location", "type": {
      "type": "record",
      "name": "Location",
      "fields": [
        {"name": "latitude", "type": "double"},
        {"name": "longitude", "type": "double"}
      ]
    }},
    {"name": "hazards", "type": {
      "type": "array",
      "items": {
        "type": "record",
        "name": "Hazard",
        "fields": [
          {"name": "type", "type": "string"},
          {"name": "severity", "type": "int"},
          {"name": "radius", "type": "double"},
          {"name": "description", "type": "string"}
        ]
      }
    }}
  ]
}
```

## Implementation Steps

### 1. Local Development Environment Setup
```bash
# Install Docker and Docker Compose
brew install docker docker-compose

# For K8s deployment (optional)
brew install kubectl helm

# Start all services using Docker Compose
docker-compose -f docker/docker-compose.yml up -d
```

### 2. Data Generation
- Create synthetic historical sailing data
- Simulate weather API responses
- Generate environmental hazard data
- Implement data quality checks

### 3. Kafka Setup
- Configure Schema Registry
- Set up topics with appropriate partitions
- Implement producers for each data type
- Create validation rules

### 4. Kafka Streams Implementation
```java
// Example Kafka Streams topology for data processing
StreamsBuilder builder = new StreamsBuilder();

KStream<String, SailingRecord> vesselData = builder.stream(
    "vessel_sailing_data",
    Consumed.with(Serdes.String(), sailingRecordSerde)
);

// Data validation and cleaning
KStream<String, SailingRecord> validData = vesselData
    .filter((key, value) -> value != null && isValid(value));

// Calculate derived metrics
KStream<String, EnrichedSailingRecord> enrichedData = validData
    .mapValues(value -> enrichWithMetrics(value));

// Detect anomalies
KStream<String, EnrichedSailingRecord> withAnomalyFlags = enrichedData
    .mapValues(value -> detectAnomalies(value));

// Write to output topic
withAnomalyFlags.to(
    "processed_sailing_data",
    Produced.with(Serdes.String(), enrichedSailingRecordSerde)
);
```

### 5. TimescaleDB Configuration
```sql
-- Create hypertable for vessel telemetry
CREATE TABLE vessel_telemetry (
    time TIMESTAMPTZ NOT NULL,
    vessel_id TEXT NOT NULL,
    position_lat DOUBLE PRECISION,
    position_lon DOUBLE PRECISION,
    speed DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    fuel_consumption DOUBLE PRECISION,
    weather_wind_speed DOUBLE PRECISION,
    weather_wave_height DOUBLE PRECISION,
    weather_current_speed DOUBLE PRECISION
);

SELECT create_hypertable('vessel_telemetry', 'time',
    chunk_time_interval => INTERVAL '1 day',
    compress_after => INTERVAL '7 days'
);
```

### 6. Feature Engineering
- Calculate vessel performance metrics
- Create weather impact features
- Generate hazard avoidance features
- Build composite features for RL

### 7. Reinforcement Learning Model
- Define state space (vessel position, weather, hazards)
- Create action space (heading changes, speed adjustments)
- Implement reward function
- Train model using historical data

### 8. Airflow DAGs
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'maritime_route_optimization',
    default_args=default_args,
    description='Maritime route optimization pipeline',
    schedule_interval='@daily',
)

# Define tasks
data_validation = PythonOperator(
    task_id='validate_data',
    python_callable=validate_data,
    dag=dag,
)

feature_engineering = PythonOperator(
    task_id='calculate_features',
    python_callable=calculate_features,
    dag=dag,
)

model_training = PythonOperator(
    task_id='train_model',
    python_callable=train_model,
    dag=dag,
)

model_deployment = PythonOperator(
    task_id='deploy_model',
    python_callable=deploy_model,
    dag=dag,
)

# Set task dependencies
data_validation >> feature_engineering >> model_training >> model_deployment
```

### 9. Visualization
- Create Streamlit dashboard
- Implement interactive map
- Show real-time route predictions
- Display model performance metrics

## Deployment

### 1. Docker Compose (Development)
```yaml
# Example Docker Compose for local development
version: '3'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,EXTERNAL://localhost:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
    ports:
      - "9092:9092"
      - "9093:9093"
  
  schema-registry:
    image: confluentinc/cp-schema-registry:latest
    depends_on:
      - kafka
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: kafka:9092
    ports:
      - "8081:8081"
  
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_PASSWORD: password
      POSTGRES_USER: maritime
      POSTGRES_DB: maritime
    ports:
      - "5432:5432"
    volumes:
      - timescaledb-data:/var/lib/postgresql/data
```

### 2. Kubernetes Deployment (Production)
```yaml
# Example Kafka Helm values
kafka:
  enabled: true
  image: confluentinc/cp-kafka:latest
  config:
    num.partitions: 3
    default.replication.factor: 1
    offsets.topic.replication.factor: 1
    transaction.state.log.replication.factor: 1
    transaction.state.log.min.isr: 1
```

## Testing Strategy
1. Unit tests for data validation
2. Integration tests for Kafka producers and streams
3. Performance tests for TimescaleDB
4. Model evaluation metrics
5. End-to-end pipeline tests

## Reinforcement Learning Details

### RL Environment

The RL environment simulates maritime navigation with:

- **State space**: 
  - Vessel position (lat, lon)
  - Vessel state (speed, heading, fuel level)
  - Local weather conditions
  - Nearby hazards
  - Distance to destination

- **Action space**:
  - Speed adjustments (increase, maintain, decrease)
  - Heading adjustments (5° increments)

- **Reward function**:
  ```python
  def calculate_reward(state, action, next_state):
      reward = 0
      
      # Distance to goal reward
      prev_distance = haversine(state.position, GOAL_POSITION)
      current_distance = haversine(next_state.position, GOAL_POSITION)
      reward += (prev_distance - current_distance) * DISTANCE_REWARD_FACTOR
      
      # Fuel consumption penalty
      reward -= next_state.fuel_consumption * FUEL_PENALTY_FACTOR
      
      # Safety rewards/penalties
      if is_near_hazard(next_state.position):
          reward -= HAZARD_PENALTY
      
      # Weather condition penalties
      weather_risk = calculate_weather_risk(next_state)
      reward -= weather_risk * WEATHER_PENALTY_FACTOR
      
      # Arrival bonus
      if is_at_destination(next_state.position):
          reward += DESTINATION_BONUS
          
      return reward
  ```

### Algorithm Choice
- **Proximal Policy Optimization (PPO)** for its sample efficiency and stability
- Deep neural network to approximate policy and value functions
- Experience replay to improve sample efficiency

## Monitoring

### Key Metrics to Monitor
- Kafka consumer lag
- Kafka Streams processing throughput
- TimescaleDB query performance
- Model training metrics:
  - Average reward per episode
  - Success rate (reaching destination)
  - Fuel efficiency
- System resource utilization

### Monitoring Tools
- Prometheus for metrics collection
- Grafana for visualization
- Kafka UI for Kafka monitoring
- Airflow monitoring for DAG status

### Dashboard Layout
```
+---------------------+---------------------+
|                     |                     |
|   Route Map View    |   System Metrics    |
|                     |                     |
+---------------------+---------------------+
|                     |                     |
| Vessel Performance  |   Model Metrics     |
|                     |                     |
+---------------------+---------------------+
|                                           |
|           Data Pipeline Status            |
|                                           |
+-------------------------------------------+
```

## Conclusion
This exercise provides a comprehensive example of building a reinforcement learning system for maritime route optimization. It covers the full data pipeline from ingestion through Kafka, processing with Kafka Streams, storage in TimescaleDB, feature engineering, model training with RL, and visualization of results. 