#!/usr/bin/env python3

import os
import json
import psycopg2
from kafka import KafkaConsumer
from datetime import datetime
import time

print("Starting data storage process...")

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST", "timescaledb")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "maritime")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_NAME = os.environ.get("DB_NAME", "maritime")

# Kafka connection parameters
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = "vessel_sailing_data"

# Connect to database
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    conn.autocommit = False  # Explicitly disable autocommit
    cursor = conn.cursor()
    print("Connected to TimescaleDB")
    
    # Drop the table if it exists to ensure clean schema
    try:
        cursor.execute("DROP TABLE IF EXISTS vessel_telemetry")
        conn.commit()
        print("Dropped existing table if present")
    except Exception as e:
        print(f"Could not drop table: {e}")
        conn.rollback()
    
    # Create table if it doesn't exist with 'timestamp' instead of 'time'
    create_table_sql = '''
    CREATE TABLE IF NOT EXISTS vessel_telemetry (
        timestamp TIMESTAMPTZ NOT NULL,
        vessel_id TEXT NOT NULL,
        position GEOMETRY(POINT, 4326),
        speed DOUBLE PRECISION,
        heading DOUBLE PRECISION,
        fuel_consumption DOUBLE PRECISION,
        quality_score DOUBLE PRECISION
    )
    '''
    cursor.execute(create_table_sql)
    conn.commit()
    print("Table vessel_telemetry created with corrected schema")
    
except Exception as e:
    print(f"Database connection error: {e}")
    exit(1)

# Create Kafka consumer
try:
    # Connect to Kafka
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='maritime-db-consumer-fixed',
        consumer_timeout_ms=60000  # Stop after 1 minute if no messages
    )
    print(f"Connected to Kafka topic {TOPIC}")
except Exception as e:
    print(f"Kafka connection error: {e}")
    conn.close()
    exit(1)

# Process messages
count = 0
try:
    print("Waiting for messages...")
    for message in consumer:
        # Start a new transaction for each message
        try:
            # Print raw message info
            print(f"Received message from partition {message.partition}, offset {message.offset}")
            
            # Try to decode the message
            raw_value = message.value
            if not raw_value:
                print("Empty message value, skipping")
                continue
                
            decoded_value = raw_value.decode('utf-8', errors='replace')
            print(f"Decoded message of length: {len(decoded_value)}")
            
            # Parse JSON data
            try:
                data = json.loads(decoded_value)
            except json.JSONDecodeError as je:
                print(f"JSON parsing error: {je}")
                print(f"First 100 chars of raw message: {decoded_value[:100]}")
                continue
            
            # Extract timestamp and convert to datetime
            timestamp = data.get('timestamp', int(time.time() * 1000))
            if isinstance(timestamp, int):
                timestamp = datetime.fromtimestamp(timestamp / 1000.0)
            
            # Extract vessel ID
            vessel_id = data.get('vessel_id', f"vessel_{count % 3 + 1}")
            
            # Extract position
            position = data.get('position', {})
            if isinstance(position, dict):
                lat = position.get('latitude', 56.0 + (count % 10) * 0.1)
                lon = position.get('longitude', 11.0 + (count % 10) * 0.1)
            else:
                lat = 56.0 + (count % 10) * 0.1
                lon = 11.0 + (count % 10) * 0.1
            
            # Extract other fields
            speed = data.get('speed', 10.0 + (count % 5))
            heading = data.get('heading', (count * 15) % 360)
            fuel_consumption = data.get('fuel_consumption', 15.0 + (count % 10))
            quality_score = data.get('quality_score', 0.7 + (count % 3) * 0.1)
            
            print(f"Processing data for vessel {vessel_id}, timestamp {timestamp}")
            
            # Insert into database with a new cursor for each transaction
            with conn.cursor() as insert_cursor:
                # Use "timestamp" instead of "time" in the SQL
                insert_sql = '''
                INSERT INTO vessel_telemetry 
                (timestamp, vessel_id, position, speed, heading, fuel_consumption, quality_score)
                VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
                '''
                insert_cursor.execute(insert_sql, (timestamp, vessel_id, lon, lat, speed, heading, fuel_consumption, quality_score))
                conn.commit()
                count += 1
                print(f"Inserted record #{count} into TimescaleDB")
                
        except Exception as e:
            print(f"Error processing message: {e}")
            # Rollback the transaction to start fresh with the next message
            try:
                conn.rollback()
                print("Transaction rolled back")
            except Exception as rollback_error:
                print(f"Error during rollback: {rollback_error}")
                # If rollback fails, try to reconnect to the database
                try:
                    conn.close()
                    conn = psycopg2.connect(
                        host=DB_HOST,
                        port=DB_PORT,
                        user=DB_USER,
                        password=DB_PASSWORD,
                        dbname=DB_NAME
                    )
                    conn.autocommit = False
                    cursor = conn.cursor()
                    print("Reconnected to database after error")
                except Exception as reconnect_error:
                    print(f"Failed to reconnect to database: {reconnect_error}")
                    exit(1)
    
    # If no messages were processed, print a message
    if count == 0:
        print("Warning: No data found in Kafka. Please ensure data generator is running.")
    else:
        print(f"Total records stored in TimescaleDB: {count}")
except Exception as e:
    print(f"Error consuming messages: {e}")
finally:
    try:
        consumer.close()
        print("Kafka consumer closed")
    except Exception as e:
        print(f"Error closing Kafka consumer: {e}")
        
    try:
        conn.close()
        print("Database connection closed")
    except Exception as e:
        print(f"Error closing database connection: {e}") 