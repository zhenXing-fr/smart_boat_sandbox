#!/bin/bash

# Check if TimescaleDB is running
if ! docker ps | grep -q "timescaledb"; then
  echo "TimescaleDB is not running. Start it with ./scripts/start_producer.sh"
  exit 1
fi

# Connect to the TimescaleDB container's psql
echo "Connecting to TimescaleDB..."
echo "Username: maritime"
echo "Password: password"
echo "Database: maritime"
echo ""
echo "Available tables:"
echo " - vessel_telemetry"
echo " - data_quality_metrics"
echo " - route_predictions"
echo ""
echo "Available views:"
echo " - vessel_performance"
echo " - daily_vessel_stats (materialized)"
echo ""
echo "Example queries:"
echo " - SELECT * FROM vessel_telemetry LIMIT 10;"
echo " - SELECT time_bucket('1 hour', timestamp) AS hour, vessel_id, AVG(speed) FROM vessel_telemetry GROUP BY hour, vessel_id ORDER BY hour DESC LIMIT 20;"
echo ""

docker exec -it timescaledb psql -U maritime -d maritime 