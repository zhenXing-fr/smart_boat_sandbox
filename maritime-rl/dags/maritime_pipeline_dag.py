"""Airflow DAG for the maritime data processing pipeline."""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup


# Default arguments for all tasks
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Path to the project
PROJECT_PATH = os.environ.get("MARITIME_PROJECT_PATH", "/opt/airflow/dags/maritime-rl")

# Create the main DAG
with DAG(
    dag_id="maritime_data_pipeline",
    default_args=default_args,
    description="Maritime data processing pipeline",
    schedule_interval="*/15 * * * *",  # Run every 15 minutes
    catchup=False,
    max_active_runs=1,
    tags=["maritime", "kafka", "streaming"],
) as dag:
    
    # Task to check Kafka topics exist
    check_kafka_topics = BashOperator(
        task_id="check_kafka_topics",
        bash_command=f"""
            echo "Checking Kafka topics..."
            TOPICS=$(docker exec -it docker-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list)
            if [[ $TOPICS != *"vessel_sailing_data"* ]]; then
                echo "vessel_sailing_data topic does not exist!"
                exit 1
            fi
            if [[ $TOPICS != *"processed_sailing_data"* ]]; then
                echo "Creating processed_sailing_data topic..."
                docker exec -it docker-kafka-1 kafka-topics --bootstrap-server localhost:9092 --create --topic processed_sailing_data --partitions 3 --replication-factor 1
            fi
            echo "Kafka topics check completed."
        """,
    )
    
    # Task to run the sailing data processor
    run_sailing_processor = BashOperator(
        task_id="run_sailing_processor",
        bash_command=f"""
            echo "Starting sailing data processor..."
            cd {PROJECT_PATH}
            source .venv/bin/activate
            python -m src.maritime_rl.processors.sailing_processor \
                --bootstrap-servers localhost:9093 \
                --schema-registry-url http://localhost:8081 \
                --input-topic vessel_sailing_data \
                --output-topic processed_sailing_data \
                --duration 600
            echo "Sailing data processor finished."
        """,
    )
    
    # Task to check processed data quality
    def check_data_quality(**context):
        """Check the quality of processed data."""
        import json
        import os
        import subprocess
        
        # Run a Kafka consumer to get a sample of processed messages
        cmd = [
            "docker", "exec", "-it", "docker-kafka-1",
            "kafka-console-consumer",
            "--bootstrap-server", "localhost:9092",
            "--topic", "processed_sailing_data",
            "--from-beginning",
            "--max-messages", "10",
            "--property", "print.key=true",
            "--property", "print.value=true"
        ]
        
        try:
            # Run the command and capture output
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout
            
            # Count messages
            message_count = output.count("\n") // 2  # Each message has key and value
            
            if message_count < 5:
                return "data_quality_alert"
            else:
                return "data_quality_good"
        
        except subprocess.CalledProcessError as e:
            print(f"Error executing Kafka consumer: {e}")
            return "data_quality_alert"
    
    check_data_quality_task = BranchPythonOperator(
        task_id="check_data_quality",
        python_callable=check_data_quality,
        provide_context=True,
    )
    
    # Task for when data quality is good
    data_quality_good = BashOperator(
        task_id="data_quality_good",
        bash_command='echo "Data quality is good, proceeding with pipeline."',
    )
    
    # Task for when data quality is bad
    data_quality_alert = BashOperator(
        task_id="data_quality_alert",
        bash_command='echo "Data quality alert! Check the processed data."',
    )
    
    # Task to store data in TimescaleDB
    store_in_timescaledb = BashOperator(
        task_id="store_in_timescaledb",
        bash_command=f"""
            echo "Storing data in TimescaleDB..."
            cd {PROJECT_PATH}
            source .venv/bin/activate
            
            # In a real implementation, you would have a Python script to:
            # 1. Consume messages from processed_sailing_data
            # 2. Transform them for TimescaleDB
            # 3. Insert into the database
            
            # For now, we'll just simulate this
            echo "Simulating data storage in TimescaleDB..."
            sleep 5
            echo "Data stored in TimescaleDB."
        """,
    )
    
    # Set up task dependencies
    check_kafka_topics >> run_sailing_processor >> check_data_quality_task
    check_data_quality_task >> [data_quality_good, data_quality_alert]
    data_quality_good >> store_in_timescaledb


# Create a separate DAG for training the RL model
with DAG(
    dag_id="maritime_model_training",
    default_args=default_args,
    description="Maritime RL model training pipeline",
    schedule_interval="0 0 * * *",  # Run once a day at midnight
    catchup=False,
    max_active_runs=1,
    tags=["maritime", "ml", "reinforcement-learning"],
) as training_dag:
    
    # Wait for data processing to complete
    wait_for_data_processing = ExternalTaskSensor(
        task_id="wait_for_data_processing",
        external_dag_id="maritime_data_pipeline",
        external_task_id="store_in_timescaledb",
        timeout=3600,
        poke_interval=60,
        mode="reschedule",  # Use reschedule mode to free up a worker slot when poking
    )
    
    # Task to prepare training data
    prepare_training_data = BashOperator(
        task_id="prepare_training_data",
        bash_command=f"""
            echo "Preparing training data from TimescaleDB..."
            cd {PROJECT_PATH}
            source .venv/bin/activate
            
            # In a real implementation, you would have a Python script to:
            # 1. Query TimescaleDB for the required time range
            # 2. Prepare features for RL training
            # 3. Save the prepared dataset
            
            # For now, we'll just simulate this
            echo "Simulating training data preparation..."
            sleep 10
            echo "Training data prepared."
        """,
    )
    
    # Task to train the RL model
    train_rl_model = BashOperator(
        task_id="train_rl_model",
        bash_command=f"""
            echo "Training RL model..."
            cd {PROJECT_PATH}
            source .venv/bin/activate
            
            # In a real implementation, you would have a Python script to:
            # 1. Load the prepared dataset
            # 2. Train the RL model
            # 3. Evaluate the model
            # 4. Save the model
            
            # For now, we'll just simulate this
            echo "Simulating RL model training..."
            sleep 30
            echo "RL model trained."
        """,
    )
    
    # Task to deploy the model
    deploy_model = BashOperator(
        task_id="deploy_model",
        bash_command=f"""
            echo "Deploying RL model..."
            cd {PROJECT_PATH}
            source .venv/bin/activate
            
            # In a real implementation, you would have a Python script to:
            # 1. Package the model for deployment
            # 2. Upload to a model registry or deployment target
            # 3. Update the serving endpoint
            
            # For now, we'll just simulate this
            echo "Simulating model deployment..."
            sleep 5
            echo "Model deployed."
        """,
    )
    
    # Set up task dependencies
    wait_for_data_processing >> prepare_training_data >> train_rl_model >> deploy_model 