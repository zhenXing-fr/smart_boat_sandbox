#!/usr/bin/env python3
"""Dashboard for visualizing maritime route optimization data."""

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
from flask import Flask, render_template, jsonify
from kafka import KafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configuration (normally should be in environment variables)
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
PROCESSED_TOPIC = os.environ.get("PROCESSED_TOPIC", "processed_sailing_data")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "maritime")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_NAME = os.environ.get("DB_NAME", "maritime")

# Global state for mock data when DB/Kafka is not available
mock_vessels = [
    {
        "id": "vessel_1",
        "name": "Baltic Trader",
        "speed": 12.5,
        "heading": 45,
        "lat": 56.15,
        "lng": 11.2,
        "fuel_consumption": 25.3,
        "quality_score": 0.92,
        "last_update": "2 min ago",
        "route": [
            [56.10, 11.0],
            [56.15, 11.2],
            [56.25, 11.5],
        ],
        "optimized_route": [
            [56.10, 11.0],
            [56.12, 11.3],
            [56.25, 11.5],
        ],
    },
    {
        "id": "vessel_2",
        "name": "Nordic Star",
        "speed": 10.2,
        "heading": 90,
        "lat": 55.8,
        "lng": 12.1,
        "fuel_consumption": 18.7,
        "quality_score": 0.78,
        "last_update": "5 min ago",
        "route": [
            [55.7, 11.9],
            [55.8, 12.1],
            [55.9, 12.4],
        ],
    },
    {
        "id": "vessel_3",
        "name": "Atlantic Voyager",
        "speed": 8.1,
        "heading": 270,
        "lat": 57.2,
        "lng": 10.5,
        "fuel_consumption": 15.2,
        "quality_score": 0.65,
        "last_update": "12 min ago",
    },
]

mock_recent_data = [
    {
        "timestamp": "2024-06-18 10:15:22",
        "vessel_name": "Baltic Trader",
        "position": "56.15, 11.2",
        "speed": 12.5,
        "heading": 45,
        "fuel_consumption": 25.3,
        "quality_score": 0.92,
    },
    {
        "timestamp": "2024-06-18 10:10:18",
        "vessel_name": "Nordic Star",
        "position": "55.8, 12.1",
        "speed": 10.2,
        "heading": 90,
        "fuel_consumption": 18.7,
        "quality_score": 0.78,
    },
    {
        "timestamp": "2024-06-18 10:05:45",
        "vessel_name": "Atlantic Voyager",
        "position": "57.2, 10.5",
        "speed": 8.1,
        "heading": 270,
        "fuel_consumption": 15.2,
        "quality_score": 0.65,
    },
]


def get_db_connection() -> Optional[psycopg2.extensions.connection]:
    """Get a connection to the TimescaleDB."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def get_processed_data(limit: int = 50) -> List[Dict[str, Any]]:
    """Get the most recent processed vessel data from TimescaleDB."""
    conn = get_db_connection()
    if not conn:
        logger.warning("Using mock data because database connection failed")
        return mock_recent_data

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    timestamp, 
                    vessel_id, 
                    ST_AsText(position) as position, 
                    speed, 
                    heading, 
                    fuel_consumption, 
                    quality_score
                FROM 
                    vessel_telemetry
                ORDER BY 
                    timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            
            result = []
            for row in rows:
                # Parse position from WKT format (POINT(lng lat))
                position_text = row[2].replace("POINT(", "").replace(")", "")
                lng, lat = position_text.split()
                
                result.append({
                    "timestamp": row[0].strftime("%Y-%m-%d %H:%M:%S"),
                    "vessel_name": f"Vessel {row[1]}",  # In a real system, we'd join with a vessel table
                    "position": f"{lat}, {lng}",
                    "speed": row[3],
                    "heading": row[4],
                    "fuel_consumption": row[5],
                    "quality_score": row[6],
                })
            
            return result
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        return mock_recent_data
    finally:
        conn.close()


def get_vessel_data() -> List[Dict[str, Any]]:
    """Get current vessel positions and routes from TimescaleDB."""
    conn = get_db_connection()
    if not conn:
        logger.warning("Using mock vessel data because database connection failed")
        return mock_vessels

    try:
        with conn.cursor() as cur:
            # Get the most recent data point for each vessel
            cur.execute(
                """
                WITH latest_positions AS (
                    SELECT DISTINCT ON (vessel_id)
                        vessel_id,
                        timestamp,
                        position,
                        speed,
                        heading,
                        fuel_consumption,
                        quality_score
                    FROM vessel_telemetry
                    ORDER BY vessel_id, timestamp DESC
                )
                SELECT 
                    vessel_id,
                    ST_X(position::geometry) as lng,
                    ST_Y(position::geometry) as lat,
                    speed,
                    heading,
                    fuel_consumption,
                    quality_score,
                    timestamp
                FROM latest_positions
                """
            )
            rows = cur.fetchall()
            
            # Get recent history for each vessel to show route
            vessels = []
            for row in rows:
                vessel_id = row[0]
                
                # Get recent positions to create route
                cur.execute(
                    """
                    SELECT 
                        ST_X(position::geometry) as lng,
                        ST_Y(position::geometry) as lat
                    FROM vessel_telemetry
                    WHERE vessel_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 20
                    """,
                    (vessel_id,),
                )
                route_points = cur.fetchall()
                route = [[lat, lng] for lng, lat in route_points]
                
                # In a real system, we would look up optimized routes from a separate table
                # and include them if available
                optimized_route = None
                
                vessel = {
                    "id": vessel_id,
                    "name": f"Vessel {vessel_id}",  # In a real system, we'd join with a vessel table
                    "speed": row[3],
                    "heading": row[4],
                    "lat": row[2],
                    "lng": row[1],
                    "fuel_consumption": row[5],
                    "quality_score": row[6],
                    "last_update": get_relative_time(row[7]),
                    "route": route if route else None,
                }
                
                # Add optimized route if we have it
                if vessel_id == "vessel_1" and not optimized_route:
                    # Mock data for vessel_1
                    vessel["optimized_route"] = [
                        [route[0][0], route[0][1]],
                        [route[0][0] + 0.02, route[0][1] + 0.3],
                        [route[-1][0], route[-1][1]],
                    ]
                
                vessels.append(vessel)
            
            return vessels if vessels else mock_vessels
    except Exception as e:
        logger.error(f"Error querying vessel data: {e}")
        return mock_vessels
    finally:
        conn.close()


def get_quality_metrics() -> tuple:
    """Get data quality metrics for charting."""
    conn = get_db_connection()
    if not conn:
        # Mock data for quality metrics
        return (
            ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
            [45, 52, 48, 58, 62, 50],
            [5, 3, 8, 2, 1, 4],
        )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    time_bucket('1 hour', timestamp) AS hour,
                    SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) AS valid_records,
                    SUM(CASE WHEN quality_score < 0.7 THEN 1 ELSE 0 END) AS invalid_records
                FROM vessel_telemetry
                WHERE timestamp > NOW() - INTERVAL '6 hours'
                GROUP BY hour
                ORDER BY hour
                """
            )
            rows = cur.fetchall()
            
            if not rows:
                # No data yet, return mock data
                return (
                    ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
                    [45, 52, 48, 58, 62, 50],
                    [5, 3, 8, 2, 1, 4],
                )
            
            labels = [row[0].strftime("%H:%M") for row in rows]
            valid_data = [row[1] for row in rows]
            invalid_data = [row[2] for row in rows]
            
            return labels, valid_data, invalid_data
    except Exception as e:
        logger.error(f"Error querying quality metrics: {e}")
        # Mock data for quality metrics
        return (
            ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
            [45, 52, 48, 58, 62, 50],
            [5, 3, 8, 2, 1, 4],
        )
    finally:
        conn.close()


def get_fuel_consumption_data() -> tuple:
    """Get fuel consumption data for charting."""
    conn = get_db_connection()
    if not conn:
        # Mock data for fuel consumption
        return (
            ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
            [22.5, 24.1, 23.8, 25.5, 21.2, 20.8],
            [20.1, 21.5, 21.2, 22.8, 19.5, 19.2],
        )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    time_bucket('1 hour', timestamp) AS hour,
                    AVG(fuel_consumption) AS avg_fuel
                FROM vessel_telemetry
                WHERE timestamp > NOW() - INTERVAL '6 hours'
                GROUP BY hour
                ORDER BY hour
                """
            )
            rows = cur.fetchall()
            
            if not rows:
                # No data yet, return mock data
                return (
                    ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
                    [22.5, 24.1, 23.8, 25.5, 21.2, 20.8],
                    [20.1, 21.5, 21.2, 22.8, 19.5, 19.2],
                )
            
            labels = [row[0].strftime("%H:%M") for row in rows]
            fuel_data = [float(row[1]) for row in rows]
            
            # In a real system, we would calculate optimized fuel usage based on model predictions
            # For now, just estimate 10% savings
            optimized_fuel_data = [fuel * 0.9 for fuel in fuel_data]
            
            return labels, fuel_data, optimized_fuel_data
    except Exception as e:
        logger.error(f"Error querying fuel consumption: {e}")
        # Mock data for fuel consumption
        return (
            ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
            [22.5, 24.1, 23.8, 25.5, 21.2, 20.8],
            [20.1, 21.5, 21.2, 22.8, 19.5, 19.2],
        )
    finally:
        conn.close()


def get_relative_time(timestamp: datetime.datetime) -> str:
    """Convert timestamp to relative time string (e.g., '5 min ago')."""
    now = datetime.datetime.now(timestamp.tzinfo)
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} days ago"
    
    hours = diff.seconds // 3600
    if hours > 0:
        return f"{hours} hours ago"
    
    minutes = (diff.seconds % 3600) // 60
    if minutes > 0:
        return f"{minutes} min ago"
    
    return "just now"


def get_aggregate_metrics() -> Dict[str, Any]:
    """Get aggregate metrics for the dashboard."""
    conn = get_db_connection()
    if not conn:
        # Mock metrics
        return {
            "active_vessels": len(mock_vessels),
            "data_quality_pct": 85,
            "avg_fuel_efficiency": 3.8,
            "optimization_savings": 12,
            "data_latency": 5,
        }

    try:
        with conn.cursor() as cur:
            # Count active vessels (those with data in the last hour)
            cur.execute(
                """
                SELECT COUNT(DISTINCT vessel_id)
                FROM vessel_telemetry
                WHERE timestamp > NOW() - INTERVAL '1 hour'
                """
            )
            active_vessels = cur.fetchone()[0]
            
            # Average quality score for recent data
            cur.execute(
                """
                SELECT AVG(quality_score) * 100
                FROM vessel_telemetry
                WHERE timestamp > NOW() - INTERVAL '6 hours'
                """
            )
            quality_result = cur.fetchone()
            data_quality_pct = int(quality_result[0]) if quality_result[0] else 0
            
            # Average fuel efficiency
            cur.execute(
                """
                SELECT AVG(fuel_consumption / speed)
                FROM vessel_telemetry
                WHERE timestamp > NOW() - INTERVAL '6 hours'
                  AND speed > 0
                """
            )
            efficiency_result = cur.fetchone()
            avg_fuel_efficiency = round(efficiency_result[0], 1) if efficiency_result[0] else 0
            
            # Optimization savings would come from the ML model
            # For now, using a mock value
            optimization_savings = 12
            
            # Data latency (time since latest record)
            cur.execute(
                """
                SELECT NOW() - MAX(timestamp)
                FROM vessel_telemetry
                """
            )
            latency_result = cur.fetchone()
            if latency_result[0]:
                data_latency = int(latency_result[0].total_seconds())
            else:
                data_latency = 0
            
            return {
                "active_vessels": active_vessels,
                "data_quality_pct": data_quality_pct,
                "avg_fuel_efficiency": avg_fuel_efficiency,
                "optimization_savings": optimization_savings,
                "data_latency": data_latency,
            }
    except Exception as e:
        logger.error(f"Error querying aggregate metrics: {e}")
        # Mock metrics
        return {
            "active_vessels": len(mock_vessels),
            "data_quality_pct": 85,
            "avg_fuel_efficiency": 3.8,
            "optimization_savings": 12,
            "data_latency": 5,
        }
    finally:
        conn.close()


@app.route("/")
def dashboard():
    """Render the dashboard."""
    now = datetime.datetime.now()
    
    # Get vessel and route data
    vessels = get_vessel_data()
    vessel_data_json = json.dumps(vessels)
    
    # Get recent data points
    recent_data = get_processed_data(limit=10)
    
    # Get quality metrics for chart
    quality_labels, quality_valid_data, quality_invalid_data = get_quality_metrics()
    
    # Get fuel consumption data for chart
    fuel_labels, fuel_data, optimized_fuel_data = get_fuel_consumption_data()
    
    # Get aggregate metrics
    metrics = get_aggregate_metrics()
    
    return render_template(
        "dashboard_template.html",
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S"),
        vessels=vessels,
        vessel_data=vessel_data_json,
        recent_data=recent_data,
        quality_labels=json.dumps(quality_labels),
        quality_valid_data=json.dumps(quality_valid_data),
        quality_invalid_data=json.dumps(quality_invalid_data),
        fuel_labels=json.dumps(fuel_labels),
        fuel_data=json.dumps(fuel_data),
        optimized_fuel_data=json.dumps(optimized_fuel_data),
        active_vessels=metrics["active_vessels"],
        data_quality_pct=metrics["data_quality_pct"],
        avg_fuel_efficiency=metrics["avg_fuel_efficiency"],
        optimization_savings=metrics["optimization_savings"],
        data_latency=metrics["data_latency"],
    )


@app.route("/api/vessels")
def api_vessels():
    """API endpoint to get vessel data."""
    vessels = get_vessel_data()
    return jsonify(vessels)


@app.route("/api/recent-data")
def api_recent_data():
    """API endpoint to get recent data points."""
    recent_data = get_processed_data(limit=50)
    return jsonify(recent_data)


def main():
    """Run the dashboard application."""
    logger.info("Starting Maritime Route Optimization Dashboard")
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main() 