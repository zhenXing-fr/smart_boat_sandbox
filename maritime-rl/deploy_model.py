import os
import json
import shutil
from datetime import datetime

print("Starting model deployment...")

# Check if model exists
model_path = "models/maritime_rl_model_latest.json"
if not os.path.exists(model_path):
    print(f"Error: Model file {model_path} not found")
    exit(1)

try:
    # Load the model to validate it
    with open(model_path, 'r') as f:
        model_data = json.load(f)
    
    num_vessels = len(model_data)
    print(f"Loaded model for {num_vessels} vessels")
    
    # Create deployment directory
    deploy_dir = "/opt/airflow/maritime-rl/src/maritime/models/deployed"
    os.makedirs(deploy_dir, exist_ok=True)
    
    # Copy model to deployment directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    deployed_model_path = f"{deploy_dir}/maritime_rl_model_{timestamp}.json"
    
    shutil.copy(model_path, deployed_model_path)
    print(f"Copied model to {deployed_model_path}")
    
    # Create/update symlink to latest deployed model
    latest_deployed_path = f"{deploy_dir}/maritime_rl_model_latest.json"
    if os.path.exists(latest_deployed_path):
        os.remove(latest_deployed_path)
    
    os.symlink(deployed_model_path, latest_deployed_path)
    print(f"Updated symlink to latest deployed model: {latest_deployed_path}")
    
    # Create a metadata file for the dashboard
    metadata = {
        "model_id": f"maritime_rl_{timestamp}",
        "deployment_time": datetime.now().isoformat(),
        "num_vessels": num_vessels,
        "vessels": list(model_data.keys()),
        "metrics": {
            vessel_id: {
                "optimal_speed": data["optimal_speed"],
                "optimal_heading": data["optimal_heading"],
                "avg_fuel_efficiency": data["avg_fuel_efficiency"],
                "training_samples": data["training_samples"]
            }
            for vessel_id, data in model_data.items()
        }
    }
    
    metadata_path = f"{deploy_dir}/model_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Created model metadata file: {metadata_path}")
    
    # Create flag file to notify dashboard of new model
    with open(f"{deploy_dir}/NEW_MODEL_AVAILABLE", 'w') as f:
        f.write(f"New model deployed at {datetime.now().isoformat()}")
    
    print(f"Created notification flag for dashboard")
    print("Model deployment completed successfully")
    
except Exception as e:
    print(f"Error during model deployment: {e}")
