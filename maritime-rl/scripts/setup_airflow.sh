#!/bin/bash
# Script to set up Airflow container with RL configuration and visualization

set -e  # Exit on any error

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MARITIME_DIR="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

echo "Setting up Airflow for RL training and visualization..."
echo "Maritime RL directory: $MARITIME_DIR"

# Create config directory
docker exec airflow-webserver mkdir -p /opt/airflow/config
docker exec airflow-webserver mkdir -p /opt/airflow/models/rl/monte_carlo
docker exec airflow-webserver mkdir -p /opt/airflow/src/maritime/visualization/static/monte_carlo

# Create vessel directories
for vessel in vessel_1 vessel_2 vessel_3; do
  docker exec airflow-webserver mkdir -p /opt/airflow/models/rl/monte_carlo/$vessel
done

# Copy Monte Carlo visualization template
if [ -f "$MARITIME_DIR/src/maritime/visualization/templates/monte_carlo_template.html" ]; then
  docker cp "$MARITIME_DIR/src/maritime/visualization/templates/monte_carlo_template.html" airflow-webserver:/opt/airflow/src/maritime/visualization/templates/
  echo "Copied Monte Carlo template"
else
  echo "Monte Carlo template not found at $MARITIME_DIR/src/maritime/visualization/templates/monte_carlo_template.html"
fi

# Copy updated dashboard with Monte Carlo link
if [ -f "$MARITIME_DIR/src/maritime/visualization/dashboard.py" ]; then
  docker cp "$MARITIME_DIR/src/maritime/visualization/dashboard.py" airflow-webserver:/opt/airflow/src/maritime/visualization/
  echo "Copied dashboard.py"
else
  echo "dashboard.py not found at $MARITIME_DIR/src/maritime/visualization/dashboard.py"
fi

if [ -f "$MARITIME_DIR/src/maritime/visualization/monte_carlo_viz.py" ]; then
  docker cp "$MARITIME_DIR/src/maritime/visualization/monte_carlo_viz.py" airflow-webserver:/opt/airflow/src/maritime/visualization/
  echo "Copied monte_carlo_viz.py"
else
  echo "monte_carlo_viz.py not found at $MARITIME_DIR/src/maritime/visualization/monte_carlo_viz.py"  
fi

if [ -f "$MARITIME_DIR/src/maritime/visualization/templates/dashboard_template.html" ]; then
  docker cp "$MARITIME_DIR/src/maritime/visualization/templates/dashboard_template.html" airflow-webserver:/opt/airflow/src/maritime/visualization/templates/
  echo "Copied dashboard template"
else
  echo "Dashboard template not found at $MARITIME_DIR/src/maritime/visualization/templates/dashboard_template.html"
fi

# Generate RL config
mkdir -p "$MARITIME_DIR/config"
cat > "$MARITIME_DIR/config/rl_config.json" << EOF
{
  "output_dir": "/opt/airflow/models/rl",
  "epochs": 100,
  "steps_per_epoch": 1000,
  "max_episode_length": 150,
  "save_freq": 10,
  "num_vessels": 3,
  "plot_results": true,
  "environment": {
    "max_steps": 200,
    "weather_change_prob": 0.1,
    "hazard_density": 0.05,
    "fuel_capacity": 100.0,
    "destination": [57.1, 12.3]
  },
  "agent": {
    "learning_rate": 0.0003,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_ratio": 0.2,
    "target_kl": 0.01,
    "value_learning_rate": 0.001,
    "train_pi_iterations": 80,
    "train_v_iterations": 80,
    "batch_size": 64
  }
}
EOF

# Copy RL config
docker cp "$MARITIME_DIR/config/rl_config.json" airflow-webserver:/opt/airflow/config/
echo "Copied RL config"

# Create a placeholder Monte Carlo summary file if it doesn't exist
mkdir -p "$MARITIME_DIR/models/rl/monte_carlo"
cat > "$MARITIME_DIR/models/rl/monte_carlo/mc_summary.json" << EOF
{
  "creation_date": "$(date -Iseconds)",
  "training_iterations": 10,
  "average_reward": 156.72,
  "success_rate": 0.78,
  "vessels": ["vessel_1", "vessel_2", "vessel_3"],
  "summary": {
    "total_trajectories": 30,
    "successful_trajectories": 24,
    "hazard_collisions": 3,
    "fuel_depletions": 3,
    "average_steps": 127.3
  }
}
EOF
docker cp "$MARITIME_DIR/models/rl/monte_carlo/mc_summary.json" airflow-webserver:/opt/airflow/models/rl/monte_carlo/
echo "Created and copied Monte Carlo summary"

# Create a sample vessel summary if it doesn't exist
for vessel in vessel_1 vessel_2 vessel_3; do
  mkdir -p "$MARITIME_DIR/models/rl/monte_carlo/$vessel"
  cat > "$MARITIME_DIR/models/rl/monte_carlo/$vessel/summary.json" << EOF
{
  "vessel_id": "$vessel",
  "iterations": 10,
  "success_rate": 0.8,
  "average_steps": 125.4,
  "average_reward": 162.5,
  "trajectories": [
    {
      "iteration": 0,
      "steps": 132,
      "destination_reached": true,
      "hazard_hit": false,
      "fuel_depleted": false,
      "final_reward": 178.3,
      "trajectory_file": "/opt/airflow/models/rl/monte_carlo/$vessel/trajectory_0.json"
    },
    {
      "iteration": 1,
      "steps": 128,
      "destination_reached": true,
      "hazard_hit": false,
      "fuel_depleted": false,
      "final_reward": 165.7,
      "trajectory_file": "/opt/airflow/models/rl/monte_carlo/$vessel/trajectory_1.json"
    }
  ]
}
EOF
  docker cp "$MARITIME_DIR/models/rl/monte_carlo/$vessel/summary.json" airflow-webserver:/opt/airflow/models/rl/monte_carlo/$vessel/
  echo "Created and copied $vessel summary"
done

# Install required libraries in Airflow container
docker exec airflow-webserver pip install tensorflow pandas matplotlib
echo "Installed Python dependencies"

# Create a simple trajectory file for visualization
for vessel in vessel_1 vessel_2 vessel_3; do
  cat > "$MARITIME_DIR/models/rl/monte_carlo/$vessel/trajectory_0.json" << EOF
{
  "vessel_id": "$vessel",
  "iteration": 0,
  "destination": [57.1, 12.3],
  "hazards": [[56.2, 10.8], [56.4, 11.2], [55.9, 11.5]],
  "trajectory": [
    {"step": 0, "position": [55.6, 10.6], "heading": 45, "speed": 12, "fuel_level": 100, "reward": 0.5, "cumulative_reward": 0.5},
    {"step": 1, "position": [55.65, 10.65], "heading": 45, "speed": 12, "fuel_level": 98, "reward": 0.6, "cumulative_reward": 1.1},
    {"step": 2, "position": [55.7, 10.7], "heading": 47, "speed": 12, "fuel_level": 96, "reward": 0.6, "cumulative_reward": 1.7},
    {"step": 3, "position": [55.75, 10.75], "heading": 47, "speed": 12.5, "fuel_level": 94, "reward": 0.7, "cumulative_reward": 2.4},
    {"step": 4, "position": [55.8, 10.8], "heading": 50, "speed": 12.5, "fuel_level": 92, "reward": 0.7, "cumulative_reward": 3.1},
    {"step": 5, "position": [55.85, 10.85], "heading": 50, "speed": 13, "fuel_level": 90, "reward": 0.8, "cumulative_reward": 3.9}
  ]
}
EOF
  docker cp "$MARITIME_DIR/models/rl/monte_carlo/$vessel/trajectory_0.json" airflow-webserver:/opt/airflow/models/rl/monte_carlo/$vessel/
  echo "Created and copied $vessel trajectory"
done

# Copy all Monte Carlo data to visualization static dir
docker exec airflow-webserver sh -c "cp -r /opt/airflow/models/rl/monte_carlo/* /opt/airflow/src/maritime/visualization/static/monte_carlo/"
echo "Copied all Monte Carlo data to visualization directory"

echo "Setup complete! Airflow is now ready for RL training." 