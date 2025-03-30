#!/usr/bin/env python

"""
Kafka topic monitor - displays messages from specified topics in real-time.
"""

import argparse
import json
import os
import sys
import signal
from typing import List

# Add the src directory to the path to make the imports work when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from confluent_kafka import Consumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import MessageField, SerializationContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up colorized output
COLORS = {
    "RESET": "\033[0m",
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "BLUE": "\033[34m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
    "WHITE": "\033[37m",
    "BOLD": "\033[1m",
}


def color_text(text, color):
    """Add color to text."""
    return f"{COLORS.get(color, '')}{text}{COLORS['RESET']}"


def pretty_print_json(data):
    """Pretty print JSON data with colors."""
    formatted = json.dumps(data, indent=2)
    
    # Add some color to keys and values
    lines = formatted.split("\n")
    colored_lines = []
    
    for line in lines:
        if ":" in line:  # It's a key-value pair
            key, value = line.split(":", 1)
            # Color the key
            key = color_text(key, "CYAN")
            # Color values differently based on type
            if value.strip().startswith('"'):  # String
                value = color_text(value, "GREEN")
            elif value.strip() in ["true", "false"]:  # Boolean
                value = color_text(value, "YELLOW")
            elif value.strip().replace(".", "").isdigit():  # Number
                value = color_text(value, "MAGENTA")
            colored_lines.append(f"{key}:{value}")
        else:
            colored_lines.append(line)
    
    return "\n".join(colored_lines)


class KafkaMonitor:
    """Monitor Kafka topics and display messages in real-time."""

    def __init__(
        self,
        topics: List[str],
        bootstrap_servers: str = None,
        schema_registry_url: str = None,
        consumer_group: str = "monitor-consumer",
        use_avro: bool = True,
    ):
        """Initialize the Kafka monitor.
        
        Args:
            topics: List of topics to monitor
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            consumer_group: Consumer group ID
            use_avro: Whether to use Avro deserialization
        """
        self.topics = topics
        self.use_avro = use_avro
        
        # Get configuration from environment variables or parameters
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9093"
        )
        self.schema_registry_url = schema_registry_url or os.getenv(
            "SCHEMA_REGISTRY_URL", "http://localhost:8081"
        )
        
        # Set up Schema Registry client if Avro is enabled
        if use_avro:
            self.schema_registry_client = SchemaRegistryClient({"url": self.schema_registry_url})
            self.avro_deserializers = {}
        
        # Set up consumer
        self.consumer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": consumer_group,
            "auto.offset.reset": "latest",  # Start from the latest message
            "enable.auto.commit": True,
        }
        self.consumer = Consumer(self.consumer_config)
        
        # Subscribe to topics
        self.consumer.subscribe(topics)
        
        # Set up signal handling for graceful shutdown
        self.running = True
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
    
    def handle_signal(self, sig, frame):
        """Handle signals for graceful shutdown."""
        print(f"\n{color_text('Stopping monitor...', 'YELLOW')}")
        self.running = False
    
    def get_avro_deserializer(self, topic):
        """Get or create an Avro deserializer for a topic."""
        if topic not in self.avro_deserializers:
            try:
                # Get the latest schema for the topic
                subject = f"{topic}-value"
                schema_id = self.schema_registry_client.get_latest_version(subject).schema_id
                schema = self.schema_registry_client.get_schema(schema_id)
                self.avro_deserializers[topic] = AvroDeserializer(
                    self.schema_registry_client, schema.schema_str
                )
            except Exception as e:
                print(f"{color_text('Error getting schema for topic', 'RED')} {topic}: {e}")
                # Fall back to JSON
                self.avro_deserializers[topic] = None
        
        return self.avro_deserializers[topic]
    
    def start(self):
        """Start monitoring Kafka topics."""
        # Print banner
        print("\n" + "="*80)
        print(f"{color_text('KAFKA TOPIC MONITOR', 'BOLD')}")
        print("="*80)
        print(f"Monitoring topics: {', '.join(color_text(topic, 'GREEN') for topic in self.topics)}")
        print(f"Bootstrap servers: {color_text(self.bootstrap_servers, 'BLUE')}")
        print(f"Schema Registry URL: {color_text(self.schema_registry_url, 'BLUE')}")
        print(f"Using Avro: {color_text(str(self.use_avro), 'YELLOW')}")
        print(f"{color_text('Press Ctrl+C to stop', 'YELLOW')}")
        print("="*80 + "\n")
        
        message_count = 0
        
        while self.running:
            try:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event - not an error
                        pass
                    else:
                        print(f"{color_text('ERROR:', 'RED')} {msg.error()}")
                    continue
                
                # Get the topic
                topic = msg.topic()
                
                # Get message key
                key = msg.key().decode('utf-8') if msg.key() else None
                
                # Get message timestamp
                if msg.timestamp()[0] == 0:  # TIMESTAMP_NOT_AVAILABLE
                    timestamp = "N/A"
                else:
                    timestamp = msg.timestamp()[1]
                
                # Deserialize the message value
                if self.use_avro:
                    deserializer = self.get_avro_deserializer(topic)
                    if deserializer:
                        try:
                            value = deserializer(
                                msg.value(), SerializationContext(topic, MessageField.VALUE)
                            )
                        except Exception as e:
                            print(f"{color_text('Avro deserialization error:', 'RED')} {e}")
                            # Fall back to treating as JSON
                            try:
                                value = json.loads(msg.value().decode('utf-8'))
                            except:
                                value = msg.value()
                    else:
                        # No Avro deserializer available, try JSON
                        try:
                            value = json.loads(msg.value().decode('utf-8'))
                        except:
                            value = msg.value()
                else:
                    # Try to parse as JSON
                    try:
                        value = json.loads(msg.value().decode('utf-8'))
                    except:
                        value = msg.value()
                
                # Increment message count
                message_count += 1
                
                # Print message details
                print("-"*80)
                print(f"{color_text('MESSAGE', 'BOLD')} #{message_count}")
                print(f"{color_text('Topic:', 'BLUE')} {topic}")
                print(f"{color_text('Partition:', 'BLUE')} {msg.partition()}")
                print(f"{color_text('Offset:', 'BLUE')} {msg.offset()}")
                print(f"{color_text('Timestamp:', 'BLUE')} {timestamp}")
                print(f"{color_text('Key:', 'BLUE')} {key}")
                print(f"{color_text('Value:', 'BLUE')}")
                
                # Pretty print the value if it's a dict
                if isinstance(value, dict):
                    print(pretty_print_json(value))
                else:
                    print(value)
                print("-"*80 + "\n")
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{color_text('Error:', 'RED')} {e}")
        
        # Clean up
        self.consumer.close()
        print(f"{color_text('Monitor stopped', 'YELLOW')}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Kafka Topic Monitor")
    parser.add_argument(
        "--topics", nargs="+", required=True, help="List of topics to monitor"
    )
    parser.add_argument(
        "--bootstrap-servers", type=str, default=None, help="Kafka bootstrap servers"
    )
    parser.add_argument(
        "--schema-registry-url", type=str, default=None, help="Schema Registry URL"
    )
    parser.add_argument(
        "--no-avro", action="store_true", help="Disable Avro deserialization"
    )
    parser.add_argument(
        "--consumer-group", type=str, default="monitor-consumer", help="Consumer group ID"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    monitor = KafkaMonitor(
        topics=args.topics,
        bootstrap_servers=args.bootstrap_servers,
        schema_registry_url=args.schema_registry_url,
        consumer_group=args.consumer_group,
        use_avro=not args.no_avro,
    )
    monitor.start()


if __name__ == "__main__":
    main() 