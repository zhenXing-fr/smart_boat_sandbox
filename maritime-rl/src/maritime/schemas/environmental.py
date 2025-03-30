"""Schema for environmental hazard data."""

ENVIRONMENTAL_SCHEMA = {
    "type": "record",
    "name": "EnvironmentalData",
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
        {"name": "hazards", "type": {
            "type": "array",
            "items": {
                "type": "record",
                "name": "Hazard",
                "fields": [
                    {"name": "type", "type": "string"},
                    {"name": "severity", "type": "int"},
                    {"name": "radius", "type": "double"},
                    {"name": "description", "type": "string"}
                ]
            }
        }}
    ]
} 