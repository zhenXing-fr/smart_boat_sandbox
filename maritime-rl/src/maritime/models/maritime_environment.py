import numpy as np
import gym
from gym import spaces
from typing import Dict, Tuple, List, Optional, Any
import json
import os
import datetime

class MaritimeEnvironment(gym.Env):
    """
    A maritime environment for reinforcement learning that simulates vessel navigation
    with realistic dynamics, weather effects, and hazards.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the maritime environment with optional configuration.
        
        Args:
            config: Dictionary containing configuration parameters
        """
        super(MaritimeEnvironment, self).__init__()
        
        # Default configuration
        self.config = {
            "max_steps": 500,
            "weather_change_probability": 0.1,
            "hazard_density": 0.05,
            "fuel_capacity": 100.0,
            "destination": (59.3293, 18.0686),  # Stockholm coordinates
            "starting_positions": [
                (55.6761, 12.5683),  # Copenhagen
                (60.1695, 24.9354),  # Helsinki
                (59.9139, 10.7522),  # Oslo
            ],
            "map_bounds": {
                "lat_min": 54.0,
                "lat_max": 61.0,
                "lon_min": 9.0,
                "lon_max": 26.0
            }
        }
        
        # Update with provided configuration
        if config:
            self.config.update(config)
        
        # Environment state
        self.steps = 0
        self.position = None
        self.heading = None
        self.speed = None
        self.fuel_level = None
        self.weather = None
        self.hazards = None
        self.destination = self.config["destination"]
        self.trajectory = []
        self.vessel_id = None
        
        # Define action and observation spaces
        # Actions: [speed_change, heading_change]
        self.action_space = spaces.Box(
            low=np.array([-2.0, -15.0]),
            high=np.array([2.0, 15.0]),
            dtype=np.float32
        )
        
        # Observations: [lat, lon, speed, heading, fuel_level, 
        #                wind_speed, wind_direction, wave_height, 
        #                distance_to_destination, hazard_proximity]
        self.observation_space = spaces.Box(
            low=np.array([
                self.config["map_bounds"]["lat_min"],
                self.config["map_bounds"]["lon_min"],
                0.0,  # min speed
                0.0,  # min heading
                0.0,  # min fuel
                0.0,  # min wind speed
                0.0,  # min wind direction
                0.0,  # min wave height
                0.0,  # min distance to destination
                0.0,  # min hazard proximity
            ]),
            high=np.array([
                self.config["map_bounds"]["lat_max"],
                self.config["map_bounds"]["lon_max"],
                30.0,  # max speed
                360.0,  # max heading
                self.config["fuel_capacity"],  # max fuel
                50.0,  # max wind speed
                360.0,  # max wind direction
                10.0,  # max wave height
                1000.0,  # max distance to destination
                1.0,  # max hazard proximity (normalized)
            ]),
            dtype=np.float32
        )
    
    def reset(self, vessel_id: Optional[str] = None) -> np.ndarray:
        """
        Reset the environment to an initial state and return the initial observation.
        
        Args:
            vessel_id: Optional vessel identifier
            
        Returns:
            Initial observation
        """
        self.steps = 0
        self.trajectory = []
        
        # Set vessel ID
        self.vessel_id = vessel_id or f"vessel_{np.random.randint(1, 100)}"
        
        # Set initial position
        start_idx = np.random.randint(0, len(self.config["starting_positions"]))
        self.position = self.config["starting_positions"][start_idx]
        
        # Set initial vessel state
        self.heading = np.random.uniform(0, 360)
        self.speed = np.random.uniform(5.0, 15.0)
        self.fuel_level = self.config["fuel_capacity"]
        
        # Generate weather conditions
        self.weather = self._generate_weather()
        
        # Generate hazards
        self.hazards = self._generate_hazards()
        
        # Get initial observation
        obs = self._get_observation()
        
        # Store initial state in trajectory
        self._record_trajectory_point(0.0)  # Initial reward is 0
        
        return obs
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Take a step in the environment using the provided action.
        
        Args:
            action: Array with [speed_change, heading_change]
            
        Returns:
            observation: Current observation
            reward: Reward for the action
            done: Whether the episode is finished
            info: Additional information
        """
        # Increment step counter
        self.steps += 1
        
        # Extract action components
        speed_change, heading_change = action
        
        # Apply actions
        self._update_vessel_state(speed_change, heading_change)
        
        # Maybe update weather
        if np.random.random() < self.config["weather_change_probability"]:
            self.weather = self._update_weather(self.weather)
        
        # Calculate next position based on heading, speed, and weather
        self._update_position()
        
        # Get new observation
        obs = self._get_observation()
        
        # Calculate rewards and check terminal conditions
        reward, done, info = self._calculate_reward_and_done()
        
        # Record trajectory point
        self._record_trajectory_point(reward)
        
        # Check if maximum steps reached
        if self.steps >= self.config["max_steps"]:
            done = True
            info["termination_reason"] = "max_steps_reached"
        
        return obs, reward, done, info
    
    def _update_vessel_state(self, speed_change: float, heading_change: float) -> None:
        """
        Update vessel state based on actions.
        
        Args:
            speed_change: Change in speed (knots)
            heading_change: Change in heading (degrees)
        """
        # Update speed with constraints
        self.speed = max(0.0, min(30.0, self.speed + speed_change))
        
        # Update heading and keep within [0, 360)
        self.heading = (self.heading + heading_change) % 360
        
        # Update fuel level based on speed and weather
        fuel_consumption = self._calculate_fuel_consumption()
        self.fuel_level = max(0.0, self.fuel_level - fuel_consumption)
    
    def _update_position(self) -> None:
        """Update vessel position based on heading, speed, and weather conditions."""
        # Convert heading to radians
        heading_rad = np.radians(self.heading)
        
        # Calculate weather effect on movement
        weather_effect = self._calculate_weather_effect()
        
        # Calculate distance moved (in degrees, simplified)
        # In a more accurate simulation, we would use proper geodesic calculations
        speed_factor = self.speed / 600.0  # Convert knots to approximate degrees per step
        
        # Apply movement with weather effects
        lat_change = speed_factor * np.cos(heading_rad) + weather_effect["lat"]
        lon_change = speed_factor * np.sin(heading_rad) + weather_effect["lon"]
        
        # Update position with bounds checking
        new_lat = max(self.config["map_bounds"]["lat_min"], 
                      min(self.config["map_bounds"]["lat_max"], 
                          self.position[0] + lat_change))
        new_lon = max(self.config["map_bounds"]["lon_min"], 
                      min(self.config["map_bounds"]["lon_max"], 
                          self.position[1] + lon_change))
        
        self.position = (new_lat, new_lon)
    
    def _calculate_weather_effect(self) -> Dict[str, float]:
        """
        Calculate the effect of weather on vessel movement.
        
        Returns:
            Dictionary with lat and lon effects
        """
        wind_speed = self.weather["wind_speed"]
        wind_direction_rad = np.radians(self.weather["wind_direction"])
        wave_height = self.weather["wave_height"]
        
        # Combined weather effect (simplified model)
        weather_strength = (wind_speed / 50.0) + (wave_height / 10.0)
        
        # Direction of the effect
        lat_effect = weather_strength * np.cos(wind_direction_rad) * 0.002
        lon_effect = weather_strength * np.sin(wind_direction_rad) * 0.002
        
        return {"lat": lat_effect, "lon": lon_effect}
    
    def _calculate_fuel_consumption(self) -> float:
        """
        Calculate fuel consumption based on speed and weather.
        
        Returns:
            Fuel consumption for the current step
        """
        # Base consumption increases quadratically with speed
        base_consumption = 0.01 * (self.speed ** 2) / 100.0
        
        # Weather effect
        wind_factor = self.weather["wind_speed"] / 20.0
        wave_factor = self.weather["wave_height"] / 5.0
        weather_multiplier = 1.0 + wind_factor + wave_factor
        
        return base_consumption * weather_multiplier
    
    def _calculate_reward_and_done(self) -> Tuple[float, bool, Dict]:
        """
        Calculate reward and determine if episode is done.
        
        Returns:
            reward: Calculated reward
            done: Whether episode is done
            info: Additional information
        """
        reward = 0.0
        done = False
        info = {}
        
        # Calculate distance to destination
        distance_to_destination = self._haversine_distance(self.position, self.destination)
        info["distance_to_destination"] = distance_to_destination
        
        # Distance progress reward
        if hasattr(self, 'previous_distance'):
            distance_progress = self.previous_distance - distance_to_destination
            reward += distance_progress * 10.0  # Reward for getting closer
        
        self.previous_distance = distance_to_destination
        
        # Check if destination reached
        if distance_to_destination < 0.1:  # ~11km in real distance
            reward += 100.0  # Big bonus for reaching destination
            done = True
            info["termination_reason"] = "destination_reached"
        
        # Fuel efficiency reward
        fuel_consumption = self._calculate_fuel_consumption()
        if self.speed > 0:
            efficiency = 1.0 / (fuel_consumption * self.speed)
            reward += efficiency * 0.1
        
        # Penalty for running out of fuel
        if self.fuel_level <= 0:
            reward -= 50.0
            done = True
            info["termination_reason"] = "out_of_fuel"
        
        # Hazard penalties
        hazard_penalty, closest_hazard = self._calculate_hazard_penalty()
        reward -= hazard_penalty
        info["closest_hazard_distance"] = closest_hazard
        
        # Check if hit hazard (very close to it)
        if closest_hazard < 0.02:  # Very close to hazard
            reward -= 100.0  # Big penalty
            done = True
            info["termination_reason"] = "hit_hazard"
        
        # Boundary penalty
        boundary_penalty = self._calculate_boundary_penalty()
        reward -= boundary_penalty
        
        # Weather condition penalties
        weather_risk = self._calculate_weather_risk()
        reward -= weather_risk * 0.5
        
        info["reward_components"] = {
            "distance_progress": distance_progress * 10.0 if hasattr(self, 'previous_distance') else 0.0,
            "destination_bonus": 100.0 if distance_to_destination < 0.1 else 0.0,
            "efficiency": efficiency * 0.1 if self.speed > 0 else 0.0,
            "hazard_penalty": -hazard_penalty,
            "boundary_penalty": -boundary_penalty,
            "weather_risk": -weather_risk * 0.5,
            "fuel_penalty": -50.0 if self.fuel_level <= 0 else 0.0
        }
        
        return reward, done, info
    
    def _calculate_hazard_penalty(self) -> Tuple[float, float]:
        """
        Calculate penalty for proximity to hazards.
        
        Returns:
            hazard_penalty: Penalty value
            closest_distance: Distance to closest hazard
        """
        closest_distance = float('inf')
        penalty = 0.0
        
        for hazard in self.hazards:
            distance = self._haversine_distance(self.position, hazard["position"])
            if distance < hazard["radius"]:
                # Inside hazard radius
                penalty_factor = 1.0 - (distance / hazard["radius"])
                hazard_penalty = hazard["severity"] * penalty_factor * 10.0
                penalty += hazard_penalty
            
            closest_distance = min(closest_distance, distance)
        
        return penalty, closest_distance
    
    def _calculate_boundary_penalty(self) -> float:
        """
        Calculate penalty for approaching map boundaries.
        
        Returns:
            Boundary penalty value
        """
        lat, lon = self.position
        bounds = self.config["map_bounds"]
        
        # Calculate distances to each boundary
        dist_to_lat_min = lat - bounds["lat_min"]
        dist_to_lat_max = bounds["lat_max"] - lat
        dist_to_lon_min = lon - bounds["lon_min"]
        dist_to_lon_max = bounds["lon_max"] - lon
        
        # Find minimum distance to any boundary
        min_dist = min(dist_to_lat_min, dist_to_lat_max, dist_to_lon_min, dist_to_lon_max)
        
        # Penalty increases as vessel gets closer to boundary
        if min_dist < 0.5:  # Within 0.5 degrees of boundary
            return (0.5 - min_dist) * 20.0
        
        return 0.0
    
    def _calculate_weather_risk(self) -> float:
        """
        Calculate risk factor based on weather conditions and vessel state.
        
        Returns:
            Weather risk value
        """
        # Simplified risk model
        wind_speed = self.weather["wind_speed"]
        wave_height = self.weather["wave_height"]
        
        # Higher speeds in bad weather increase risk
        speed_factor = self.speed / 10.0
        
        # Calculate risk
        risk = (wind_speed / 50.0) * (wave_height / 5.0) * speed_factor
        
        return risk
    
    def _get_observation(self) -> np.ndarray:
        """
        Get the current observation state.
        
        Returns:
            Numpy array of observations
        """
        lat, lon = self.position
        distance_to_destination = self._haversine_distance(self.position, self.destination)
        
        # Calculate hazard proximity (normalized to [0,1])
        hazard_proximity = 0.0
        if self.hazards:
            min_distance = float('inf')
            for hazard in self.hazards:
                distance = self._haversine_distance(self.position, hazard["position"])
                normalized_distance = min(1.0, distance / hazard["radius"])
                min_distance = min(min_distance, normalized_distance)
            
            hazard_proximity = 1.0 - min_distance if min_distance != float('inf') else 0.0
        
        return np.array([
            lat,
            lon,
            self.speed,
            self.heading,
            self.fuel_level,
            self.weather["wind_speed"],
            self.weather["wind_direction"],
            self.weather["wave_height"],
            distance_to_destination,
            hazard_proximity
        ], dtype=np.float32)
    
    def _generate_weather(self) -> Dict[str, float]:
        """
        Generate weather conditions.
        
        Returns:
            Dictionary of weather parameters
        """
        return {
            "wind_speed": np.random.uniform(0.0, 30.0),  # knots
            "wind_direction": np.random.uniform(0.0, 360.0),  # degrees
            "wave_height": np.random.uniform(0.0, 5.0),  # meters
            "current_speed": np.random.uniform(0.0, 3.0),  # knots
            "current_direction": np.random.uniform(0.0, 360.0),  # degrees
        }
    
    def _update_weather(self, current_weather: Dict[str, float]) -> Dict[str, float]:
        """
        Update weather conditions gradually.
        
        Args:
            current_weather: Current weather state
            
        Returns:
            Updated weather state
        """
        new_weather = current_weather.copy()
        
        # Add random changes
        new_weather["wind_speed"] = max(0, min(50, current_weather["wind_speed"] + 
                                            np.random.normal(0, 2.0)))
        new_weather["wind_direction"] = (current_weather["wind_direction"] + 
                                      np.random.normal(0, 10.0)) % 360
        new_weather["wave_height"] = max(0, min(10, current_weather["wave_height"] + 
                                             np.random.normal(0, 0.3)))
        new_weather["current_speed"] = max(0, min(5, current_weather["current_speed"] + 
                                               np.random.normal(0, 0.2)))
        new_weather["current_direction"] = (current_weather["current_direction"] + 
                                         np.random.normal(0, 5.0)) % 360
        
        return new_weather
    
    def _generate_hazards(self) -> List[Dict[str, Any]]:
        """
        Generate maritime hazards.
        
        Returns:
            List of hazard objects
        """
        num_hazards = int(self.config["hazard_density"] * 100)
        hazards = []
        
        for _ in range(num_hazards):
            # Random position within map bounds
            lat = np.random.uniform(self.config["map_bounds"]["lat_min"], 
                                  self.config["map_bounds"]["lat_max"])
            lon = np.random.uniform(self.config["map_bounds"]["lon_min"], 
                                  self.config["map_bounds"]["lon_max"])
            
            hazard_types = ["shallow_water", "traffic_zone", "restricted_area", "storm"]
            hazard_type = np.random.choice(hazard_types)
            
            # Severity between 1-5
            severity = np.random.randint(1, 6)
            
            # Radius between 0.05-0.2 degrees
            radius = np.random.uniform(0.05, 0.2)
            
            hazards.append({
                "type": hazard_type,
                "position": (lat, lon),
                "severity": severity,
                "radius": radius,
                "description": f"{hazard_type.replace('_', ' ').title()} - Severity {severity}"
            })
        
        return hazards
    
    def _haversine_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """
        Calculate the great circle distance between two points in degrees.
        
        Args:
            pos1: (latitude, longitude) of first point
            pos2: (latitude, longitude) of second point
            
        Returns:
            Distance in degrees
        """
        lat1, lon1 = pos1
        lat2, lon2 = pos2
        
        # Simple Euclidean distance in degrees as an approximation
        # In a real system, we would use proper haversine formula
        return np.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def _record_trajectory_point(self, reward: float) -> None:
        """
        Record current state for trajectory visualization.
        
        Args:
            reward: Current reward
        """
        self.trajectory.append({
            "step": self.steps,
            "timestamp": datetime.datetime.now().isoformat(),
            "position": self.position,
            "speed": self.speed,
            "heading": self.heading,
            "fuel_level": self.fuel_level,
            "weather": self.weather,
            "reward": reward
        })
    
    def save_trajectory(self, filepath: str) -> None:
        """
        Save the current trajectory to a file.
        
        Args:
            filepath: Path to save the trajectory
        """
        trajectory_data = {
            "vessel_id": self.vessel_id,
            "start_time": self.trajectory[0]["timestamp"] if self.trajectory else None,
            "end_time": self.trajectory[-1]["timestamp"] if self.trajectory else None,
            "steps": len(self.trajectory),
            "destination": self.destination,
            "hazards": self.hazards,
            "trajectory": self.trajectory
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(trajectory_data, f, indent=2)
    
    def render(self, mode: str = 'human') -> None:
        """
        Render the environment (simplified text output).
        
        Args:
            mode: Rendering mode
        """
        if mode == 'human':
            print(f"Step: {self.steps}")
            print(f"Position: Lat {self.position[0]:.4f}, Lon {self.position[1]:.4f}")
            print(f"Speed: {self.speed:.2f} knots, Heading: {self.heading:.2f} degrees")
            print(f"Fuel: {self.fuel_level:.2f} units")
            print(f"Weather: Wind {self.weather['wind_speed']:.1f} knots at {self.weather['wind_direction']:.1f}°, " 
                  f"Waves {self.weather['wave_height']:.1f}m")
            
            dist = self._haversine_distance(self.position, self.destination)
            print(f"Distance to destination: {dist:.2f} degrees")
            print("-" * 40) 