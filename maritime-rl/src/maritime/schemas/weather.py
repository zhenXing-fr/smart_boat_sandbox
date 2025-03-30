"""Schema for weather forecast data."""

WEATHER_SCHEMA = {
    "type": "record",
    "name": "WeatherData",
    "namespace": "com.maritime.data",
    "fields": [
        {"name": "timestamp", "type": "long"},
        {"name": "location", "type": {
            "type": "record",
            "name": "Location",
            "fields": [
                {"name": "latitude", "type": "double"},
                {"name": "longitude", "type": "double"}
            ]
        }},
        {"name": "forecast", "type": {
            "type": "array",
            "items": {
                "type": "record",
                "name": "ForecastPoint",
                "fields": [
                    {"name": "time", "type": "long"},
                    {"name": "wind_speed", "type": "double"},
                    {"name": "wind_direction", "type": "double"},
                    {"name": "wave_height", "type": "double"},
                    {"name": "current_speed", "type": "double"},
                    {"name": "current_direction", "type": "double"}
                ]
            }
        }}
    ]
} 