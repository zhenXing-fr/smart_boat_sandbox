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
        time, 
        vessel_id, 
        ST_X(position::geometry) as lon,
        ST_Y(position::geometry) as lat, 
        speed, 
        heading, 
        fuel_consumption
    FROM vessel_telemetry
    ORDER BY vessel_id, time
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
    os.symlink(model_path, latest_model_path)
    
    print(f"Created symlink to latest model: {latest_model_path}")
    
except Exception as e:
    print(f"Error during model training: {e}")
finally:
    conn.close()
    print("Database connection closed")
