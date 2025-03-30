"""Base class for Kafka producers with common functionality."""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Add the src directory to the path to make the imports work when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import fastavro
import requests
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class BaseProducer(ABC):
    """Base class for all Kafka producers in the system."""

    def __init__(
        self,
        topic_name: str,
        schema: Dict[str, Any],
        bootstrap_servers: Optional[str] = None,
        schema_registry_url: Optional[str] = None,
        num_partitions: int = 3,
        replication_factor: int = 1,
        client_id: Optional[str] = None,
    ):
        """
        Initialize the base producer.

        Args:
            topic_name: The Kafka topic to produce to
            schema: The Avro schema for message validation
            bootstrap_servers: Kafka bootstrap servers string (host:port)
            schema_registry_url: Schema Registry URL
            num_partitions: Number of partitions for the topic
            replication_factor: Replication factor for the topic
            client_id: Client ID for the producer
        """
        self.topic_name = topic_name
        self.schema = schema
        
        # Use environment variables as defaults if not provided
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.schema_registry_url = schema_registry_url or os.getenv(
            "SCHEMA_REGISTRY_URL", "http://localhost:8081"
        )
        self.client_id = client_id or os.getenv("KAFKA_CLIENT_ID", "maritime-producer")
        
        # Set up Schema Registry client
        self.schema_registry_client = SchemaRegistryClient({"url": self.schema_registry_url})
        
        # Register the schema with the Schema Registry
        self._register_schema()
        
        # Set up the Avro serializer
        self.avro_serializer = AvroSerializer(
            self.schema_registry_client,
            json.dumps(self.schema),
        )
        
        # Kafka producer configuration
        self.producer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            # Add some sensible defaults
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 500,
        }
        
        self.producer = Producer(self.producer_config)
        
        # Create the topic if it doesn't exist
        self._ensure_topic_exists(
            topic_name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
        )
        
        logger.info(
            f"Initialized producer for topic '{topic_name}' "
            f"with bootstrap servers '{self.bootstrap_servers}' "
            f"and schema registry '{self.schema_registry_url}'"
        )
    
    def _register_schema(self) -> None:
        """Register the schema with the Schema Registry."""
        schema_subject = f"{self.topic_name}-value"
        schema_str = json.dumps(self.schema)
        
        try:
            # Check if schema already exists
            subject_versions = f"{self.schema_registry_url}/subjects/{schema_subject}/versions"
            response = requests.get(subject_versions)
            
            if response.status_code == 404 or (response.status_code == 200 and len(response.json()) == 0):
                # Register new schema
                register_url = f"{self.schema_registry_url}/subjects/{schema_subject}/versions"
                headers = {"Content-Type": "application/vnd.schemaregistry.v1+json"}
                payload = {"schema": schema_str}
                
                response = requests.post(register_url, headers=headers, json=payload)
                
                if response.status_code in (200, 201):
                    schema_id = response.json().get("id")
                    logger.info(f"Registered schema for topic '{self.topic_name}' with ID {schema_id}")
                else:
                    logger.error(f"Failed to register schema: {response.text}")
            else:
                logger.info(f"Schema for '{schema_subject}' already exists in the registry")
        
        except Exception as e:
            logger.error(f"Error registering schema: {e}")
    
    def _ensure_topic_exists(
        self, topic_name: str, num_partitions: int, replication_factor: int
    ) -> None:
        """
        Ensure that the Kafka topic exists, creating it if necessary.
        
        Args:
            topic_name: The name of the topic to check/create
            num_partitions: Number of partitions for the topic if created
            replication_factor: Replication factor for the topic if created
        """
        admin_client = AdminClient({"bootstrap.servers": self.bootstrap_servers})
        
        # Check if topic exists
        topic_metadata = admin_client.list_topics(timeout=10)
        
        if topic_name not in topic_metadata.topics:
            logger.info(f"Topic '{topic_name}' does not exist. Creating...")
            topic_list = [
                NewTopic(
                    topic_name,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor,
                )
            ]
            
            try:
                admin_client.create_topics(topic_list)
                logger.info(
                    f"Created topic '{topic_name}' with {num_partitions} partitions "
                    f"and replication factor {replication_factor}"
                )
            except Exception as e:
                logger.error(f"Failed to create topic '{topic_name}': {e}")
        else:
            logger.info(f"Topic '{topic_name}' already exists")
    
    def _delivery_report(self, err, msg) -> None:
        """
        Callback function for delivery reports.
        
        Args:
            err: Error object (None if no error)
            msg: Message object
        """
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
            )
    
    def _validate_with_schema(self, record: Dict[str, Any]) -> bool:
        """
        Validate a record against the Avro schema.
        
        Args:
            record: Record to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            fastavro.parse_schema(self.schema)
            fastavro.validate(record, self.schema)
            return True
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            logger.debug(f"Failed record: {json.dumps(record, indent=2)}")
            return False
    
    def send_message(self, record: Dict[str, Any], key: Optional[str] = None) -> bool:
        """
        Send a single message to the Kafka topic.
        
        Args:
            record: The record to send
            key: Optional message key
            
        Returns:
            bool: True if the message was sent, False otherwise
        """
        if not self._validate_with_schema(record):
            return False
        
        try:
            # Serialize record using Schema Registry
            serialized_data = self.avro_serializer(
                record, SerializationContext(self.topic_name, MessageField.VALUE)
            )
            
            # Send message
            self.producer.produce(
                topic=self.topic_name,
                key=key.encode("utf-8") if key else None,
                value=serialized_data,
                callback=self._delivery_report,
            )
            
            # Trigger any available delivery report callbacks
            self.producer.poll(0)
            
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def send_batch(self, records: List[Dict[str, Any]], key_field: Optional[str] = None) -> int:
        """
        Send a batch of messages to the Kafka topic.
        
        Args:
            records: List of records to send
            key_field: Optional field name to use as message key
            
        Returns:
            int: Number of messages successfully queued
        """
        success_count = 0
        
        for record in records:
            key = record.get(key_field) if key_field else None
            if self.send_message(record, str(key) if key else None):
                success_count += 1
        
        # Flush to ensure all messages are sent
        self.producer.flush()
        
        return success_count
    
    def close(self) -> None:
        """Close the producer and release resources."""
        self.producer.flush()
        logger.info(f"Producer for topic '{self.topic_name}' closed")
    
    @abstractmethod
    def generate_data(self) -> List[Dict[str, Any]]:
        """
        Generate data records to be sent to Kafka.
        
        This method should be implemented by subclasses.
        
        Returns:
            List of records to send
        """
        pass 