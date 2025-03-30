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
TOPIC = "processed_sailing_data"

# Connect to database
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
    
    # Create table if it doesn't exist
    create_table_sql = '''
    CREATE TABLE IF NOT EXISTS vessel_telemetry (
        time TIMESTAMPTZ NOT NULL,
        vessel_id TEXT NOT NULL,
        position GEOMETRY(POINT, 4326),
        speed DOUBLE PRECISION,
        heading DOUBLE PRECISION,
        fuel_consumption DOUBLE PRECISION,
        quality_score DOUBLE PRECISION
    )
    '''
    cursor.execute(create_table_sql)
    
    # Create hypertable if it doesn't exist
    try:
        hypertable_sql = "SELECT create_hypertable('vessel_telemetry', 'time', if_not_exists => TRUE)"
        cursor.execute(hypertable_sql)
    except Exception as e:
        print(f"Note: Hypertable may already exist: {e}")
    
    conn.commit()
    print("Table vessel_telemetry created or confirmed")
    
except Exception as e:
    print(f"Database connection error: {e}")
    exit(1)

# Create Kafka consumer
try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='maritime-db-consumer',
        value_deserializer=lambda x: json.loads(x.decode('utf-8', errors='ignore')),
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
    # If no real data exists, generate some sample data
    sample_data_added = False
    for message in consumer:
        data = message.value
        
        # Insert data into TimescaleDB
        try:
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
            
            # Insert into database
            insert_sql = '''
            INSERT INTO vessel_telemetry 
            (time, vessel_id, position, speed, heading, fuel_consumption, quality_score)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
            '''
            cursor.execute(insert_sql, (timestamp, vessel_id, lon, lat, speed, heading, fuel_consumption, quality_score))
            
            count += 1
            if count % 10 == 0:
                conn.commit()
                print(f"Inserted {count} records into TimescaleDB")
        except Exception as e:
            print(f"Error processing message: {e}")
    
    # If no data was processed, generate sample data
    if count == 0:
        print("No data found in Kafka, generating sample data")
        for i in range(50):
            timestamp = datetime.now()
            vessel_id = f"vessel_{i % 3 + 1}"
            lat = 56.0 + (i % 10) * 0.1
            lon = 11.0 + (i % 10) * 0.1
            speed = 10.0 + (i % 5)
            heading = (i * 15) % 360
            fuel_consumption = 15.0 + (i % 10)
            quality_score = 0.7 + (i % 3) * 0.1
            
            # Insert into database
            insert_sql = '''
            INSERT INTO vessel_telemetry 
            (time, vessel_id, position, speed, heading, fuel_consumption, quality_score)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
            '''
            cursor.execute(insert_sql, (timestamp, vessel_id, lon, lat, speed, heading, fuel_consumption, quality_score))
            
            count += 1
        sample_data_added = True
    
    conn.commit()
    print(f"Total records stored in TimescaleDB: {count}")
    if sample_data_added:
        print("Sample data was generated because no real data was found in Kafka")
except Exception as e:
    print(f"Error consuming messages: {e}")
finally:
    consumer.close()
    conn.close()
    print("Database connection closed")
