import os

class Config:
    # برای Render.com حتماً از environment variables بخوانید
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # مسیر دیتابیس در Render (فقط این پوشه قابل نوشتن است)
    DATABASE_DIR = os.environ.get('DATABASE_DIR') or '/opt/render/project/src/databases'
    
    # Super Admin از environment بخواند
    SUPER_ADMIN_USERNAME = os.environ.get('SUPER_ADMIN_USERNAME') or 'superadmin'
    SUPER_ADMIN_PASSWORD = os.environ.get('SUPER_ADMIN_PASSWORD') or 'superadmin123'
    
    # SMS API
    SMS_API_KEY = os.environ.get('SMS_API_KEY') or ''
    SMS_ACTIVE = os.environ.get('SMS_ACTIVE', 'False').lower() == 'true'
    
    SCHOOL_TYPES = {
        'elementary': 'ابتدایی',
        'middle': 'متوسطه اول',
        'high': 'متوسطه دوم'
    }