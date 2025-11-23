#!/bin/bash
set -e

echo " Starting SECURE build process for School Management System"
echo "=============================================="

# بررسی وجود متغیرهای امنیتی حیاتی
echo " Checking critical security variables..."

REQUIRED_VARS=(
    "SECRET_KEY"
    "SUPER_ADMIN_USERNAME"
    "SUPER_ADMIN_PASSWORD"
    "DATABASE_URL"
    "PORT"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo " ERROR: Critical security variable $var is not set"
        echo " Please set this variable in Render.com dashboard"
        exit 1
    fi
    echo "    $var is configured"
done

# بررسی قدرت رمز عبور Super Admin
echo "  Validating Super Admin password strength..."
SUPER_ADMIN_PASSWORD_LENGTH=${#SUPER_ADMIN_PASSWORD}
if [ "$SUPER_ADMIN_PASSWORD_LENGTH" -lt 12 ]; then
    echo " ERROR: SUPER_ADMIN_PASSWORD must be at least 12 characters long"
    echo " Current length: $SUPER_ADMIN_PASSWORD_LENGTH"
    exit 1
fi
echo "    Super Admin password meets security requirements (length: $SUPER_ADMIN_PASSWORD_LENGTH)"

# نصب وابستگی‌ها
echo " Installing Python dependencies securely..."
pip install --no-cache-dir -r requirements.txt
echo " Dependencies installed securely"

# ایجاد دایرکتوری‌های ضروری
echo " Creating necessary directories with secure permissions..."
mkdir -p /opt/render/project/src/{app/static/css,app/static/js,app/static/images,sessions,logs,uploads/{avatars,documents},databases}
chmod 755 /opt/render/project/src
chmod 750 /opt/render/project/src/{sessions,logs,uploads,databases}
chmod 755 /opt/render/project/src/app/static
chmod 755 /opt/render/project/src/app/static/{css,js,images}
echo " Directories created with secure permissions"

# ایجاد فایل‌های استاتیک
echo " Creating static files..."
cat > /opt/render/project/src/app/static/css/main.css << 'EOF'
/* CSS مینیمال و کاربردی */
body { font-family: 'Vazirmatn', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; }
EOF

echo "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAFVBMVEX///8AAAD///8AAAD///8AAAD///9t52NFAAAAB3RSTlMAERAZmZn7VQO2PAAAAHhJREFUGNNjYGBgZGJmYWFhZWVj5+Dk4uHlFxQSFhYRlVJQUlZRVVPX0NTS1tHTNzA0MjYxtbK2sbWzd3B0cnZxdXP38PTy9vH18w8IDAoOCQ0Lj4iMio5hYIwBADuZJgFzJg7/AAAAAElFTkSuQmCC" | base64 -d > /opt/render/project/src/app/static/favicon.ico
echo " Static files created"

# مهاجرت دیتابیس
echo " Running database migrations securely..."
flask db upgrade
echo " Database migrations completed successfully"

# بررسی ایجاد Super Admin
echo " Verifying Super Admin account creation..."
python -c "
from app import create_app
from app.models import db, User
from config import Config
import os

app = create_app()
with app.app_context():
    super_admin = User.query.filter_by(username=Config.SUPER_ADMIN_USERNAME).first()
    if super_admin:
        print(' Super Admin account verified successfully')
        print(f' Username: {super_admin.username}')
        print(f' Created at: {super_admin.created_at}')
    else:
        print(' ERROR: Super Admin account was not created')
        exit(1)
"

echo "=============================================="
echo " SECURE BUILD COMPLETED SUCCESSFULLY"
echo " System is ready for production deployment"
echo " Remember to disable development features in production"
