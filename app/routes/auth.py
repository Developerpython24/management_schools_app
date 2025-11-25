from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask import session 
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session  
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash  
from app.models import db, User
from app.decorators import is_account_locked, record_failed_attempt, clear_failed_attempts
from app.utils.sms_service import sms_service
from app.utils.audit_log import log_audit_action
from flask_wtf import FlaskForm
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__)

class LoginForm(FlaskForm):
    username = StringField('نام کاربری', validators=[
        DataRequired(message='نام کاربری الزامی است'),
        Length(min=3, max=50, message='نام کاربری باید بین 3 تا 50 کاراکتر باشد')
    ])
    password = PasswordField('رمز عبور', validators=[
        DataRequired(message='رمز عبور الزامی است'),
        Length(min=6, message='رمز عبور باید حداقل 6 کاراکتر باشد')
    ])
    remember = BooleanField('مرا به خاطر بسپار')
    submit = SubmitField('ورود')

class PasswordResetRequestForm(FlaskForm):
    email = StringField('ایمیل', validators=[
        DataRequired(message='ایمیل الزامی است'),
        Email(message='ایمیل معتبر نیست')
    ])
    submit = SubmitField('درخواست بازیابی')

class PasswordResetForm(FlaskForm):
    new_password = PasswordField('رمز عبور جدید', validators=[
        DataRequired(message='رمز عبور جدید الزامی است'),
        Length(min=8, message='رمز عبور باید حداقل 8 کاراکتر باشد')
    ])
    confirm_password = PasswordField('تایید رمز عبور', validators=[
        DataRequired(message='تایید رمز عبور الزامی است'),
        EqualTo('new_password', message='رمز عبور‌ها مطابقت ندارند')
    ])
    submit = SubmitField('تغییر رمز عبور')

@bp.route('/')
def index():
    """Redirect to appropriate dashboard based on user role"""
    if current_user.is_authenticated:
        if current_user.is_super_admin:
            return redirect(url_for('super_admin.dashboard'))
        elif current_user.is_school_admin:
            return redirect(url_for('school_admin.dashboard'))
        elif current_user.is_teacher:
            return redirect(url_for('teacher.dashboard'))
    
    return redirect(url_for('auth.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        
        # Check if account is locked
        if is_account_locked(username):
            remaining_time = 300 - (time.time() - login_attempts[username][1])  # 5 minutes lockout
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            flash(f'حساب شما به دلیل تلاش‌های ناموفق متوالی قفل شده است. لطفاً پس از {minutes} دقیقه و {seconds} ثانیه دوباره تلاش کنید.', 'danger')
            logger.warning(f"Login attempt on locked account: {username}")
            return render_template('auth/login.html', form=form)
        
        user = None
        
        #  اصلاح Super Admin - استفاده از مقدار واقعی از Config
        from config import Config
        if username == Config.SUPER_ADMIN_USERNAME:
            # بررسی رمز عبور Super Admin
            if check_password_hash(generate_password_hash(Config.SUPER_ADMIN_PASSWORD), password):
                # ایجاد کاربر Super Admin
                user = User(
                    id=0,
                    username=Config.SUPER_ADMIN_USERNAME,
                    name='Super Admin',
                    role='super_admin',
                    is_active=True
                )
                user.set_id = lambda: str(0)  #  تنظیم موقت get_id برای Super Admin
                logger.info(f"Super Admin {username} logged in successfully")
        
        # Check regular users
        if not user:
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                logger.info(f"User {username} logged in successfully")
            else:
                user = None
        
        # Successful login
        if user:
            clear_failed_attempts(username)
            login_user(user, remember=form.remember.data, duration=timedelta(days=30))
            
            flash(f'خوشحالم که دوباره اینجا هستم، {user.name}!', 'success')
            session_id = session.get('_id', 'unknown')
            logger.info(f"User {username} logged in successfully. Session ID: {session_id}")
            
            # Log audit action
            log_audit_action(
                user_id=user.id,
                action='login',
                description=f'User {user.username} logged in successfully',
                school_id=user.school_id if hasattr(user, 'school_id') else None
            )
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                if user.is_super_admin:
                    next_page = url_for('super_admin.dashboard')
                elif user.is_school_admin:
                    next_page = url_for('school_admin.dashboard')
                elif user.is_teacher:
                    next_page = url_for('teacher.dashboard')
                else:
                    next_page = url_for('auth.index')
            
            logger.info(f"Redirecting to: {next_page}")
            return redirect(next_page)
        
        # Failed login
        record_failed_attempt(username)
        flash('نام کاربری یا رمز عبور اشتباه است', 'danger')
        logger.warning(f"Failed login attempt for username: {username}")
    
    return render_template('auth/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    username = current_user.username
    user_id = current_user.id
    
    logout_user()
    session.clear()
    
    flash('شما با موفقیت از سیستم خارج شدید', 'info')
    logger.info(f"User {username} logged out successfully")
    
    # Log audit action
    log_audit_action(
        user_id=user_id,
        action='logout',
        description=f'User {username} logged out successfully'
    )
    
    return redirect(url_for('auth.login'))

@bp.route('/password-reset', methods=['GET', 'POST'])
def password_reset_request():
    """Password reset request page"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    form = PasswordResetRequestForm()
    
    if form.validate_on_submit():
        email = form.email.data
        try:
            user = User.query.filter_by(email=email).first()
            
            if user:
                # In a real application, generate a secure token and send email
                # For now, just log the request
                logger.info(f"Password reset requested for {email}")
                flash('لینک بازیابی رمز عبور به ایمیل شما ارسال شد', 'success')
            else:
                # Always show success message for security reasons
                logger.info(f"Password reset requested for non-existent email: {email}")
                flash('لینک بازیابی رمز عبور به ایمیل شما ارسال شد', 'success')
            
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            logger.error(f"Error in password reset request: {str(e)}")
            flash('خطا در پردازش درخواست. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return render_template('auth/password_reset.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Password reset page"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    # In a real application, validate the token here
    # For now, just show the form
    form = PasswordResetForm()
    
    if form.validate_on_submit():
        if form.new_password.data != form.confirm_password.data:
            flash('رمز عبور‌ها مطابقت ندارند', 'danger')
            return render_template('auth/reset_password.html', form=form, token=token)
        
        try:
            # In a real application, find user by token and update password
            flash('رمز عبور شما با موفقیت تغییر کرد. اکنون می‌توانید وارد سیستم شوید.', 'success')
            logger.info("Password reset successful")
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            logger.error(f"Error resetting password: {str(e)}")
            flash('خطا در تغییر رمز عبور. لطفاً دوباره تلاش کنید.', 'danger')
    
    return render_template('auth/reset_password.html', form=form, token=token)

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page"""
    return render_template('auth/settings.html')

@bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html')

@bp.route('/toggle-sidebar', methods=['POST'])
@login_required
def toggle_sidebar():
    """Toggle sidebar state"""
    collapsed = request.json.get('collapsed', False)
    session['sidebar_collapsed'] = collapsed
    return {'success': True}
