from functools import wraps
from flask import redirect, url_for, flash, abort, session
from flask_login import current_user, login_required
import time

# Rate limiting storage
login_attempts = {}
LOCKOUT_TIME = 300  # 5 minutes
MAX_ATTEMPTS = 5

def is_account_locked(username):
    """Check if account is locked due to multiple failed attempts"""
    if username in login_attempts:
        attempts, last_attempt = login_attempts[username]
        if attempts >= MAX_ATTEMPTS:
            if time.time() - last_attempt < LOCKOUT_TIME:
                return True
            else:
                # Unlock account after lockout time
                del login_attempts[username]
    return False

def record_failed_attempt(username):
    """Record a failed login attempt"""
    current_time = time.time()
    if username in login_attempts:
        attempts, _ = login_attempts[username]
        login_attempts[username] = (attempts + 1, current_time)
    else:
        login_attempts[username] = (1, current_time)

def clear_failed_attempts(username):
    """Clear failed attempts after successful login"""
    if username in login_attempts:
        del login_attempts[username]

def role_required(*roles):
    """Decorator to restrict access based on user roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('لطفاً ابتدا وارد سیستم شوید', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in roles:
                flash('شما دسترسی لازم برای این صفحه را ندارید', 'danger')
                app.logger.warning(f"Unauthorized access attempt by {current_user.username} to {request.path}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def super_admin_required(f):
    """Decorator for Super Admin access only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            flash('فقط Super Admin می‌تواند به این صفحه دسترسی داشته باشد', 'danger')
            app.logger.warning(f"Super admin access attempt by {current_user.username}")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def school_admin_required(f):
    """Decorator for School Admin and Super Admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('لطفاً ابتدا وارد سیستم شوید', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role not in ['school_admin', 'super_admin']:
            flash('فقط مدیران مدرسه می‌توانند به این صفحه دسترسی داشته باشند', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """Decorator for Teacher access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('لطفاً ابتدا وارد سیستم شوید', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role not in ['teacher', 'school_admin', 'super_admin']:
            flash('فقط معلمان و مدیران می‌توانند به این صفحه دسترسی داشته باشند', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function
