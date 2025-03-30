#!/usr/bin/env python3
"""
Generate realistic vessel data and send it to Kafka.
This creates real data for the maritime route optimization system.
"""

import json
import random
import time
from datetime import datetime, timedelta
import argparse
import os
import sys
from kafka import KafkaProducer

def get_random_drift(base, max_drift_pct=0.05):
    """Apply random drift to a base value."""
    max_drift = base * max_drift_pct
    return base + random.uniform(-max_drift, max_drift)

def generate_vessel_data(vessel_id, num_points=100, time_interval_sec=60):
    """Generate a trajectory for a vessel."""
    # Initial position
    data = []
    
    # Starting parameters
    vessels = {
        "vessel_1": {
            "name": "Baltic Trader",
            "lat": 56.10,
            "lng": 11.0,
            "heading": 45,
            "speed": 12.5,
            "destination": {"lat": 56.25, "lng": 11.5}
        },
        "vessel_2": {
            "name": "Nordic Star",
            "lat": 55.7,
            "lng": 11.9,
            "heading": 90,
            "speed": 10.2,
            "destination": {"lat": 55.9, "lng": 12.4}
        },
        "vessel_3": {
            "name": "Atlantic Voyager",
            "lat": 57.0,
            "lng": 10.2,
            "heading": 270,
            "speed": 8.1,
            "destination": {"lat": 57.2, "lng": 10.5}
        }
    }
    
    # Use vessel parameters if available, otherwise use defaults
    vessel = vessels.get(vessel_id, {
        "name": f"Vessel {vessel_id}",
        "lat": 56.0 + random.uniform(-1, 1),
        "lng": 11.0 + random.uniform(-1, 1),
        "heading": random.uniform(0, 360),
        "speed": random.uniform(8, 15),
        "destination": {
            "lat": 56.0 + random.uniform(-1, 1) + 0.2,
            "lng": 11.0 + random.uniform(-1, 1) + 0.2
        }
    })
    
    lat = vessel["lat"]
    lng = vessel["lng"]
    heading = vessel["heading"]
    speed = vessel["speed"]
    
    # Environmental conditions
    wind_speed = random.uniform(5, 15)  # knots
    wave_height = random.uniform(0.5, 2.5)  # meters
    current_speed = random.uniform(0.5, 2.0)  # knots
    
    # Generate trajectory
    for i in range(num_points):
        # Calculate timestamp
        timestamp = int((datetime.now() + timedelta(seconds=i * time_interval_sec)).timestamp() * 1000)
        
        # Calculate fuel consumption based on speed, wind, and waves
        # Simple model: higher speed and adverse conditions = higher consumption
        base_consumption = speed * 1.5  # base fuel consumption (liters per hour)
        wind_factor = 1 + (wind_speed / 30)  # wind impact
        wave_factor = 1 + (wave_height / 5)  # wave impact
        
        fuel_consumption = base_consumption * wind_factor * wave_factor
        
        # Create data point
        data_point = {
            "vessel_id": vessel_id,
            "timestamp": timestamp,
            "position": {
                "latitude": lat,
                "longitude": lng
            },
            "speed": speed,
            "heading": heading,
            "fuel_consumption": fuel_consumption,
            "weather_conditions": {
                "wind_speed": wind_speed,
                "wave_height": wave_height,
                "current_speed": current_speed
            }
        }
        
        data.append(data_point)
        
        # Update position based on heading and speed
        # Note: This is a simplified calculation - in a real system, use proper geospatial calculations
        lat_change = speed * 0.0001 * time_interval_sec/3600 * math.cos(math.radians(heading))
        lng_change = speed * 0.0001 * time_interval_sec/3600 * math.sin(math.radians(heading))
        
        lat += lat_change
        lng += lng_change
        
        # Adjust heading to move toward destination
        dest_lat = vessel["destination"]["lat"]
        dest_lng = vessel["destination"]["lng"]
        
        # Calculate bearing to destination
        target_heading = math.degrees(math.atan2(dest_lng - lng, dest_lat - lat))
        if target_heading < 0:
            target_heading += 360
            
        # Gradually adjust current heading toward target (with some randomness)
        heading_diff = (target_heading - heading + 180) % 360 - 180
        heading_change = max(-10, min(10, heading_diff * 0.2 + random.uniform(-5, 5)))
        heading = (heading + heading_change) % 360
        
        # Adjust speed with some randomness
        speed = max(5, min(20, speed + random.uniform(-0.5, 0.5)))
        
        # Update environmental conditions
        wind_speed = max(0, min(30, wind_speed + random.uniform(-1, 1)))
        wave_height = max(0, min(5, wave_height + random.uniform(-0.2, 0.2)))
        current_speed = max(0, min(3, current_speed + random.uniform(-0.1, 0.1)))
        
    return data

def send_to_kafka(producer, topic, data):
    """Send data points to Kafka topic."""
    for data_point in data:
        producer.send(topic, value=data_point)
    producer.flush()

def main():
    """Main function to generate and send vessel data."""
    parser = argparse.ArgumentParser(description="Generate vessel data and send to Kafka")
    parser.add_argument("--bootstrap-servers", default="localhost:9093", help="Kafka bootstrap servers")
    parser.add_argument("--topic", default="vessel_sailing_data", help="Kafka topic")
    parser.add_argument("--vessels", default="vessel_1,vessel_2,vessel_3", help="Comma-separated list of vessel IDs")
    parser.add_argument("--points", type=int, default=100, help="Number of data points per vessel")
    parser.add_argument("--interval", type=int, default=60, help="Time interval between points (seconds)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between sending points (seconds)")
    parser.add_argument("--continue", dest="continuous", action="store_true", help="Continue generating data indefinitely")
    
    args = parser.parse_args()
    
    # Create Kafka producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=args.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"Connected to Kafka at {args.bootstrap_servers}")
    except Exception as e:
        print(f"Error connecting to Kafka: {e}")
        sys.exit(1)
    
    # Get vessel IDs
    vessel_ids = args.vessels.split(",")
    print(f"Generating data for vessels: {vessel_ids}")
    
    try:
        if args.continuous:
            print(f"Generating data continuously (Ctrl+C to stop)")
            
            # Track last position and parameters for each vessel
            vessel_state = {}
            
            while True:
                for vessel_id in vessel_ids:
                    # Generate a single data point for each vessel
                    if vessel_id not in vessel_state:
                        # Initialize vessel state
                        vessel_state[vessel_id] = {
                            "lat": 56.0 + random.uniform(-1, 1),
                            "lng": 11.0 + random.uniform(-1, 1),
                            "heading": random.uniform(0, 360),
                            "speed": random.uniform(8, 15),
                            "wind_speed": random.uniform(5, 15),
                            "wave_height": random.uniform(0.5, 2.5),
                            "current_speed": random.uniform(0.5, 2.0),
                            "destination": {
                                "lat": 56.0 + random.uniform(-1, 1) + 0.2,
                                "lng": 11.0 + random.uniform(-1, 1) + 0.2
                            }
                        }
                    
                    # Get current state
                    state = vessel_state[vessel_id]
                    
                    # Calculate fuel consumption
                    base_consumption = state["speed"] * 1.5
                    wind_factor = 1 + (state["wind_speed"] / 30)
                    wave_factor = 1 + (state["wave_height"] / 5)
                    fuel_consumption = base_consumption * wind_factor * wave_factor
                    
                    # Create data point
                    data_point = {
                        "vessel_id": vessel_id,
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "position": {
                            "latitude": state["lat"],
                            "longitude": state["lng"]
                        },
                        "speed": state["speed"],
                        "heading": state["heading"],
                        "fuel_consumption": fuel_consumption,
                        "weather_conditions": {
                            "wind_speed": state["wind_speed"],
                            "wave_height": state["wave_height"],
                            "current_speed": state["current_speed"]
                        }
                    }
                    
                    # Send to Kafka
                    producer.send(args.topic, value=data_point)
                    
                    # Update position and parameters for next iteration
                    lat_change = state["speed"] * 0.0001 * args.delay * math.cos(math.radians(state["heading"]))
                    lng_change = state["speed"] * 0.0001 * args.delay * math.sin(math.radians(state["heading"]))
                    
                    state["lat"] += lat_change
                    state["lng"] += lng_change
                    
                    # Calculate bearing to destination
                    dest_lat = state["destination"]["lat"]
                    dest_lng = state["destination"]["lng"]
                    
                    # If close to destination, pick a new destination
                    if abs(dest_lat - state["lat"]) < 0.01 and abs(dest_lng - state["lng"]) < 0.01:
                        state["destination"] = {
                            "lat": state["lat"] + random.uniform(-0.2, 0.2),
                            "lng": state["lng"] + random.uniform(-0.2, 0.2)
                        }
                        dest_lat = state["destination"]["lat"]
                        dest_lng = state["destination"]["lng"]
                    
                    # Adjust heading toward destination
                    target_heading = math.degrees(math.atan2(dest_lng - state["lng"], dest_lat - state["lat"]))
                    if target_heading < 0:
                        target_heading += 360
                        
                    heading_diff = (target_heading - state["heading"] + 180) % 360 - 180
                    heading_change = max(-10, min(10, heading_diff * 0.2 + random.uniform(-5, 5)))
                    state["heading"] = (state["heading"] + heading_change) % 360
                    
                    # Update other parameters
                    state["speed"] = max(5, min(20, state["speed"] + random.uniform(-0.5, 0.5)))
                    state["wind_speed"] = max(0, min(30, state["wind_speed"] + random.uniform(-1, 1)))
                    state["wave_height"] = max(0, min(5, state["wave_height"] + random.uniform(-0.2, 0.2)))
                    state["current_speed"] = max(0, min(3, state["current_speed"] + random.uniform(-0.1, 0.1)))
                
                # Flush after sending data for all vessels
                producer.flush()
                print(f"Sent data points at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Wait before next iteration
                time.sleep(args.delay)
        else:
            # Generate a batch of data points for each vessel
            for vessel_id in vessel_ids:
                data = generate_vessel_data(
                    vessel_id=vessel_id, 
                    num_points=args.points,
                    time_interval_sec=args.interval
                )
                
                print(f"Generated {len(data)} data points for vessel {vessel_id}")
                
                # Send to Kafka with delay to simulate real-time data
                for i, data_point in enumerate(data):
                    producer.send(args.topic, value=data_point)
                    if (i + 1) % 10 == 0:
                        producer.flush()
                        print(f"Sent {i + 1}/{len(data)} data points for vessel {vessel_id}")
                    time.sleep(args.delay)
                
                producer.flush()
            
            print(f"Finished sending {len(vessel_ids) * args.points} data points to Kafka topic {args.topic}")
    
    except KeyboardInterrupt:
        print("Data generation interrupted")
    finally:
        producer.close()
        print("Kafka producer closed")

if __name__ == "__main__":
    # Add math module for trig calculations
    import math
    main() 