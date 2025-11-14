from flask import Flask
from app.models import init_main_db, create_super_admin
from app.routes import auth, super_admin, school_admin, teacher

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    # Initialize database
    init_main_db()
    create_super_admin()
    
    # Register blueprints
    app.register_blueprint(auth.bp)
    app.register_blueprint(super_admin.bp, url_prefix='/super_admin')
    app.register_blueprint(school_admin.bp, url_prefix='/school_admin')
    app.register_blueprint(teacher.bp, url_prefix='/teacher')
    
    return app
