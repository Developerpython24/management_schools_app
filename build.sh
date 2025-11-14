#!/bin/bash
# This script runs after build

echo "Creating database directory..."
mkdir -p databases

echo "Initializing databases..."
python -c "from app.models import init_main_db, create_super_admin; init_main_db(); create_super_admin();"

echo "Build completed successfully!"