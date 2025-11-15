import os
from dotenv import load_dotenv
from datetime import timedelta

# بارگذاری متغیرهای محیطی فقط در حالت توسعه
if os.environ.get('FLASK_ENV') != 'production':
    load_dotenv()

class Config:
    # تنظیمات پایه
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    
    # امنیت - کلید را حتماً در production تنظیم کنید
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("❌ SECRET_KEY is required in production environment!")
        SECRET_KEY = 'dev-secret-key-change-in-production'
    
    # تنظیمات session
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # مسیرهای دیتابیس و آپلود
    DATABASE_DIR = os.environ.get('DATABASE_DIR') or '/opt/render/project/src/databases'
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/opt/render/project/src/uploads'
    
    # دیتابیس
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("❌ DATABASE_URL is required in production!")
        # دیتابیس توسعه
        db_path = os.path.join(DATABASE_DIR, 'school_management.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    
    # برای PostgreSQL در production
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_size': 10,
        'max_overflow': 20,
    }
    
    # 🔐 Super Admin Settings - فقط از environment variables خوانده شود
    SUPER_ADMIN_USERNAME = os.environ.get('SUPER_ADMIN_USERNAME')
    SUPER_ADMIN_PASSWORD = os.environ.get('SUPER_ADMIN_PASSWORD')
    
    # بررسی امنیتی برای production
    if os.environ.get('FLASK_ENV') == 'production':
        if not SUPER_ADMIN_USERNAME or not SUPER_ADMIN_PASSWORD:
            raise ValueError("❌ SUPER_ADMIN_USERNAME and SUPER_ADMIN_PASSWORD are required in production!")
        if len(SUPER_ADMIN_PASSWORD) < 12:
            raise ValueError("❌ SUPER_ADMIN_PASSWORD must be at least 12 characters long for production!")
    
    # تنظیمات SMS
    SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
    SMS_ACTIVE = os.environ.get('SMS_ACTIVE', 'False').lower() == 'true'
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'kavenegar')
    SMS_SENDER = os.environ.get('SMS_SENDER', '10008663')
    
    # تنظیمات ایمیل
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@school.com')
    
    # محدودیت‌های فایل
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}
    
    # محدودیت نرخ
    LOGIN_RATE_LIMIT = 5
    LOGIN_LOCKOUT_TIME = 300  # 5 minutes
    
    # انواع مدرسه
    SCHOOL_TYPES = {
        'elementary': 'ابتدایی',
        'middle': 'متوسطه اول',
        'high': 'متوسطه دوم',
        'combined': 'یکپارچه'
    }
    
    @classmethod
    def init_app(cls, app):
        """اینیشیال‌سازی اپلیکیشن با تنظیمات امنیتی"""
        # ایجاد دایرکتوری‌ها
        os.makedirs(cls.DATABASE_DIR, exist_ok=True)
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        
        # بررسی امنیتی برای Super Admin
        if app.debug:
            app.logger.debug("✅ Security check passed - Development mode")
            if not cls.SUPER_ADMIN_USERNAME or not cls.SUPER_ADMIN_PASSWORD:
                app.logger.warning("⚠️  Super Admin credentials not set - using defaults for development")
        
        # لاگ تنظیمات امنیتی (بدون نمایش کلیدها)
        app.logger.info("🔒 Security configuration loaded")
        app.logger.info(f"Environment: {cls.FLASK_ENV}")
        app.logger.info(f"Super Admin Username configured: {'Yes' if cls.SUPER_ADMIN_USERNAME else 'No'}")
        app.logger.info(f"Database connection: {'Configured' if cls.SQLALCHEMY_DATABASE_URI else 'Not configured'}")
