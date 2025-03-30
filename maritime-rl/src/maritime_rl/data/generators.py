"""Generates synthetic maritime data for simulation and testing."""

import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import numpy as np


class VesselDataGenerator:
    """Generates synthetic vessel data based on realistic patterns."""

    # Mediterranean coordinates (roughly)
    MED_LAT_MIN, MED_LAT_MAX = 35.0, 45.0
    MED_LON_MIN, MED_LON_MAX = 5.0, 30.0
    
    # Common vessel speeds (in knots)
    VESSEL_SPEEDS = {
        "cargo": (8, 20),
        "tanker": (10, 15),
        "passenger": (15, 25),
        "fishing": (5, 12)
    }
    
    # Major Mediterranean ports
    MAJOR_PORTS = [
        # Name, (latitude, longitude)
        ("Marseille", (43.2965, 5.3698)),
        ("Barcelona", (41.3851, 2.1734)),
        ("Naples", (40.8518, 14.2681)),
        ("Piraeus", (37.9421, 23.6466)),
        ("Alexandria", (31.2001, 29.9187)),
        ("Valencia", (39.4699, 0.3763)),
        ("Genoa", (44.4056, 8.9463)),
        ("Istanbul", (41.0082, 28.9784)),
    ]
    
    def __init__(self, seed: Optional[int] = None, num_vessels: int = 5):
        """Initialize the generator with optional random seed."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        self.num_vessels = num_vessels
        self.vessels = self._create_vessels(num_vessels)
        self.current_time = int(time.time())
        
    def _create_vessels(self, count: int) -> List[Dict]:
        """Create vessels with initial properties."""
        vessels = []
        types = list(self.VESSEL_SPEEDS.keys())
        
        for i in range(count):
            vessel_type = random.choice(types)
            origin_port, destination_port = random.sample(self.MAJOR_PORTS, 2)
            
            vessel = {
                "id": f"vessel_{i+1:03d}",
                "type": vessel_type,
                "origin": origin_port,
                "destination": destination_port,
                "position": origin_port[1],  # Start at origin port
                "heading": self._calculate_bearing(*origin_port[1], *destination_port[1]),
                "speed": random.uniform(*self.VESSEL_SPEEDS[vessel_type]),
                "progress": 0.0,  # Progress from 0 to 1
                "route_length": self._haversine_distance(*origin_port[1], *destination_port[1])
            }
            vessels.append(vessel)
            
        return vessels
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in km using haversine formula."""
        R = 6371.0  # Earth radius in km
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate initial bearing between two points in degrees."""
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        
        x = np.sin(lon2 - lon1) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(lon2 - lon1)
        
        bearing = np.arctan2(x, y)
        bearing = np.degrees(bearing)
        bearing = (bearing + 360) % 360  # Normalize to 0-360
        
        return bearing
    
    def _interpolate_position(self, origin: Tuple[float, float], 
                             destination: Tuple[float, float], 
                             progress: float) -> Tuple[float, float]:
        """Interpolate between origin and destination based on progress (0-1)."""
        # This is a simple linear interpolation - actual maritime routes would follow 
        # more complex paths using great circles
        lat = origin[0] + progress * (destination[0] - origin[0])
        lon = origin[1] + progress * (destination[1] - origin[1])
        return (lat, lon)
    
    def _generate_weather_at_position(self, lat: float, lon: float, 
                                     timestamp: int) -> Dict:
        """Generate realistic weather conditions for a position."""
        # Use timestamp to add seasonal variations - simplified model
        day_of_year = datetime.fromtimestamp(timestamp).timetuple().tm_yday
        season_factor = np.sin(day_of_year / 365 * 2 * np.pi)  # -1 to 1
        
        # Mediterranean weather tends to be calmer - adjust accordingly
        base_wind = 5 + 10 * abs(season_factor)  # 5-15 knots base
        wind_variation = np.random.normal(0, 2)  # Add some randomness
        wind_speed = max(0, base_wind + wind_variation)
        
        # Wave height correlates with wind speed
        wave_height = wind_speed * 0.1 + np.random.normal(0, 0.3)
        wave_height = max(0, wave_height)  # No negative waves
        
        # Current speed is generally lower
        current_speed = np.random.uniform(0, 2) + abs(season_factor)
        
        return {
            "wind_speed": wind_speed,
            "wave_height": wave_height,
            "current_speed": current_speed
        }
    
    def _update_vessel_position(self, vessel: Dict, time_delta: float) -> Dict:
        """Update a vessel's position and attributes based on time delta (in hours)."""
        # Calculate distance traveled
        speed_km_h = vessel["speed"] * 1.852  # Convert knots to km/h
        distance_traveled = speed_km_h * time_delta
        
        # Update progress
        new_progress = vessel["progress"] + (distance_traveled / vessel["route_length"])
        vessel["progress"] = min(1.0, new_progress)  # Cap at 1.0
        
        # Update position
        origin_pos = vessel["origin"][1]
        dest_pos = vessel["destination"][1]
        vessel["position"] = self._interpolate_position(origin_pos, dest_pos, vessel["progress"])
        
        # Add some variation to speed and heading
        vessel["speed"] += np.random.normal(0, 0.2)  # Small speed variations
        vessel["speed"] = max(min(vessel["speed"], 
                                  self.VESSEL_SPEEDS[vessel["type"]][1]), 
                              self.VESSEL_SPEEDS[vessel["type"]][0])
        
        # Small heading variations (simulating course corrections)
        ideal_heading = self._calculate_bearing(*vessel["position"], *dest_pos)
        vessel["heading"] = ideal_heading + np.random.normal(0, 2)
        vessel["heading"] = vessel["heading"] % 360  # Normalize
        
        # Calculate fuel consumption based on vessel type and speed
        if vessel["type"] == "cargo":
            base_consumption = 5.0  # tons per hour
        elif vessel["type"] == "tanker":
            base_consumption = 7.0
        elif vessel["type"] == "passenger":
            base_consumption = 4.0
        else:  # fishing
            base_consumption = 2.0
            
        # Adjust for speed (consumption increases faster than linearly with speed)
        speed_factor = (vessel["speed"] / self.VESSEL_SPEEDS[vessel["type"]][0])**1.5
        vessel["fuel_consumption"] = base_consumption * speed_factor
        
        # Add weather at vessel's position
        vessel["weather"] = self._generate_weather_at_position(
            vessel["position"][0], vessel["position"][1], self.current_time)
        
        # Check if arrived at destination
        if vessel["progress"] >= 0.99:
            # Swap origin and destination for return journey
            vessel["origin"], vessel["destination"] = vessel["destination"], vessel["origin"]
            vessel["position"] = vessel["origin"][1]
            vessel["progress"] = 0.0
            vessel["heading"] = self._calculate_bearing(*vessel["origin"][1], *vessel["destination"][1])
            vessel["route_length"] = self._haversine_distance(*vessel["origin"][1], *vessel["destination"][1])
        
        return vessel
    
    def generate_sailing_record(self, time_delta_hours: float = 1.0) -> List[Dict]:
        """Generate a batch of sailing records for all vessels."""
        self.current_time += int(time_delta_hours * 3600)  # Update time
        records = []
        
        for vessel in self.vessels:
            updated_vessel = self._update_vessel_position(vessel, time_delta_hours)
            
            # Create sailing record
            record = {
                "vessel_id": updated_vessel["id"],
                "timestamp": self.current_time,
                "position": {
                    "latitude": updated_vessel["position"][0],
                    "longitude": updated_vessel["position"][1]
                },
                "speed": updated_vessel["speed"],
                "heading": updated_vessel["heading"],
                "fuel_consumption": updated_vessel["fuel_consumption"],
                "weather_conditions": updated_vessel["weather"]
            }
            records.append(record)
            
        return records


class WeatherGenerator:
    """Generates synthetic weather data for maritime regions."""
    
    # Mediterranean grid parameters
    MED_LAT_MIN, MED_LAT_MAX = 35.0, 45.0
    MED_LON_MIN, MED_LON_MAX = 5.0, 30.0
    GRID_RESOLUTION = 1.0  # Grid size in degrees
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize the weather generator."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        self.current_time = int(time.time())
        self.grid_points = self._create_grid()
        
        # Weather patterns - (center_lat, center_lon, radius, intensity)
        # These will evolve over time to create realistic weather patterns
        self.weather_patterns = self._initialize_weather_patterns()
        
    def _create_grid(self) -> List[Tuple[float, float]]:
        """Create a grid of points covering the Mediterranean."""
        grid = []
        for lat in np.arange(self.MED_LAT_MIN, self.MED_LAT_MAX, self.GRID_RESOLUTION):
            for lon in np.arange(self.MED_LON_MIN, self.MED_LON_MAX, self.GRID_RESOLUTION):
                grid.append((lat, lon))
        return grid
    
    def _initialize_weather_patterns(self, num_patterns: int = 5) -> List[Dict]:
        """Initialize weather patterns that will move and evolve."""
        patterns = []
        for _ in range(num_patterns):
            pattern = {
                "center": (
                    random.uniform(self.MED_LAT_MIN, self.MED_LAT_MAX),
                    random.uniform(self.MED_LON_MIN, self.MED_LON_MAX)
                ),
                "radius": random.uniform(1.0, 3.0),  # Size in degrees
                "intensity": random.uniform(0.2, 1.0),  # 0 to 1 scale
                "movement": (
                    random.uniform(-0.2, 0.2),  # Lat movement per hour
                    random.uniform(-0.2, 0.2)   # Lon movement per hour
                ),
                "type": random.choice(["high_pressure", "low_pressure", "storm"])
            }
            patterns.append(pattern)
        return patterns
    
    def _update_weather_patterns(self, hours: float = 6.0) -> None:
        """Update weather patterns based on time elapsed."""
        for pattern in self.weather_patterns:
            # Move the pattern
            center_lat = pattern["center"][0] + pattern["movement"][0] * hours
            center_lon = pattern["center"][1] + pattern["movement"][1] * hours
            
            # Wrap around if outside boundaries
            center_lat = (center_lat - self.MED_LAT_MIN) % (self.MED_LAT_MAX - self.MED_LAT_MIN) + self.MED_LAT_MIN
            center_lon = (center_lon - self.MED_LON_MIN) % (self.MED_LON_MAX - self.MED_LON_MIN) + self.MED_LON_MIN
            
            pattern["center"] = (center_lat, center_lon)
            
            # Evolve intensity and radius
            pattern["intensity"] += random.uniform(-0.1, 0.1)
            pattern["intensity"] = max(0.1, min(1.0, pattern["intensity"]))
            
            pattern["radius"] += random.uniform(-0.2, 0.2)
            pattern["radius"] = max(0.5, min(4.0, pattern["radius"]))
            
            # Small chance to change type
            if random.random() < 0.05:
                pattern["type"] = random.choice(["high_pressure", "low_pressure", "storm"])
    
    def _calculate_weather_at_point(self, lat: float, lon: float) -> Dict:
        """Calculate weather conditions at a specific point based on patterns."""
        # Base conditions
        wind_speed = 5.0  # knots
        wind_direction = random.uniform(0, 360)
        wave_height = 0.5  # meters
        current_speed = 0.5  # knots
        current_direction = random.uniform(0, 360)
        
        # Apply influence from each weather pattern
        for pattern in self.weather_patterns:
            # Calculate distance to pattern center
            distance = np.sqrt((lat - pattern["center"][0])**2 + (lon - pattern["center"][1])**2)
            
            # If within pattern radius, apply influence
            if distance < pattern["radius"]:
                influence = pattern["intensity"] * (1 - distance / pattern["radius"])
                
                if pattern["type"] == "high_pressure":
                    # High pressure: lower wind, lower waves
                    wind_speed -= 5.0 * influence
                    wave_height -= 0.5 * influence
                elif pattern["type"] == "low_pressure":
                    # Low pressure: higher wind, higher waves
                    wind_speed += 10.0 * influence
                    wave_height += 1.0 * influence
                    current_speed += 1.0 * influence
                elif pattern["type"] == "storm":
                    # Storm: much higher wind, much higher waves
                    wind_speed += 25.0 * influence
                    wave_height += 3.0 * influence
                    current_speed += 2.0 * influence
                
                # Wind direction influenced by pattern
                # Clockwise for high pressure, counterclockwise for low
                if pattern["type"] == "high_pressure":
                    angle = np.degrees(np.arctan2(lat - pattern["center"][0], lon - pattern["center"][1]))
                    wind_direction = (angle + 90) % 360  # 90° rotation for clockwise
                else:
                    angle = np.degrees(np.arctan2(lat - pattern["center"][0], lon - pattern["center"][1]))
                    wind_direction = (angle - 90) % 360  # -90° rotation for counterclockwise
        
        # Ensure values are in valid ranges
        wind_speed = max(0, wind_speed)
        wave_height = max(0, wave_height)
        current_speed = max(0, current_speed)
        
        return {
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "wave_height": wave_height,
            "current_speed": current_speed,
            "current_direction": current_direction
        }
    
    def generate_weather_data(self, hours_elapsed: float = 6.0) -> List[Dict]:
        """Generate weather forecast data for the grid."""
        self.current_time += int(hours_elapsed * 3600)
        self._update_weather_patterns(hours_elapsed)
        
        weather_data = []
        for lat, lon in self.grid_points:
            # Generate current weather
            current_weather = self._calculate_weather_at_point(lat, lon)
            
            # Generate forecast for the next 24 hours (4-hour intervals)
            forecast = []
            forecast_time = self.current_time
            
            for i in range(6):  # 24 hours in 4-hour intervals
                forecast_time += 4 * 3600
                
                # Add some variation to forecasted values
                forecast_entry = {
                    "time": forecast_time,
                    "wind_speed": current_weather["wind_speed"] + random.uniform(-2, 2),
                    "wind_direction": (current_weather["wind_direction"] + random.uniform(-20, 20)) % 360,
                    "wave_height": max(0, current_weather["wave_height"] + random.uniform(-0.3, 0.3)),
                    "current_speed": max(0, current_weather["current_speed"] + random.uniform(-0.2, 0.2)),
                    "current_direction": (current_weather["current_direction"] + random.uniform(-30, 30)) % 360
                }
                forecast.append(forecast_entry)
            
            weather_record = {
                "timestamp": self.current_time,
                "location": {
                    "latitude": lat,
                    "longitude": lon
                },
                "forecast": forecast
            }
            weather_data.append(weather_record)
            
        return weather_data


class HazardGenerator:
    """Generates synthetic environmental hazards for maritime navigation."""
    
    # Mediterranean coordinates
    MED_LAT_MIN, MED_LAT_MAX = 35.0, 45.0
    MED_LON_MIN, MED_LON_MAX = 5.0, 30.0
    
    # Hazard types
    HAZARD_TYPES = [
        # type, max severity, max radius, description template
        ("rocks", 5, 1.0, "Submerged rocks at {:.2f}°N, {:.2f}°E"),
        ("shallow", 3, 2.0, "Shallow waters around {:.2f}°N, {:.2f}°E"),
        ("debris", 2, 0.5, "Floating debris at {:.2f}°N, {:.2f}°E"),
        ("restricted", 4, 3.0, "Restricted zone at {:.2f}°N, {:.2f}°E"),
        ("traffic", 3, 2.0, "High traffic area at {:.2f}°N, {:.2f}°E")
    ]
    
    def __init__(self, seed: Optional[int] = None, num_static_hazards: int = 20):
        """Initialize the hazard generator."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        self.current_time = int(time.time())
        self.static_hazards = self._generate_static_hazards(num_static_hazards)
        self.dynamic_hazards = []
    
    def _generate_static_hazards(self, count: int) -> List[Dict]:
        """Generate static hazards like rocks and shallow waters."""
        hazards = []
        for _ in range(count):
            hazard_type = random.choice(self.HAZARD_TYPES)
            
            lat = random.uniform(self.MED_LAT_MIN, self.MED_LAT_MAX)
            lon = random.uniform(self.MED_LON_MIN, self.MED_LON_MAX)
            
            hazard = {
                "type": hazard_type[0],
                "severity": random.randint(1, hazard_type[1]),
                "radius": random.uniform(0.1, hazard_type[2]),
                "description": hazard_type[3].format(lat, lon),
                "location": (lat, lon),
                "is_static": True
            }
            hazards.append(hazard)
            
        return hazards
    
    def _update_dynamic_hazards(self, hours_elapsed: float) -> None:
        """Update dynamic hazards - remove expired ones, add new ones."""
        current_timestamp = self.current_time
        
        # Remove expired hazards
        self.dynamic_hazards = [h for h in self.dynamic_hazards if h["expiry"] > current_timestamp]
        
        # Chance to add new dynamic hazards
        if random.random() < 0.3:  # 30% chance per update
            lat = random.uniform(self.MED_LAT_MIN, self.MED_LAT_MAX)
            lon = random.uniform(self.MED_LON_MIN, self.MED_LON_MAX)
            
            hazard_type = random.choice(["debris", "traffic"])
            max_severity = next((h[1] for h in self.HAZARD_TYPES if h[0] == hazard_type), 3)
            max_radius = next((h[2] for h in self.HAZARD_TYPES if h[0] == hazard_type), 1.0)
            description_template = next((h[3] for h in self.HAZARD_TYPES if h[0] == hazard_type), 
                                       "Hazard at {:.2f}°N, {:.2f}°E")
            
            # Dynamic hazards expire after 1-3 days
            expiry = current_timestamp + random.randint(24, 72) * 3600
            
            hazard = {
                "type": hazard_type,
                "severity": random.randint(1, max_severity),
                "radius": random.uniform(0.1, max_radius),
                "description": description_template.format(lat, lon),
                "location": (lat, lon),
                "is_static": False,
                "expiry": expiry
            }
            self.dynamic_hazards.append(hazard)
    
    def generate_environmental_data(self, hours_elapsed: float = 6.0) -> Dict:
        """Generate environmental hazard data."""
        self.current_time += int(hours_elapsed * 3600)
        self._update_dynamic_hazards(hours_elapsed)
        
        # Combine static and dynamic hazards
        all_hazards = self.static_hazards + self.dynamic_hazards
        
        # Create grid-based data (less dense than weather)
        grid_data = []
        for lat in np.arange(self.MED_LAT_MIN, self.MED_LAT_MAX, 2.0):
            for lon in np.arange(self.MED_LON_MIN, self.MED_LON_MAX, 2.0):
                
                # Find hazards that affect this grid point
                local_hazards = []
                for hazard in all_hazards:
                    h_lat, h_lon = hazard["location"]
                    distance = np.sqrt((lat - h_lat)**2 + (lon - h_lon)**2)
                    
                    if distance < hazard["radius"]:
                        # Copy hazard with format compatible with schema
                        local_hazard = {
                            "type": hazard["type"],
                            "severity": hazard["severity"],
                            "radius": hazard["radius"],
                            "description": hazard["description"]
                        }
                        local_hazards.append(local_hazard)
                
                if local_hazards:  # Only add grid points with hazards
                    record = {
                        "timestamp": self.current_time,
                        "location": {
                            "latitude": lat,
                            "longitude": lon
                        },
                        "hazards": local_hazards
                    }
                    grid_data.append(record)
        
        return grid_data 