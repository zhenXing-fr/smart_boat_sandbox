#!/usr/bin/env python3
"""
Monte Carlo visualization component for maritime route optimization dashboard.
Renders multiple trajectory paths from RL model simulations.
"""

import os
import json
import glob
from typing import List, Dict, Any, Optional, Tuple
import logging

import numpy as np
import pandas as pd
from flask import Flask, render_template, jsonify, request, Blueprint

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create Blueprint for Monte Carlo visualization
monte_carlo_bp = Blueprint('monte_carlo', __name__, url_prefix='/monte_carlo')


def load_monte_carlo_data(model_dir: str) -> Dict[str, Any]:
    """
    Load Monte Carlo visualization data from model directory.
    
    Args:
        model_dir: Directory containing model and Monte Carlo data
        
    Returns:
        Dictionary with Monte Carlo visualization data
    """
    monte_carlo_dir = os.path.join(model_dir, "monte_carlo")
    
    if not os.path.exists(monte_carlo_dir):
        logger.warning(f"Monte Carlo directory not found: {monte_carlo_dir}")
        return {"error": "Monte Carlo data not found"}
    
    # Load summary file
    summary_file = os.path.join(monte_carlo_dir, "mc_summary.json")
    if not os.path.exists(summary_file):
        logger.warning(f"Monte Carlo summary file not found: {summary_file}")
        return {"error": "Monte Carlo summary not found"}
    
    with open(summary_file, 'r') as f:
        summary = json.load(f)
    
    # Load vessel summaries
    vessel_data = {}
    for vessel_id in summary.get("vessels", []):
        vessel_dir = os.path.join(monte_carlo_dir, vessel_id)
        vessel_summary_file = os.path.join(vessel_dir, "summary.json")
        
        if os.path.exists(vessel_summary_file):
            with open(vessel_summary_file, 'r') as f:
                vessel_summary = json.load(f)
                
            # Load trajectory data for visualization
            trajectory_data = []
            for trajectory in vessel_summary.get("trajectories", []):
                traj_file = trajectory.get("trajectory_file")
                if traj_file and os.path.exists(traj_file):
                    with open(traj_file, 'r') as f:
                        traj_data = json.load(f)
                        
                    # Add to trajectory data
                    trajectory_data.append({
                        "iteration": trajectory.get("iteration"),
                        "steps": trajectory.get("steps"),
                        "destination_reached": trajectory.get("destination_reached", False),
                        "hazard_hit": trajectory.get("hazard_hit", False),
                        "fuel_depleted": trajectory.get("fuel_depleted", False),
                        "path": [(p.get("position")[0], p.get("position")[1]) 
                                for p in traj_data.get("trajectory", [])],
                        "rewards": [p.get("reward", 0) for p in traj_data.get("trajectory", [])],
                        "fuel_levels": [p.get("fuel_level", 0) for p in traj_data.get("trajectory", [])],
                        "speeds": [p.get("speed", 0) for p in traj_data.get("trajectory", [])]
                    })
            
            vessel_summary["trajectory_data"] = trajectory_data
            vessel_data[vessel_id] = vessel_summary
    
    # Add vessel data to summary
    summary["vessel_data"] = vessel_data
    
    # Add hazards if available in any trajectory
    for vessel_id, vessel_info in vessel_data.items():
        for trajectory in vessel_info.get("trajectories", []):
            traj_file = trajectory.get("trajectory_file")
            if traj_file and os.path.exists(traj_file):
                with open(traj_file, 'r') as f:
                    traj_data = json.load(f)
                    
                if "hazards" in traj_data:
                    summary["hazards"] = traj_data.get("hazards")
                    break
        if "hazards" in summary:
            break
    
    # Add destination if available
    for vessel_id, vessel_info in vessel_data.items():
        for trajectory in vessel_info.get("trajectories", []):
            traj_file = trajectory.get("trajectory_file")
            if traj_file and os.path.exists(traj_file):
                with open(traj_file, 'r') as f:
                    traj_data = json.load(f)
                    
                if "destination" in traj_data:
                    summary["destination"] = traj_data.get("destination")
                    break
        if "destination" in summary:
            break
    
    return summary


def find_latest_model_dir() -> Optional[str]:
    """
    Find the most recent model directory.
    
    Returns:
        Path to the latest model directory, or None if not found
    """
    # Look in various possible locations for Monte Carlo data
    possible_paths = [
        "/opt/airflow/models/rl/monte_carlo",   # Container path (most preferred)
        "/opt/airflow/models/rl",               # Container model dir
        "/opt/airflow/src/maritime/visualization/static/monte_carlo", # Static dir in container
        "models/rl/monte_carlo",                # Relative from current dir 
        "models/rl",                            # Relative model dir
        "../models/rl/monte_carlo",             # One level up
        "../models/rl",                         # One level up model dir
        "../../models/rl/monte_carlo",          # Two levels up
        "static/monte_carlo",                   # Static dir
        "src/maritime/visualization/static/monte_carlo" # Static dir in src
    ]
    
    # First check for directories with mc_summary.json
    for path in possible_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "mc_summary.json")):
            logger.info(f"Found Monte Carlo data directly at: {path}")
            return path
    
    # Then check for rl directories that contain monte_carlo subdirectories
    for path in possible_paths:
        if path.endswith("/monte_carlo"):
            parent_path = os.path.dirname(path)
            if os.path.exists(parent_path) and os.path.exists(path):
                logger.info(f"Found Monte Carlo data at: {path}")
                return parent_path
    
    logger.warning("No model directories found")
    return None


@monte_carlo_bp.route('/')
def monte_carlo_home():
    """Route for Monte Carlo visualization home page."""
    model_dir = find_latest_model_dir()
    if not model_dir:
        return jsonify({"error": "No model directory found"})
    
    monte_carlo_data = load_monte_carlo_data(model_dir)
    if "error" in monte_carlo_data:
        return jsonify(monte_carlo_data)
    
    return jsonify(monte_carlo_data)


@monte_carlo_bp.route('/data')
def monte_carlo_data():
    """Route for Monte Carlo visualization data."""
    model_dir = request.args.get('model_dir')
    if not model_dir:
        model_dir = find_latest_model_dir()
        if not model_dir:
            return jsonify({"error": "No model directory found"})
    
    monte_carlo_data = load_monte_carlo_data(model_dir)
    return jsonify(monte_carlo_data)


@monte_carlo_bp.route('/vessel/<vessel_id>')
def vessel_data(vessel_id):
    """Route for vessel-specific Monte Carlo visualization data."""
    model_dir = request.args.get('model_dir')
    if not model_dir:
        model_dir = find_latest_model_dir()
        if not model_dir:
            return jsonify({"error": "No model directory found"})
    
    monte_carlo_data = load_monte_carlo_data(model_dir)
    if "error" in monte_carlo_data:
        return jsonify(monte_carlo_data)
    
    vessel_data = monte_carlo_data.get("vessel_data", {}).get(vessel_id)
    if not vessel_data:
        return jsonify({"error": f"Vessel {vessel_id} not found"})
    
    return jsonify({
        "vessel_id": vessel_id,
        "vessel_data": vessel_data,
        "hazards": monte_carlo_data.get("hazards"),
        "destination": monte_carlo_data.get("destination")
    })


def register_monte_carlo_routes(app: Flask) -> None:
    """
    Register Monte Carlo routes with Flask app.
    
    Args:
        app: Flask application instance
    """
    app.register_blueprint(monte_carlo_bp)
    logger.info("Monte Carlo visualization routes registered") 