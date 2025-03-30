"""Schema for vessel sailing data."""

SAILING_SCHEMA = {
    "type": "record",
    "name": "SailingRecord",
    "namespace": "com.maritime.data",
    "fields": [
        {"name": "vessel_id", "type": "string"},
        {"name": "timestamp", "type": "long"},
        {"name": "position", "type": {
            "type": "record",
            "name": "Position",
            "fields": [
                {"name": "latitude", "type": "double"},
                {"name": "longitude", "type": "double"}
            ]
        }},
        {"name": "speed", "type": "double"},
        {"name": "heading", "type": "double"},
        {"name": "fuel_consumption", "type": "double"},
        {"name": "weather_conditions", "type": {
            "type": "record",
            "name": "Weather",
            "fields": [
                {"name": "wind_speed", "type": "double"},
                {"name": "wave_height", "type": "double"},
                {"name": "current_speed", "type": "double"}
            ]
        }}
    ]
} 