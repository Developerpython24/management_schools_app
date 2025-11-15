#!/bin/bash
set -euo pipefail

echo "🔒 Starting SECURE build process for School Management System"
echo "=============================================="

# بررسی وجود متغیرهای امنیتی حیاتی
echo "✅ Checking critical security variables..."

REQUIRED_VARS=(
    "SECRET_KEY"
    "SUPER_ADMIN_USERNAME"
    "SUPER_ADMIN_PASSWORD"
    "DATABASE_URL"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "❌ ERROR: Critical security variable $var is not set"
        echo "💡 Please set this variable in Render.com dashboard"
        exit 1
    fi
    echo "   ✅ $var is configured"
done

# بررسی قدرت رمز عبور Super Admin
echo "🛡️  Validating Super Admin password strength..."
SUPER_ADMIN_PASSWORD_LENGTH=${#SUPER_ADMIN_PASSWORD}
if [ "$SUPER_ADMIN_PASSWORD_LENGTH" -lt 12 ]; then
    echo "❌ ERROR: SUPER_ADMIN_PASSWORD must be at least 12 characters long"
    echo "💡 Current length: $SUPER_ADMIN_PASSWORD_LENGTH"
    exit 1
fi
echo "   ✅ Super Admin password meets security requirements (length: $SUPER_ADMIN_PASSWORD_LENGTH)"

# نصب وابستگی‌ها
echo "📦 Installing Python dependencies securely..."
pip install --no-cache-dir -r requirements.txt
echo "✅ Dependencies installed securely"

# ایجاد دایرکتوری‌های ضروری
echo "📁 Creating necessary directories with secure permissions..."
mkdir -p /opt/render/project/src/{databases,uploads,logs}
chmod 755 /opt/render/project/src
chmod 750 /opt/render/project/src/{databases,uploads,logs}
echo "✅ Directories created with secure permissions"

# مهاجرت دیتابیس
echo "🔄 Running database migrations securely..."
flask db upgrade
echo "✅ Database migrations completed successfully"

# بررسی ایجاد Super Admin
echo "👑 Verifying Super Admin account creation..."
python -c "
from app import create_app
from app.models import db, User
from config import Config
import os

app = create_app()
with app.app_context():
    super_admin = User.query.filter_by(username=Config.SUPER_ADMIN_USERNAME).first()
    if super_admin:
        print('✅ Super Admin account verified successfully')
        print(f'👤 Username: {super_admin.username}')
        print(f'📅 Created at: {super_admin.created_at}')
    else:
        print('❌ ERROR: Super Admin account was not created')
        exit(1)
"

echo "=============================================="
echo "✅ SECURE BUILD COMPLETED SUCCESSFULLY"
echo "🔒 System is ready for production deployment"
echo "💡 Remember to disable development features in production"
