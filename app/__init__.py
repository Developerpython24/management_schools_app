from flask import Flask, current_app
from flask_login import LoginManager, user_loader  #  اضافه شده
from config import Config
from app.extensions import db, migrate, mail, csrf
from app.models import User  #  اضافه شده
import logging

login_manager = LoginManager()  # خارج از create_app

def create_app(config_class=Config):
    """Factory function to create Flask application"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)  #  اینجا init می‌شود
    mail.init_app(app)
    csrf.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "لطفاً برای دسترسی به این صفحه وارد شوید."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"
    
    # Set up logging
    setup_logging(app)
    
    # Setup security headers
    setup_security(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Initialize database
    with app.app_context():
        init_database(app)
    
    # Register shell context
    register_shell_context(app)
    
    #  اینجا user_loader را تعریف می‌کنیم
    @login_manager.user_loader
    def load_user(user_id):
        """Load user from database for Flask-Login"""
        try:
            return User.query.get(int(user_id))
        except:
            app.logger.error(f"Error loading user with ID: {user_id}")
            return None
    
    return app

def setup_logging(app):
    """Configure application logging"""
    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )
    
    app.logger.info("Logging system initialized")

def setup_security(app):
    """Configure security headers and settings"""
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self'  https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net"
        return response

def register_blueprints(app):
    """Register application blueprints"""
    # Auth blueprint
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    # Super Admin blueprint
    from app.routes.super_admin import bp as super_admin_bp
    app.register_blueprint(super_admin_bp, url_prefix='/super_admin')
    
    # School Admin blueprint
    from app.routes.school_admin import bp as school_admin_bp
    app.register_blueprint(school_admin_bp, url_prefix='/school_admin')
    
    # Teacher blueprint
    from app.routes.teacher import bp as teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    
    # API blueprint
    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    app.logger.info("Blueprints registered successfully")

def register_shell_context(app):
    """Register shell context for Flask CLI"""
    @app.shell_context_processor
    def make_shell_context():
        return {
            'app': app,
            'db': db,
            # Import models here if needed
            # 'User': User,
            # 'School': School,
        }
