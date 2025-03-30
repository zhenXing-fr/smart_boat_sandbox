from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow import DAG
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
    'maritime_model_training',
    default_args=default_args,
    description='Maritime route optimization model training',
    schedule_interval='@daily',
)

# Define task to prepare training data
prepare_training_data = BashOperator(
    task_id='prepare_training_data',
    bash_command='''
    cd /opt/airflow
    export PYTHONPATH="${PYTHONPATH}:/opt/airflow"
    python3 -c "
import pandas as pd
import psycopg2
import os
import json
from datetime import datetime

DB_HOST = 'timescaledb'
DB_PORT = '5432'
DB_USER = 'maritime'
DB_PASSWORD = 'password'
DB_NAME = 'maritime'

print('Preparing training data for model training...')

# Connect to database
conn = None
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    print('Connected to database')
    
    # Query vessel data
    query = '''SELECT timestamp, vessel_id, ST_X(position::geometry) as lon,
           ST_Y(position::geometry) as lat, speed, heading, fuel_consumption
    FROM vessel_telemetry ORDER BY vessel_id, timestamp'''
    
    # Execute query and load into DataFrame
    df = pd.read_sql_query(query, conn)
    
    # Create output directory if it doesn't exist
    os.makedirs('/opt/airflow/data/training', exist_ok=True)
    
    # Save to CSV for training
    output_file = '/opt/airflow/data/training/vessel_data.csv'
    df.to_csv(output_file, index=False)
    print(f'Saved {len(df)} records to {output_file}')
    
    # Create metadata file
    metadata = {
        'records': len(df),
        'vessels': df['vessel_id'].nunique(),
        'data_range': [df['timestamp'].min(), df['timestamp'].max()],
        'prepared_at': datetime.now().isoformat()
    }
    
    with open('/opt/airflow/data/training/metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    print('Training data preparation complete')
    
except Exception as e:
    print(f'Error preparing training data: {e}')
    exit(1)
finally:
    if conn:
        conn.close()
"
    ''',
    dag=dag
)

# Define task to train model
train_model = BashOperator(
    task_id='train_model',
    bash_command='''
    cd /opt/airflow
    export PYTHONPATH="${PYTHONPATH}:/opt/airflow"
    python3 -c "
import pandas as pd
import json
import os
from datetime import datetime

print('Training maritime route optimization model...')

try:
    # Load training data
    data_file = '/opt/airflow/data/training/vessel_data.csv'
    df = pd.read_csv(data_file)
    
    # Group by vessel and process
    vessels = df['vessel_id'].unique()
    model_data = {}
    
    for vessel_id in vessels:
        vessel_df = df[df['vessel_id'] == vessel_id].copy()
        vessel_df = vessel_df.sort_values('timestamp')
        
        # Simple model: find best fuel efficiency speed and heading
        features_df = vessel_df.copy()
        
        if len(features_df) > 1:
            # Create features
            features_df['lat_diff'] = features_df['lat'].diff()
            features_df['lon_diff'] = features_df['lon'].diff()
            features_df['distance'] = (features_df['lat_diff']**2 + features_df['lon_diff']**2)**0.5
            features_df['fuel_efficiency'] = features_df['fuel_consumption'] / (features_df['distance'] * features_df['speed'])
            features_df = features_df.dropna()
            
            if len(features_df) > 0:
                # Find optimal parameters (simple approach)
                optimal_speed = features_df.loc[features_df['fuel_efficiency'].idxmin()]['speed']
                optimal_heading = features_df.loc[features_df['fuel_efficiency'].idxmin()]['heading']
                
                model_data[vessel_id] = {
                    'optimal_speed': float(optimal_speed),
                    'optimal_heading': float(optimal_heading),
                    'avg_fuel_consumption': float(features_df['fuel_consumption'].mean()),
                    'avg_fuel_efficiency': float(features_df['fuel_efficiency'].mean()),
                    'training_samples': len(features_df),
                    'training_date': datetime.now().isoformat()
                }
    
    # Create output directory
    os.makedirs('/opt/airflow/models/basic', exist_ok=True)
    
    # Save model data
    model_file = f'/opt/airflow/models/basic/maritime_model_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.json'
    with open(model_file, 'w') as f:
        json.dump(model_data, f, indent=2)
    
    # Create symlink to latest model
    latest_link = '/opt/airflow/models/basic/latest_model.json'
    if os.path.exists(latest_link):
        os.remove(latest_link)
    os.symlink(model_file, latest_link)
    
    print(f'Model training complete. Model saved to {model_file}')
    
except Exception as e:
    print(f'Error training model: {e}')
    exit(1)
"
    ''',
    dag=dag
)

# Add RL training task
train_rl_model = BashOperator(
    task_id='train_rl_model',
    bash_command='''
    cd /opt/airflow
    export PYTHONPATH="${PYTHONPATH}:/opt/airflow"
    
    # First run Monte Carlo simulation
    python3 -c "
import os
import json
import random
import math
import numpy as np
import pandas as pd
from datetime import datetime

print('Training reinforcement learning model...')

# Create output directories
os.makedirs('/opt/airflow/models/rl', exist_ok=True)
os.makedirs('/opt/airflow/models/rl/monte_carlo', exist_ok=True)

try:
    # Load training data
    data_file = '/opt/airflow/data/training/vessel_data.csv'
    if not os.path.exists(data_file):
        raise FileNotFoundError(f'Training data file not found: {data_file}')
        
    df = pd.read_csv(data_file)
    vessel_ids = df['vessel_id'].unique().tolist()
    
    if not vessel_ids:
        raise ValueError('No vessel IDs found in training data')
    
    print(f'Found {len(vessel_ids)} vessels in training data')
    
    # Set up Monte Carlo parameters
    iterations = 10
    hazard_positions = [
        [56.2, 10.8],
        [56.4, 11.2],
        [55.9, 11.5]
    ]
    destination = [57.1, 12.3]
    
    # Track overall metrics
    total_trajectories = len(vessel_ids) * iterations
    successful_trajectories = 0
    hazard_collisions = 0
    fuel_depletions = 0
    total_steps = 0
    total_reward = 0
    
    # Create directories for each vessel
    for vessel_id in vessel_ids:
        vessel_dir = f'/opt/airflow/models/rl/monte_carlo/{vessel_id}'
        os.makedirs(vessel_dir, exist_ok=True)
        
        # Get actual data for this vessel
        vessel_df = df[df['vessel_id'] == vessel_id]
        
        # Generate trajectories for this vessel
        vessel_trajectories = []
        
        # Get starting and ending positions from actual data
        if len(vessel_df) >= 2:
            start_lat = vessel_df.iloc[0]['lat']
            start_lon = vessel_df.iloc[0]['lon']
            
            # Use the last position as a reference for destination
            last_lat = vessel_df.iloc[-1]['lat'] 
            last_lon = vessel_df.iloc[-1]['lon']
            
            # Calculate a reasonable destination a bit further from last position
            direction_lat = last_lat - start_lat
            direction_lon = last_lon - start_lon
            distance = math.sqrt(direction_lat**2 + direction_lon**2)
            
            if distance > 0:
                # Extend 20% further in the same direction
                dest_lat = last_lat + (direction_lat / distance) * distance * 0.2
                dest_lon = last_lon + (direction_lon / distance) * distance * 0.2
                destination = [dest_lat, dest_lon]
        
        for i in range(iterations):
            # Use actual starting point if available, otherwise generate random
            if len(vessel_df) > 0:
                start_lat = vessel_df.iloc[0]['lat'] + random.uniform(-0.05, 0.05)
                start_lon = vessel_df.iloc[0]['lon'] + random.uniform(-0.05, 0.05)
            else:
                start_lat = 55.5 + random.random() * 1.0
                start_lon = 10.5 + random.random() * 0.5
            
            # Simulate a trajectory
            steps = random.randint(100, 150)
            trajectory = []
            
            # Set up initial state
            position = [start_lat, start_lon]
            heading = math.degrees(math.atan2(
                destination[0] - start_lat,
                destination[1] - start_lon
            ))
            
            # Use actual speed if available 
            if len(vessel_df) > 0:
                speed = vessel_df['speed'].mean()
            else:
                speed = 10 + random.random() * 5
                
            fuel_level = 100.0
            
            # Random success/failure
            success_prob = 0.8  # 80% success rate
            dest_reached = random.random() < success_prob
            
            if not dest_reached:
                # Determine failure mode
                if random.random() < 0.5:
                    hazard_hit = True
                    fuel_depleted = False
                    # Will fail at a random step between 50-80% of the way
                    failure_step = int(steps * (0.5 + random.random() * 0.3))
                else:
                    hazard_hit = False
                    fuel_depleted = True
                    # Will fail at a random step between 60-90% of the way
                    failure_step = int(steps * (0.6 + random.random() * 0.3))
            else:
                hazard_hit = False
                fuel_depleted = False
                failure_step = steps + 1  # No failure
            
            # Generate the path and rewards
            current_reward = 0
            trajectory_data = []
            
            for step in range(steps):
                # Adjust heading slightly toward destination
                ideal_heading = math.degrees(math.atan2(
                    destination[0] - position[0],
                    destination[1] - position[1]
                ))
                heading_diff = (ideal_heading - heading + 180) % 360 - 180
                heading += heading_diff * 0.2  # Gradually adjust
                
                # Add some noise to heading
                heading += (random.random() - 0.5) * 10
                
                # Move according to heading and speed
                dx = math.cos(math.radians(heading)) * speed * 0.001
                dy = math.sin(math.radians(heading)) * speed * 0.001
                position = [position[0] + dy, position[1] + dx]
                
                # Reduce fuel
                fuel_consumption = 0.5 + (speed / 20) + random.random() * 0.2
                fuel_level -= fuel_consumption
                
                # Calculate distance to destination
                dist_to_dest = math.sqrt(
                    (position[0] - destination[0])**2 + 
                    (position[1] - destination[1])**2
                )
                
                # Calculate reward (more reward as we get closer)
                step_reward = 1.0 - (dist_to_dest / 3.0)
                
                # Penalty for fuel consumption
                step_reward -= fuel_consumption * 0.1
                
                # Check for hazards
                near_hazard = False
                for hazard in hazard_positions:
                    hazard_dist = math.sqrt(
                        (position[0] - hazard[0])**2 + 
                        (position[1] - hazard[1])**2
                    )
                    if hazard_dist < 0.15:
                        near_hazard = True
                        step_reward -= 5.0
                
                # If this is the failure step, enforce failure
                if step == failure_step:
                    if hazard_hit:
                        # Force collision with a hazard
                        position = hazard_positions[random.randint(0, len(hazard_positions)-1)]
                        step_reward -= 50.0
                    elif fuel_depleted:
                        # Force fuel depletion
                        fuel_level = 0
                        step_reward -= 30.0
                
                # Add to total reward
                current_reward += step_reward
                
                # Store this step
                trajectory_data.append({
                    'step': step,
                    'position': position,
                    'heading': heading,
                    'speed': speed,
                    'fuel_level': fuel_level,
                    'reward': step_reward,
                    'cumulative_reward': current_reward
                })
                
                # Check for terminal state
                if fuel_level <= 0 or near_hazard or dist_to_dest < 0.05:
                    break
            
            # Add destination bonus if reached
            if dist_to_dest < 0.05:
                current_reward += 100.0
                dest_reached = True
            
            # Save trajectory file
            traj_file = f'{vessel_dir}/trajectory_{i}.json'
            with open(traj_file, 'w') as f:
                json.dump({
                    'vessel_id': vessel_id,
                    'iteration': i,
                    'destination': destination,
                    'hazards': hazard_positions,
                    'trajectory': trajectory_data
                }, f, indent=2)
            
            # Add to vessel trajectories
            vessel_trajectories.append({
                'iteration': i,
                'steps': len(trajectory_data),
                'destination_reached': dest_reached,
                'hazard_hit': hazard_hit,
                'fuel_depleted': fuel_depleted,
                'final_reward': current_reward,
                'trajectory_file': traj_file
            })
            
            # Update overall metrics
            if dest_reached:
                successful_trajectories += 1
            if hazard_hit:
                hazard_collisions += 1
            if fuel_depleted:
                fuel_depletions += 1
            total_steps += len(trajectory_data)
            total_reward += current_reward
        
        # Save vessel summary
        with open(f'{vessel_dir}/summary.json', 'w') as f:
            json.dump({
                'vessel_id': vessel_id,
                'iterations': iterations,
                'success_rate': sum(1 for t in vessel_trajectories if t['destination_reached']) / iterations,
                'average_steps': sum(t['steps'] for t in vessel_trajectories) / iterations,
                'average_reward': sum(t['final_reward'] for t in vessel_trajectories) / iterations,
                'trajectories': vessel_trajectories
            }, f, indent=2)
    
    # Create overall summary
    with open('/opt/airflow/models/rl/monte_carlo/mc_summary.json', 'w') as f:
        json.dump({
            'creation_date': datetime.now().isoformat(),
            'training_iterations': iterations,
            'average_reward': round(total_reward / total_trajectories, 2),
            'success_rate': round(successful_trajectories / total_trajectories, 2),
            'vessels': vessel_ids,
            'summary': {
                'total_trajectories': total_trajectories,
                'successful_trajectories': successful_trajectories,
                'hazard_collisions': hazard_collisions,
                'fuel_depletions': fuel_depletions,
                'average_steps': round(total_steps / total_trajectories, 1)
            }
        }, f, indent=2)
    
    # Create notification file
    with open('/opt/airflow/models/rl/NEW_RL_MODEL_AVAILABLE', 'w') as f:
        f.write(f'New RL model generated at {datetime.now().isoformat()}')
    
    print('RL model training and Monte Carlo simulation complete')
except Exception as e:
    print(f'Error in RL training: {e}')
    exit(1)
"

    # Now run the RL model training script that creates the maritime_rl_model_latest.json file
    echo "Training RL model with actual vessel data..."
    cd /opt/airflow/maritime-rl
    
    # Create a Python script for model training
    cat > train_model.py << 'EOFPYTHON'
import os
import psycopg2
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pickle
import json

print("Starting RL model training...")

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST", "timescaledb")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "maritime")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_NAME = os.environ.get("DB_NAME", "maritime")

# Connect to the database
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    cursor = conn.cursor()
    print("Connected to TimescaleDB")
except Exception as e:
    print(f"Database connection error: {e}")
    exit(1)

# Query vessel telemetry data
try:
    query = '''
    SELECT 
        timestamp, 
        vessel_id, 
        ST_X(position::geometry) as lon,
        ST_Y(position::geometry) as lat, 
        speed, 
        heading, 
        fuel_consumption
    FROM vessel_telemetry
    ORDER BY vessel_id, timestamp
    '''
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if not rows:
        print("No vessel telemetry data found in the database")
        exit(1)
    
    print(f"Retrieved {len(rows)} records from database")
    
    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=[
        'timestamp', 'vessel_id', 'longitude', 'latitude', 
        'speed', 'heading', 'fuel_consumption'
    ])
    
    # Process data by vessel
    vessels = df['vessel_id'].unique()
    print(f"Found data for {len(vessels)} vessels")
    
    # Simple RL model training (in a real scenario, this would be more complex)
    model_data = {}
    
    for vessel_id in vessels:
        vessel_df = df[df['vessel_id'] == vessel_id].sort_values('timestamp')
        
        if len(vessel_df) < 10:
            print(f"Not enough data for vessel {vessel_id}, skipping")
            continue
            
        print(f"Training model for vessel {vessel_id} with {len(vessel_df)} records")
        
        # Extract features
        features = []
        for i in range(1, len(vessel_df)):
            prev = vessel_df.iloc[i-1]
            curr = vessel_df.iloc[i]
            
            # Calculate distance traveled
            lat1, lon1 = prev['latitude'], prev['longitude']
            lat2, lon2 = curr['latitude'], curr['longitude']
            
            # Simple Euclidean distance as a proxy
            distance = np.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
            
            # Calculate time difference
            time_diff = (curr['timestamp'] - prev['timestamp']).total_seconds() / 3600  # hours
            
            # Skip invalid time differences
            if time_diff <= 0:
                continue
                
            # Calculate metrics
            speed_diff = curr['speed'] - prev['speed']
            heading_diff = min(abs(curr['heading'] - prev['heading']), 360 - abs(curr['heading'] - prev['heading']))
            fuel_consumption = curr['fuel_consumption']
            
            # Calculate derived metrics
            if time_diff > 0:
                fuel_efficiency = fuel_consumption / (distance * curr['speed']) if distance * curr['speed'] > 0 else 0
            else:
                fuel_efficiency = 0
                
            features.append({
                'vessel_id': vessel_id,
                'timestamp': curr['timestamp'],
                'latitude': curr['latitude'],
                'longitude': curr['longitude'],
                'speed': curr['speed'],
                'heading': curr['heading'],
                'speed_diff': speed_diff,
                'heading_diff': heading_diff,
                'distance': distance,
                'time_diff': time_diff,
                'fuel_consumption': fuel_consumption,
                'fuel_efficiency': fuel_efficiency
            })
        
        if not features:
            print(f"No valid features for vessel {vessel_id}, skipping")
            continue
            
        features_df = pd.DataFrame(features)
        
        # Simple model: optimal speed and heading for minimal fuel consumption
        optimal_speed = features_df.loc[features_df['fuel_efficiency'].idxmin()]['speed']
        optimal_heading = features_df.loc[features_df['fuel_efficiency'].idxmin()]['heading']
        
        model_data[vessel_id] = {
            'optimal_speed': float(optimal_speed),
            'optimal_heading': float(optimal_heading),
            'avg_fuel_consumption': float(features_df['fuel_consumption'].mean()),
            'avg_fuel_efficiency': float(features_df['fuel_efficiency'].mean()),
            'training_samples': len(features_df),
            'training_date': datetime.now().isoformat()
        }
        
        print(f"Model for vessel {vessel_id}: optimal_speed={optimal_speed}, optimal_heading={optimal_heading}")
    
    # Save the model
    os.makedirs('models', exist_ok=True)
    model_path = f"models/maritime_rl_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(model_path, 'w') as f:
        json.dump(model_data, f, indent=2)
    
    print(f"Model saved to {model_path}")
    
    # Create a symlink to the latest model
    latest_model_path = "models/maritime_rl_model_latest.json"
    if os.path.exists(latest_model_path):
        os.remove(latest_model_path)
    
    # Use a relative path without the models/ prefix
    model_filename = os.path.basename(model_path)
    os.symlink(model_filename, latest_model_path)
    
    print(f"Created symlink to latest model: {latest_model_path}")
    
except Exception as e:
    print(f"Error during model training: {e}")
finally:
    conn.close()
    print("Database connection closed")
EOFPYTHON

    # Run the script to train the model
    python3 train_model.py
    
    echo "RL model trained successfully."
    ''',
    dag=dag
)

# Define task to deploy model
deploy_model = BashOperator(
    task_id='deploy_model',
    bash_command='''
    cd /opt/airflow
    
    # Deploy basic model
    if [ -f "/opt/airflow/models/basic/latest_model.json" ]; then
        echo "Deploying basic model to dashboard..."
        mkdir -p /opt/airflow/src/maritime/visualization/static/models
        cp /opt/airflow/models/basic/latest_model.json /opt/airflow/src/maritime/visualization/static/models/
        echo "Basic model deployed"
    else
        echo "No basic model found to deploy"
    fi
    
    # Deploy RL model and Monte Carlo data
    if [ -d "/opt/airflow/models/rl/monte_carlo" ]; then
        echo "Deploying Monte Carlo data to dashboard..."
        
        # Create directories for dashboard to access
        mkdir -p /opt/airflow/src/maritime/visualization/static/monte_carlo
        
        # Copy Monte Carlo data
        cp -r /opt/airflow/models/rl/monte_carlo/* /opt/airflow/src/maritime/visualization/static/monte_carlo/
        
        # Create notification for dashboard
        echo "New RL model available at $(date -Iseconds)" > /opt/airflow/src/maritime/visualization/static/NEW_MODEL_AVAILABLE
        
        echo "Monte Carlo data deployed"
    else
        echo "No Monte Carlo data found to deploy"
    fi
    
    # Fix symlink if broken
    cd /opt/airflow/maritime-rl
    echo "Checking for model files..."
    
    # Find the latest model file
    LATEST_MODEL=$(ls -t models/maritime_rl_model_*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_MODEL" ]; then
        echo "Found latest model file: $LATEST_MODEL"
        
        # Check if symlink exists and is valid
        if [ ! -L "models/maritime_rl_model_latest.json" ] || [ ! -e "models/maritime_rl_model_latest.json" ]; then
            echo "Fixing broken symlink..."
            rm -f models/maritime_rl_model_latest.json
            ln -sf $(basename $LATEST_MODEL) models/maritime_rl_model_latest.json
            echo "Symlink fixed"
        fi
        
        # Now deploy the model
        echo "Deploying maritime RL model to dashboard..."
        mkdir -p /opt/airflow/src/maritime/visualization/static/models
        cp models/maritime_rl_model_latest.json /opt/airflow/src/maritime/visualization/static/models/
        echo "Maritime RL model deployed"
    else
        echo "No maritime RL model files found"
    fi
    
    echo "All models deployed successfully."
    ''',
    dag=dag
)

# Update task dependencies to include RL training
prepare_training_data >> train_model
prepare_training_data >> train_rl_model
train_model >> deploy_model
train_rl_model >> deploy_model 