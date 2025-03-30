#!/usr/bin/env python3
"""Dashboard for visualizing maritime route optimization data."""

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
from flask import Flask, render_template, jsonify, flash, request
from kafka import KafkaConsumer

# Import Monte Carlo visualization
from .monte_carlo_viz import register_monte_carlo_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = os.environ.get("SECRET_KEY", "maritime_optimization_key")

# Configuration from environment variables
USE_MOCK_DATA = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"  # Default to false to use real data
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
PROCESSED_TOPIC = os.environ.get("PROCESSED_TOPIC", "processed_sailing_data")
DB_HOST = os.environ.get("DB_HOST", "localhost")  # Changed from timescaledb to localhost
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
        error_msg = f"Failed to connect to database: {e}"
        logger.error(error_msg)
        flash(f"Database connection error: {error_msg}", "danger")
        if USE_MOCK_DATA:
            return None
        else:
            raise RuntimeError(f"Cannot connect to database and mock data is disabled: {error_msg}")


def get_processed_data(limit: int = 50) -> List[Dict[str, Any]]:
    """Get the most recent processed vessel data from TimescaleDB."""
    conn = get_db_connection()
    if not conn and USE_MOCK_DATA:
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
            
            if not rows:
                if USE_MOCK_DATA:
                    logger.warning("No data found in database, using mock data")
                    return mock_recent_data
                else:
                    flash("No vessel telemetry data found in the database", "warning")
                    return []
            
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
        error_msg = f"Error querying database: {e}"
        logger.error(error_msg)
        flash(error_msg, "danger")
        if USE_MOCK_DATA:
            return mock_recent_data
        else:
            return []
    finally:
        conn.close()


def get_vessel_data() -> List[Dict[str, Any]]:
    """Get current vessel positions and routes from TimescaleDB."""
    conn = get_db_connection()
    if not conn and USE_MOCK_DATA:
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
            
            if not rows:
                if USE_MOCK_DATA:
                    logger.warning("No vessel data found in database, using mock data")
                    return mock_vessels
                else:
                    flash("No vessel position data found in the database", "warning")
                    return []
            
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
            
            return vessels if vessels else (mock_vessels if USE_MOCK_DATA else [])
    except Exception as e:
        error_msg = f"Error querying vessel data: {e}"
        logger.error(error_msg)
        flash(error_msg, "danger")
        if USE_MOCK_DATA:
            return mock_vessels
        else:
            return []
    finally:
        conn.close()


def get_quality_metrics() -> tuple:
    """Get data quality metrics for charting."""
    conn = get_db_connection()
    if not conn and USE_MOCK_DATA:
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
                if USE_MOCK_DATA:
                    # No data yet, return mock data
                    return (
                        ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
                        [45, 52, 48, 58, 62, 50],
                        [5, 3, 8, 2, 1, 4],
                    )
                else:
                    flash("No quality metrics data found for the past 6 hours", "warning")
                    return ([], [], [])
            
            labels = [row[0].strftime("%H:%M") for row in rows]
            valid_data = [row[1] for row in rows]
            invalid_data = [row[2] for row in rows]
            
            return labels, valid_data, invalid_data
    except Exception as e:
        error_msg = f"Error querying quality metrics: {e}"
        logger.error(error_msg)
        flash(error_msg, "danger")
        if USE_MOCK_DATA:
            # Mock data for quality metrics
            return (
                ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
                [45, 52, 48, 58, 62, 50],
                [5, 3, 8, 2, 1, 4],
            )
        else:
            return ([], [], [])
    finally:
        conn.close()


def get_fuel_consumption_data() -> tuple:
    """Get fuel consumption data for charting."""
    conn = get_db_connection()
    if not conn and USE_MOCK_DATA:
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
                if USE_MOCK_DATA:
                    # No data yet, return mock data
                    return (
                        ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
                        [22.5, 24.1, 23.8, 25.5, 21.2, 20.8],
                        [20.1, 21.5, 21.2, 22.8, 19.5, 19.2],
                    )
                else:
                    flash("No fuel consumption data found for the past 6 hours", "warning")
                    return ([], [], [])
            
            labels = [row[0].strftime("%H:%M") for row in rows]
            fuel_data = [float(row[1]) for row in rows]
            
            # In a real system, we would calculate optimized fuel usage based on model predictions
            # For now, just estimate 10% savings
            optimized_fuel_data = [fuel * 0.9 for fuel in fuel_data]
            
            return labels, fuel_data, optimized_fuel_data
    except Exception as e:
        error_msg = f"Error querying fuel consumption: {e}"
        logger.error(error_msg)
        flash(error_msg, "danger")
        if USE_MOCK_DATA:
            # Mock data for fuel consumption
            return (
                ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
                [22.5, 24.1, 23.8, 25.5, 21.2, 20.8],
                [20.1, 21.5, 21.2, 22.8, 19.5, 19.2],
            )
        else:
            return ([], [], [])
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
    if not conn and USE_MOCK_DATA:
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
            
            metrics = {
                "active_vessels": active_vessels,
                "data_quality_pct": data_quality_pct,
                "avg_fuel_efficiency": avg_fuel_efficiency,
                "optimization_savings": optimization_savings,
                "data_latency": data_latency,
            }
            
            if all(v == 0 for v in metrics.values()) and USE_MOCK_DATA:
                logger.warning("No aggregate metrics found in database, using mock data")
                return {
                    "active_vessels": len(mock_vessels),
                    "data_quality_pct": 85,
                    "avg_fuel_efficiency": 3.8,
                    "optimization_savings": 12,
                    "data_latency": 5,
                }
                
            return metrics
    except Exception as e:
        error_msg = f"Error querying aggregate metrics: {e}"
        logger.error(error_msg)
        flash(error_msg, "danger")
        if USE_MOCK_DATA:
            # Mock metrics
            return {
                "active_vessels": len(mock_vessels),
                "data_quality_pct": 85,
                "avg_fuel_efficiency": 3.8,
                "optimization_savings": 12,
                "data_latency": 5,
            }
        else:
            return {
                "active_vessels": 0,
                "data_quality_pct": 0,
                "avg_fuel_efficiency": 0,
                "optimization_savings": 0,
                "data_latency": 0,
            }
    finally:
        conn.close()


@app.route("/")
def index():
    """Route for dashboard home page."""
    vessels = get_vessel_data()
    recent_data = get_processed_data(10)  # Get the 10 most recent records
    
    quality_metrics = get_quality_metrics()
    fuel_consumption = get_fuel_consumption_data()
    
    return render_template(
        'dashboard_template.html',
        page='dashboard',
        vessels=vessels,
        active_vessels=len(vessels),
        data_quality_pct=int(quality_metrics[1][-1]),
        avg_fuel_efficiency="{:.2f}".format(fuel_consumption[1][-1]),
        optimization_savings="{:.1f}".format(fuel_consumption[2][-1] - fuel_consumption[1][-1]),
        recent_data=recent_data,
        use_mock_data=USE_MOCK_DATA,
        last_updated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        monte_carlo_url="/monte_carlo_page"
    )


@app.route("/vessels")
def vessels_page():
    """Render the vessels details page."""
    now = datetime.datetime.now()
    vessels = get_vessel_data()
    vessel_data_json = json.dumps(vessels)
    
    # Get vessel-specific metrics
    # In a real system, you'd query these from the database
    vessel_metrics = {
        vessel["id"]: {
            "distance_traveled": round(10 + float(vessel["id"].split("_")[1]) * 5, 1),
            "avg_speed": round(8 + float(vessel["id"].split("_")[1]) * 0.5, 1),
            "fuel_efficiency": round(3.5 - float(vessel["id"].split("_")[1]) * 0.1, 1),
            "optimization_gain": round(10 + float(vessel["id"].split("_")[1]) * 0.8, 1),
        }
        for vessel in vessels
    }
    
    return render_template(
        "vessels_template.html",
        page="vessels",
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S"),
        vessels=vessels,
        vessel_data=vessel_data_json,
        vessel_metrics=vessel_metrics,
    )


@app.route("/routes")
def routes_page():
    """Render the routes optimization page."""
    now = datetime.datetime.now()
    vessels = get_vessel_data()
    vessel_data_json = json.dumps(vessels)
    
    # Get route comparison data
    # This would come from your ML model results in a real system
    route_comparisons = [
        {
            "vessel_id": "vessel_1",
            "vessel_name": "Baltic Trader",
            "route_type": "Optimized",
            "distance": 245.8,
            "estimated_time": "18h 30m",
            "fuel_consumption": 3250.5,
            "cost_savings": "12.5%",
            "co2_reduction": "10.8%",
            "weather_risk": "Low",
        },
        {
            "vessel_id": "vessel_1",
            "vessel_name": "Baltic Trader",
            "route_type": "Traditional",
            "distance": 267.3,
            "estimated_time": "20h 15m",
            "fuel_consumption": 3715.8,
            "cost_savings": "-",
            "co2_reduction": "-",
            "weather_risk": "Medium",
        },
        {
            "vessel_id": "vessel_2",
            "vessel_name": "Nordic Star",
            "route_type": "Optimized",
            "distance": 198.5,
            "estimated_time": "16h 45m",
            "fuel_consumption": 2875.2,
            "cost_savings": "8.3%",
            "co2_reduction": "7.5%",
            "weather_risk": "Low",
        },
        {
            "vessel_id": "vessel_2",
            "vessel_name": "Nordic Star",
            "route_type": "Traditional",
            "distance": 210.2,
            "estimated_time": "17h 30m",
            "fuel_consumption": 3135.8,
            "cost_savings": "-",
            "co2_reduction": "-",
            "weather_risk": "Low",
        },
    ]
    
    return render_template(
        "routes_template.html",
        page="routes",
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S"),
        vessels=vessels,
        vessel_data=vessel_data_json,
        route_comparisons=route_comparisons,
    )


@app.route("/data_quality")
def data_quality_page():
    """Render the data quality metrics page."""
    now = datetime.datetime.now()
    
    # Get quality metrics for charts
    quality_labels, quality_valid_data, quality_invalid_data = get_quality_metrics()
    
    # Get detailed quality metrics
    # In a real system, these would be calculated from your data pipeline
    detailed_metrics = [
        {
            "metric": "Missing Values",
            "current": "0.8%",
            "trend": "↓ 0.2%",
            "status": "good",
        },
        {
            "metric": "Duplicate Records",
            "current": "0.1%",
            "trend": "↔ 0.0%",
            "status": "good",
        },
        {
            "metric": "Anomalies",
            "current": "2.3%",
            "trend": "↑ 0.5%",
            "status": "warning",
        },
        {
            "metric": "Latency",
            "current": "5.2s",
            "trend": "↓ 0.8s",
            "status": "good",
        },
        {
            "metric": "Schema Compliance",
            "current": "99.7%",
            "trend": "↑ 0.1%",
            "status": "good",
        },
        {
            "metric": "Data Freshness",
            "current": "98.2%",
            "trend": "↓ 0.3%",
            "status": "good",
        },
    ]
    
    # Get recent validation failures
    validation_failures = [
        {
            "timestamp": "2024-06-18 10:18:42",
            "vessel_id": "vessel_3",
            "error_type": "Out of range value",
            "field": "speed",
            "value": "85.2",
            "expected": "0-30",
        },
        {
            "timestamp": "2024-06-18 10:15:36",
            "vessel_id": "vessel_1",
            "error_type": "Invalid coordinates",
            "field": "position.longitude",
            "value": "190.5",
            "expected": "-180 to 180",
        },
        {
            "timestamp": "2024-06-18 10:12:18",
            "vessel_id": "vessel_2",
            "error_type": "Missing value",
            "field": "weather_conditions.wave_height",
            "value": "null",
            "expected": "numeric",
        },
    ]
    
    return render_template(
        "data_quality_template.html",
        page="data_quality",
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S"),
        quality_labels=json.dumps(quality_labels),
        quality_valid_data=json.dumps(quality_valid_data),
        quality_invalid_data=json.dumps(quality_invalid_data),
        detailed_metrics=detailed_metrics,
        validation_failures=validation_failures,
    )


@app.route("/models")
def models_page():
    """Render the models metrics page."""
    now = datetime.datetime.now()
    
    # Get model versions and status
    # In a real system, this would come from your model registry
    model_versions = [
        {
            "id": "mro-v1.2.5",
            "name": "Route Optimizer",
            "version": "1.2.5",
            "status": "Deployed",
            "deployed_at": "2024-06-15 08:30",
            "accuracy": "92.3%",
            "fuel_savings": "11.8%",
            "training_data": "2024-05-01 to 2024-06-01",
        },
        {
            "id": "mro-v1.2.4",
            "name": "Route Optimizer",
            "version": "1.2.4",
            "status": "Archived",
            "deployed_at": "2024-05-20 14:15",
            "accuracy": "91.7%",
            "fuel_savings": "10.5%",
            "training_data": "2024-04-01 to 2024-05-01",
        },
        {
            "id": "mro-v1.3.0-beta",
            "name": "Route Optimizer",
            "version": "1.3.0-beta",
            "status": "Testing",
            "deployed_at": "2024-06-17 11:45",
            "accuracy": "94.1%",
            "fuel_savings": "13.2%",
            "training_data": "2024-05-01 to 2024-06-10",
        },
    ]
    
    # Training metrics over time
    training_metrics = {
        "dates": ["2024-05-01", "2024-05-10", "2024-05-20", "2024-06-01", "2024-06-10"],
        "reward": [156, 185, 210, 235, 258],
        "loss": [0.42, 0.38, 0.31, 0.28, 0.25],
        "fuel_efficiency": [3.8, 3.7, 3.5, 3.4, 3.2],
    }
    
    return render_template(
        "models_template.html",
        page="models",
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S"),
        model_versions=model_versions,
        training_metrics=json.dumps(training_metrics),
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


# Register Monte Carlo routes with app
register_monte_carlo_routes(app)

@app.route('/monte_carlo_page')
def monte_carlo_page():
    """Render the Monte Carlo visualization page."""
    return render_template(
        'monte_carlo_template.html',
        page='monte_carlo',
        use_mock_data=USE_MOCK_DATA,
        last_updated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


def main():
    """Run the dashboard application."""
    logger.info("Starting Maritime Route Optimization Dashboard")
    app.run(host="0.0.0.0", port=5501, debug=True)


if __name__ == "__main__":
    main() 