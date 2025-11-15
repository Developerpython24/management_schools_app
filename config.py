import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables
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
    
    # Database configuration
    DATABASE_DIR = os.environ.get('DATABASE_DIR') or '/opt/render/project/src/databases'
    os.makedirs(DATABASE_DIR, exist_ok=True)
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("DATABASE_URL is required in production!")
        # Local development database
        db_path = os.path.join(DATABASE_DIR, 'school_management.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 3600
    
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
    UPLOAD_FOLDER = os.path.join(DATABASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}
    
    # Rate limiting configuration
    LOGIN_RATE_LIMIT = 5
    LOGIN_LOCKOUT_TIME = 300  # 5 minutes
    
    # School types
    SCHOOL_TYPES = {
        'elementary': 'ابتدایی',
        'middle': 'متوسطه اول',
        'high': 'متوسطه دوم',
        'combined': 'یکپارچه'
    }
    
    @classmethod
    def init_app(cls, app):
        """Initialize app with configuration"""
        # Create necessary directories
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        
        # Setup logging in debug mode
        if app.debug:
            app.logger.debug(f"Database URI: {cls.SQLALCHEMY_DATABASE_URI}")
            app.logger.debug(f"SMS Active: {cls.SMS_ACTIVE}")
            app.logger.debug(f"Environment: {cls.FLASK_ENV}")
