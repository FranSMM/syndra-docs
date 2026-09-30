#!/bin/bash
set -e

# This script is executed automatically by the Postgres image just once when the volume is created.

echo "Creating secondary database for Prefect (prefect_db)..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE prefect_db;
    GRANT ALL PRIVILEGES ON DATABASE prefect_db TO $POSTGRES_USER;
EOSQL

echo "Prefect database created successfully."
