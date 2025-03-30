"""Kafka Streams processor for sailing data."""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# Add the src directory to the path to make the imports work when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext
from dotenv import load_dotenv

from src.maritime.schemas.sailing import SAILING_SCHEMA

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SailingProcessor:
    """Kafka Streams processor for sailing data.
    
    This processor reads data from the sailing topic, applies validation and transformations,
    and writes the processed data to an output topic.
    """

    def __init__(
        self,
        input_topic: str,
        output_topic: str,
        bootstrap_servers: Optional[str] = None,
        schema_registry_url: Optional[str] = None,
        consumer_group: str = "sailing-processor",
        auto_offset_reset: str = "earliest",
    ):
        """Initialize the sailing processor.
        
        Args:
            input_topic: The input Kafka topic
            output_topic: The output Kafka topic
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            consumer_group: Consumer group ID
            auto_offset_reset: Auto offset reset policy
        """
        self.input_topic = input_topic
        self.output_topic = output_topic
        
        # Get bootstrap servers and schema registry URL from environment or parameters
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9093"
        )
        self.schema_registry_url = schema_registry_url or os.getenv(
            "SCHEMA_REGISTRY_URL", "http://localhost:8081"
        )
        
        # Set up Schema Registry client
        self.schema_registry_client = SchemaRegistryClient({"url": self.schema_registry_url})
        
        # Set up Avro serializer and deserializer
        self.avro_deserializer = AvroDeserializer(
            self.schema_registry_client,
            json.dumps(SAILING_SCHEMA),
        )
        
        # Output schema is the same as input schema for now - in real implementation, 
        # you would add additional fields for quality gates, etc.
        self.avro_serializer = AvroSerializer(
            self.schema_registry_client,
            json.dumps(SAILING_SCHEMA),
        )
        
        # Set up consumer
        self.consumer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": consumer_group,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": False,
        }
        self.consumer = Consumer(self.consumer_config)
        
        # Set up producer
        self.producer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": "sailing-processor",
        }
        self.producer = Producer(self.producer_config)
        
        logger.info(
            f"Initialized sailing processor: {input_topic} -> {output_topic}, "
            f"bootstrap servers: {self.bootstrap_servers}, "
            f"schema registry: {self.schema_registry_url}"
        )
    
    def _delivery_report(self, err, msg):
        """Delivery report callback for Kafka producer."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
            )
    
    def _validate_record(self, record: Dict) -> bool:
        """Validate the sailing record.
        
        Args:
            record: The sailing record to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation
        if record is None:
            return False
        
        # Required fields
        required_fields = ["vessel_id", "timestamp", "position", "speed", "heading", "fuel_consumption"]
        if not all(field in record for field in required_fields):
            logger.warning(f"Record missing required fields: {record}")
            return False
        
        # Value range checks
        if record["speed"] < 0 or record["speed"] > 50:  # Max speed in knots
            logger.warning(f"Invalid speed: {record['speed']}")
            return False
        
        if record["fuel_consumption"] < 0 or record["fuel_consumption"] > 100:
            logger.warning(f"Invalid fuel consumption: {record['fuel_consumption']}")
            return False
        
        # Position checks (Mediterranean roughly)
        lat = record["position"]["latitude"]
        lon = record["position"]["longitude"]
        if lat < 30 or lat > 50 or lon < 0 or lon > 40:
            logger.warning(f"Position outside Mediterranean: {lat}, {lon}")
            return False
        
        return True
    
    def _apply_quality_gates(self, record: Dict) -> Dict:
        """Apply quality gates to the sailing record.
        
        Args:
            record: The sailing record to check
            
        Returns:
            Enriched record with quality metrics
        """
        # In a real implementation, you would add more sophisticated quality checks
        # and enrichment here. For now, we just pass through valid records.
        
        # Simple quality metrics
        quality_metrics = {
            "is_valid": True,
            "validation_timestamp": int(time.time()),
            "quality_score": 1.0,  # 0.0 to 1.0 scale
        }
        
        # In a real implementation, you would add these fields to the record
        # For now, we'll just log them
        logger.debug(f"Quality metrics for vessel {record['vessel_id']}: {quality_metrics}")
        
        return record
    
    def _enrich_record(self, record: Dict) -> Dict:
        """Enrich the sailing record with additional data.
        
        Args:
            record: The sailing record to enrich
            
        Returns:
            Enriched record
        """
        # In a real implementation, you would enrich the record with additional data,
        # such as weather forecasts, historical performance, etc.
        
        # For now, we'll just pass through the record
        return record
    
    def _process_record(self, record: Dict) -> Optional[Dict]:
        """Process a single sailing record.
        
        Args:
            record: The sailing record to process
            
        Returns:
            Processed record, or None if the record should be discarded
        """
        # Validate
        if not self._validate_record(record):
            return None
        
        # Apply quality gates
        record = self._apply_quality_gates(record)
        
        # Enrich
        record = self._enrich_record(record)
        
        return record
    
    def start(self, duration_seconds: Optional[int] = None):
        """Start the processor.
        
        Args:
            duration_seconds: Optional duration to run, or None for indefinite
        """
        # Subscribe to input topic
        self.consumer.subscribe([self.input_topic])
        
        start_time = time.time()
        running = True
        records_processed = 0
        records_valid = 0
        
        try:
            logger.info(f"Starting to process records from {self.input_topic}")
            
            while running:
                # Check if we've reached the duration limit
                if duration_seconds is not None and time.time() - start_time > duration_seconds:
                    logger.info(f"Reached duration limit of {duration_seconds} seconds")
                    break
                
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event - not an error
                        logger.debug(f"Reached end of partition {msg.partition()}")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                # Deserialize the message
                try:
                    sailing_record = self.avro_deserializer(
                        msg.value(), SerializationContext(self.input_topic, MessageField.VALUE)
                    )
                    records_processed += 1
                    
                    # Process the record
                    processed_record = self._process_record(sailing_record)
                    
                    # If the record is valid, produce it to the output topic
                    if processed_record:
                        records_valid += 1
                        serialized_data = self.avro_serializer(
                            processed_record,
                            SerializationContext(self.output_topic, MessageField.VALUE)
                        )
                        
                        # Use vessel_id as key for partitioning
                        key = processed_record.get("vessel_id", "").encode("utf-8")
                        
                        self.producer.produce(
                            topic=self.output_topic,
                            key=key,
                            value=serialized_data,
                            callback=self._delivery_report,
                        )
                        
                        # Trigger delivery reports
                        self.producer.poll(0)
                    
                    # Commit the offset
                    self.consumer.commit(asynchronous=False)
                    
                    # Log progress periodically
                    if records_processed % 100 == 0:
                        logger.info(
                            f"Processed {records_processed} records, {records_valid} valid "
                            f"({records_valid / records_processed * 100:.1f}% valid)"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except KeyboardInterrupt:
            logger.info("Interrupted, shutting down")
        
        finally:
            # Clean up
            self.consumer.close()
            self.producer.flush()
            
            logger.info(
                f"Processor finished: processed {records_processed} records, "
                f"{records_valid} valid ({records_valid / max(1, records_processed) * 100:.1f}% valid)"
            )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Sailing Data Processor")
    parser.add_argument(
        "--bootstrap-servers", type=str, default=None, help="Kafka bootstrap servers"
    )
    parser.add_argument(
        "--schema-registry-url", type=str, default=None, help="Schema Registry URL"
    )
    parser.add_argument(
        "--input-topic", type=str, default="vessel_sailing_data", help="Input topic name"
    )
    parser.add_argument(
        "--output-topic", type=str, default="processed_sailing_data", help="Output topic name"
    )
    parser.add_argument(
        "--consumer-group", type=str, default="sailing-processor", help="Consumer group ID"
    )
    parser.add_argument(
        "--duration", type=int, default=None, help="Duration to run in seconds (default: indefinite)"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    processor = SailingProcessor(
        input_topic=args.input_topic,
        output_topic=args.output_topic,
        bootstrap_servers=args.bootstrap_servers,
        schema_registry_url=args.schema_registry_url,
        consumer_group=args.consumer_group,
    )
    processor.start(duration_seconds=args.duration)


if __name__ == "__main__":
    main() 