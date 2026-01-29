#!/bin/bash
# Initialize Apache AGE as a shared preload library
# This script configures PostgreSQL to load AGE on startup

set -e

# Add AGE to shared_preload_libraries in postgresql.conf
echo "Configuring AGE as shared preload library..."

# Update postgresql.conf to include 'age' in shared_preload_libraries
if ! grep -q "shared_preload_libraries.*age" "$PGDATA/postgresql.conf"; then
    echo "shared_preload_libraries = 'age'" >> "$PGDATA/postgresql.conf"
    echo "AGE added to shared_preload_libraries"
else
    echo "AGE already in shared_preload_libraries"
fi

# Set search path to include ag_catalog
echo "search_path = 'ag_catalog, \"\$user\", public'" >> "$PGDATA/postgresql.conf"

echo "AGE configuration complete!"
