-- Install required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create a hypertable for storing vessel telemetry data
CREATE TABLE IF NOT EXISTS vessel_telemetry (
    id SERIAL PRIMARY KEY,
    vessel_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    position GEOGRAPHY(POINT) NOT NULL,
    speed FLOAT NOT NULL,
    heading FLOAT NOT NULL,
    fuel_consumption FLOAT NOT NULL,
    weather_conditions JSONB,
    route_segment VARCHAR(100),
    quality_score FLOAT,
    data_source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('vessel_telemetry', 'timestamp', if_not_exists => TRUE);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_vessel_telemetry_vessel_id ON vessel_telemetry (vessel_id);
CREATE INDEX IF NOT EXISTS idx_vessel_telemetry_route_segment ON vessel_telemetry (route_segment);
CREATE INDEX IF NOT EXISTS idx_vessel_telemetry_quality_score ON vessel_telemetry (quality_score);

-- Create a table for storing quality metrics
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    topic VARCHAR(100) NOT NULL,
    total_records INT NOT NULL,
    valid_records INT NOT NULL,
    invalid_records INT NOT NULL,
    min_quality_score FLOAT,
    avg_quality_score FLOAT,
    max_quality_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('data_quality_metrics', 'timestamp', if_not_exists => TRUE);

-- Create a view for vessel performance analytics
CREATE OR REPLACE VIEW vessel_performance AS
SELECT 
    time_bucket('1 hour', timestamp) AS hour,
    vessel_id,
    AVG(speed) AS avg_speed,
    AVG(fuel_consumption) AS avg_fuel,
    COUNT(*) AS data_points,
    AVG(quality_score) AS avg_quality
FROM 
    vessel_telemetry
WHERE 
    quality_score >= 0.7  -- Only consider high-quality data
GROUP BY 
    hour, vessel_id;

-- Create a materialized view for daily vessel statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_vessel_stats
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', timestamp) AS day,
    vessel_id,
    AVG(speed) AS avg_speed,
    MAX(speed) AS max_speed,
    AVG(fuel_consumption) AS avg_fuel,
    SUM(fuel_consumption) AS total_fuel,
    COUNT(*) AS data_points
FROM 
    vessel_telemetry
GROUP BY 
    day, vessel_id
WITH NO DATA;

-- Refresh policy for the materialized view
SELECT add_continuous_aggregate_policy('daily_vessel_stats',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day');

-- Create a table for ML model predictions
CREATE TABLE IF NOT EXISTS route_predictions (
    id SERIAL PRIMARY KEY,
    vessel_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    current_position GEOGRAPHY(POINT) NOT NULL,
    predicted_route GEOGRAPHY(LINESTRING) NOT NULL,
    confidence_score FLOAT NOT NULL,
    fuel_savings_estimate FLOAT,
    time_savings_estimate INTERVAL,
    model_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('route_predictions', 'timestamp', if_not_exists => TRUE);

-- Create index on vessel_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_route_predictions_vessel_id ON route_predictions (vessel_id);

-- Grant privileges to maritime user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO maritime;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO maritime; 