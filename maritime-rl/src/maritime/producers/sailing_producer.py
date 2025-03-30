"""Producer for vessel sailing data."""

import argparse
import logging
import signal
import sys
import time
from typing import Any, Dict, List, Optional

# Add the src directory to the path to make the imports work when running directly
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.maritime.data.generators import VesselDataGenerator
from src.maritime.producers.base_producer import BaseProducer
from src.maritime.schemas.sailing import SAILING_SCHEMA

logger = logging.getLogger(__name__)


class SailingDataProducer(BaseProducer):
    """Producer for vessel sailing data."""

    def __init__(
        self,
        topic_name: str = "vessel_sailing_data",
        bootstrap_servers: Optional[str] = None,
        schema_registry_url: Optional[str] = None,
        num_vessels: int = 5,
        time_interval_hours: float = 1.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize the sailing data producer.

        Args:
            topic_name: Kafka topic name
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            num_vessels: Number of vessels to simulate
            time_interval_hours: Time interval between data points
            seed: Random seed for reproducibility
        """
        super().__init__(
            topic_name=topic_name,
            schema=SAILING_SCHEMA,
            bootstrap_servers=bootstrap_servers,
            schema_registry_url=schema_registry_url,
        )
        self.num_vessels = num_vessels
        self.time_interval_hours = time_interval_hours
        self.generator = VesselDataGenerator(seed=seed, num_vessels=num_vessels)
        logger.info(
            f"Initialized sailing data producer with {num_vessels} vessels "
            f"and {time_interval_hours}h interval"
        )

    def generate_data(self) -> List[Dict[str, Any]]:
        """
        Generate sailing data for all vessels.

        Returns:
            List of sailing records
        """
        return self.generator.generate_sailing_record(time_delta_hours=self.time_interval_hours)

    def run(self, iterations: Optional[int] = None, interval_seconds: float = 1.0):
        """
        Run the producer to continually generate and send data.

        Args:
            iterations: Number of iterations to run (None for infinite)
            interval_seconds: Sleep interval between iterations
        """
        logger.info(
            f"Starting sailing data producer, iterations={iterations}, "
            f"interval={interval_seconds}s"
        )

        # Set up signal handling for graceful shutdown
        running = True

        def handle_signal(sig, frame):
            nonlocal running
            logger.info(f"Received signal {sig}, shutting down...")
            running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        count = 0
        try:
            while running and (iterations is None or count < iterations):
                records = self.generate_data()
                success_count = self.send_batch(records, key_field="vessel_id")
                logger.info(f"Sent {success_count}/{len(records)} sailing records")

                count += 1
                if iterations is not None:
                    logger.info(f"Completed iteration {count}/{iterations}")

                # Sleep for the specified interval
                if running and (iterations is None or count < iterations):
                    time.sleep(interval_seconds)

        except Exception as e:
            logger.error(f"Error in producer run loop: {e}")
            raise
        finally:
            self.close()
            logger.info("Sailing data producer shut down")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Sailing Data Producer")
    parser.add_argument(
        "--bootstrap-servers", type=str, default=None, help="Kafka bootstrap servers"
    )
    parser.add_argument(
        "--schema-registry-url", type=str, default=None, help="Schema Registry URL"
    )
    parser.add_argument(
        "--topic", type=str, default="vessel_sailing_data", help="Kafka topic name"
    )
    parser.add_argument(
        "--vessels", type=int, default=5, help="Number of vessels to simulate"
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Time interval in hours between data points"
    )
    parser.add_argument(
        "--sleep", type=float, default=1.0, help="Sleep seconds between producer iterations"
    )
    parser.add_argument(
        "--iterations", type=int, default=None, help="Number of iterations (default: infinite)"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    producer = SailingDataProducer(
        topic_name=args.topic,
        bootstrap_servers=args.bootstrap_servers,
        schema_registry_url=args.schema_registry_url,
        num_vessels=args.vessels,
        time_interval_hours=args.interval,
        seed=args.seed,
    )
    producer.run(iterations=args.iterations, interval_seconds=args.sleep)


if __name__ == "__main__":
    main() 