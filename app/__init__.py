from flask import Flask, current_app, url_for, session
from config import Config
from app.extensions import db, migrate, login_manager, mail, csrf
from app.models import init_database, User
import logging
import os
from datetime import datetime
import jdatetime

def register_template_filters(app):
    """Register custom template filters"""
    @app.template_filter('format_datetime')
    def format_datetime_filter(dt):
        """Format a datetime object for display in templates"""
        if not dt:
            return ''
        return dt.strftime('%Y/%m/%d %H:%M:%S')
    
    @app.template_filter('format_date')
    def format_date_filter(dt):
        """Format a date object for display in templates"""
        if not dt:
            return ''
        return dt.strftime('%Y/%m/%d')
    
    @app.template_filter('format_persian_date')
    def format_persian_date_filter(dt):
        """Format a date object as Persian date"""
        if not dt:
            return ''
        return jdatetime.date.fromgregorian(date=dt).strftime('%Y/%m/%d')

def register_context_processors(app):
    """Register custom context processors for templates"""
    @app.context_processor
    def utility_processor():
        """Custom template context containing useful functions and variables"""
        return dict(
            now=datetime.now,
            current_year=datetime.now().year,
            static_url=lambda filename: url_for('static', filename=filename, _external=True),
            datetime=datetime,
            session=session
        )

def create_app(config_class=Config):
    """Factory function to create Flask application"""
    app = Flask(__name__, 
                static_folder='static',
                static_url_path='/static')
    
    app.config.from_object(config_class)
    
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['STATIC_FOLDER'] = '/opt/render/project/src/app/static'
        app.config['SESSION_FILE_DIR'] = '/opt/render/project/src/sessions'
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "لطفاً برای دسترسی به این صفحه وارد شوید."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"
    
    # Register template filters
    register_template_filters(app)
    
    # Register context processors
    register_context_processors(app)
    
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
    
    return app

def setup_logging(app):
    """Configure application logging"""
    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]',
        handlers=[
            logging.FileHandler("/opt/render/project/src/app.log" if os.environ.get('FLASK_ENV') == 'production' else "app.log"),
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
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net"
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

@login_manager.user_loader
def load_user(user_id):
    """Load user from database for Flask-Login"""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        current_app.logger.error(f"Error loading user with ID {user_id}: {str(e)}")
        return None
