#!/bin/bash
set -e

echo "🚀 Starting build process for School Management System"

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p /opt/render/project/src/databases
mkdir -p /opt/render/project/src/uploads
mkdir -p /opt/render/project/src/logs

# Set permissions
echo "🔒 Setting proper permissions..."
chmod -R 755 /opt/render/project/src

# Database migration
echo "🔄 Running database migrations..."
flask db upgrade

# Create super admin if not exists
echo "👑 Creating super admin user..."
python -c "
from app import create_app
from app.models import db, User
from config import Config
import os

app = create_app()
with app.app_context():
    super_admin = User.query.filter_by(username=Config.SUPER_ADMIN_USERNAME).first()
    if not super_admin:
        super_admin = User(
            username=Config.SUPER_ADMIN_USERNAME,
            name='Super Admin',
            role='super_admin',
            email='admin@school.com',
            is_active=True
        )
        super_admin.set_password(Config.SUPER_ADMIN_PASSWORD)
        db.session.add(super_admin)
        db.session.commit()
        print('✅ Super Admin created successfully')
    else:
        print('✅ Super Admin already exists')
"

echo "✅ Build completed successfully!"
