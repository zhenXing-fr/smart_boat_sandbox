#!/bin/bash

# Color variables
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function log_status {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warning {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function log_error {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if pgAdmin is running
if ! docker ps | grep -q pgadmin; then
    log_error "pgAdmin is not running. Please start it first using start_services_sequential.sh"
    exit 1
fi

# Create temporary SQL file
cat > /tmp/setup_connections.sql << EOF
-- Create server group
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pgadmin_server_group WHERE name = 'Maritime Project') THEN
        INSERT INTO pgadmin_server_group (name, uid, user_id)
        SELECT 'Maritime Project', gen_random_uuid(), id FROM pgadmin_user WHERE username = 'admin@maritime.com' LIMIT 1;
    END IF;
END \$\$;

-- Get the server group id
WITH group_id AS (
    SELECT id FROM pgadmin_server_group WHERE name = 'Maritime Project'
)
-- Create TimescaleDB server connection if it doesn't exist
INSERT INTO pgadmin_server (name, servergroup_id, json_data, user_id)
SELECT 
    'TimescaleDB', 
    group_id.id, 
    '{"host": "timescaledb", "port": 5432, "db": "maritime", "username": "maritime", "password": "password", "ssl_mode": "prefer", "maintenance_db": "maritime"}', 
    pgadmin_user.id
FROM 
    group_id, 
    pgadmin_user 
WHERE 
    pgadmin_user.username = 'admin@maritime.com'
    AND NOT EXISTS (
        SELECT 1 FROM pgadmin_server 
        WHERE name = 'TimescaleDB' 
        AND user_id = pgadmin_user.id
    );

-- Create Airflow Postgres server connection if it doesn't exist
WITH group_id AS (
    SELECT id FROM pgadmin_server_group WHERE name = 'Maritime Project'
)
INSERT INTO pgadmin_server (name, servergroup_id, json_data, user_id)
SELECT 
    'Airflow Postgres', 
    group_id.id, 
    '{"host": "airflow-postgres", "port": 5432, "db": "airflow", "username": "airflow", "password": "airflow", "ssl_mode": "prefer", "maintenance_db": "airflow"}', 
    pgadmin_user.id
FROM 
    group_id, 
    pgadmin_user 
WHERE 
    pgadmin_user.username = 'admin@maritime.com'
    AND NOT EXISTS (
        SELECT 1 FROM pgadmin_server 
        WHERE name = 'Airflow Postgres' 
        AND user_id = pgadmin_user.id
    );
EOF

log_status "Setting up pgAdmin connections..."

# Create servers in pgAdmin
docker exec -i pgadmin psql -U pgadmin -d pgadmin4 < /tmp/setup_connections.sql

# Remove temporary file
rm /tmp/setup_connections.sql

log_status "pgAdmin connections have been set up."
log_status "You can now access TimescaleDB and Airflow Postgres in pgAdmin at http://localhost:5050"
log_status "Login with email: admin@maritime.com and password: maritime_admin" 