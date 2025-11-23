import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables only in development
if os.environ.get('FLASK_ENV') != 'production':
    load_dotenv()

class Config:
    # Basic configuration
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("SECRET_KEY is required in production environment!")
        SECRET_KEY = 'dev-secret-key-change-in-production'
    
    # Session configuration
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_NAME = '__session'
    
    # Session file directory - تنظیمات ویژه برای Render.com
    SESSION_FILE_DIR = os.environ.get('SESSION_FILE_DIR', '/opt/render/project/src/sessions')
    
    # Database configuration
    DATABASE_DIR = os.environ.get('DATABASE_DIR') or '/opt/render/project/src/databases'
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/opt/render/project/src/uploads'
    
    # مسیر دیتابیس در render.com
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("DATABASE_URL is required in production!")
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
    
    # Super Admin configuration
    SUPER_ADMIN_USERNAME = os.environ.get('SUPER_ADMIN_USERNAME', 'superadmin')
    SUPER_ADMIN_PASSWORD = os.environ.get('SUPER_ADMIN_PASSWORD', 'superadmin123')
    
    # SMS configuration
    SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
    SMS_ACTIVE = os.environ.get('SMS_ACTIVE', 'False').lower() == 'true'
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'kavenegar')
    SMS_SENDER = os.environ.get('SMS_SENDER', '10008663')
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@school.com')
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    @classmethod
    def init_app(cls, app):
        """Initialize app with configuration"""
        # ایجاد پوشه session - فقط در صورتی که قابل نوشتن باشد
        if cls.FLASK_ENV == 'production':
            # برای Render.com، فقط اگر دایرکتوری وجود داشته باشد یا قابل ایجاد باشد
            if os.access(os.path.dirname(cls.SESSION_FILE_DIR), os.W_OK):
                os.makedirs(cls.SESSION_FILE_DIR, exist_ok=True)
        else:
            os.makedirs(cls.SESSION_FILE_DIR, exist_ok=True)
        
        # ایجاد دایرکتوری‌های لازم - فقط در حالت توسعه
        if cls.FLASK_ENV != 'production':
            os.makedirs(cls.DATABASE_DIR, exist_ok=True)
            os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
            os.makedirs(os.path.join(cls.UPLOAD_FOLDER, 'avatars'), exist_ok=True)
            os.makedirs(os.path.join(cls.UPLOAD_FOLDER, 'documents'), exist_ok=True)
        
        # لاگ تنظیمات
        if app.debug:
            app.logger.debug(f"Database URI: {cls.SQLALCHEMY_DATABASE_URI}")
            app.logger.debug(f"SMS Active: {cls.SMS_ACTIVE}")
            app.logger.debug(f"Environment: {cls.FLASK_ENV}")
            app.logger.debug(f"Session File Dir: {cls.SESSION_FILE_DIR}")
            app.logger.debug(f"Upload Folder: {cls.UPLOAD_FOLDER}")
