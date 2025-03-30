# Maritime Route Optimization with Reinforcement Learning

This project implements a maritime route optimization system using reinforcement learning. It processes historical sailing data, weather conditions, and environmental hazards to optimize vessel routes for fuel efficiency and safety.

## Setup

### Prerequisites

- Python 3.9+
- Rancher Desktop or Docker Desktop
- Helm
- kubectl
- ArgoCD (for production deployment)

### Development Environment

We use `uv` for faster dependency management and virtual environment creation. To set up:

```bash
# Install uv if you don't have it
pip install uv

# Create virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e .
```

For development dependencies:
```bash
uv pip install -e ".[dev]"
```

For Airflow integration:
```bash
uv pip install -e ".[airflow]"
```

## Project Structure

```
maritime-rl/
├── helm/               # Kubernetes deployment configurations
│   ├── kafka/
│   ├── timescaledb/
│   ├── airflow/
│   └── argocd/
├── data/               # Data sources and samples
│   ├── historical/
│   ├── weather/
│   └── environmental/
├── src/                # Source code
│   ├── producers/      # Kafka producers for data ingestion
│   ├── processors/     # Data processing and validation
│   ├── features/       # Feature engineering
│   ├── models/         # RL models and training
│   └── visualization/  # Streamlit dashboards
├── tests/              # Test suite
└── docker/             # Docker configurations
```

## Running the Pipeline

1. Start local Kubernetes cluster:
   ```bash
   rancher desktop start
   ```

2. Deploy infrastructure:
   ```bash
   helm install kafka ./helm/kafka
   helm install timescaledb ./helm/timescaledb
   helm install airflow ./helm/airflow
   ```

3. Run data producers:
   ```bash
   python -m src.producers.historical_data
   python -m src.producers.weather_data
   python -m src.producers.environmental_data
   ```

4. Start the visualization dashboard:
   ```bash
   streamlit run src/visualization/dashboard.py
   ```

## Testing

Run the test suite:
```bash
pytest
```

Or with coverage:
```bash
pytest --cov=src
```

## License

MIT 