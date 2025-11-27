from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from werkzeug.security import generate_password_hash
import logging
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from functools import wraps

from app.models import db, School, User, Student, Teacher, Class
from app.decorators import super_admin_required
from app.utils.audit_log import log_audit_action
from app.utils.sms_service import sms_service
from app.utils.export_utils import export_to_excel

logger = logging.getLogger(__name__)
bp = Blueprint('super_admin', __name__, url_prefix='/super_admin')

class SchoolForm(FlaskForm):
    name = StringField('نام مدرسه', validators=[
        DataRequired(message='نام مدرسه الزامی است'),
        Length(min=3, max=100, message='نام مدرسه باید بین 3 تا 100 کاراکتر باشد')
    ])
    school_type = SelectField('نوع مدرسه', choices=[
        ('elementary', 'ابتدایی'),
        ('middle', 'متوسطه اول'),
        ('high', 'متوسطه دوم'),
        ('combined', 'یکپارچه')
    ], validators=[DataRequired(message='نوع مدرسه الزامی است')])
    address = StringField('آدرس', validators=[Optional(), Length(max=200)])
    phone = StringField('شماره تماس', validators=[Optional(), Length(max=20)])
    email = StringField('ایمیل', validators=[Optional(), Email(message='ایمیل معتبر نیست'), Length(max=100)])

class SchoolWithAdminForm(FlaskForm):
    """Form for creating school with admin account"""
    # اطلاعات مدرسه
    name = StringField('نام مدرسه', validators=[
        DataRequired(message='نام مدرسه الزامی است'),
        Length(min=3, max=100, message='نام مدرسه باید بین 3 تا 100 کاراکتر باشد')
    ])
    school_type = SelectField('نوع مدرسه', choices=[
        ('elementary', 'ابتدایی'),
        ('middle', 'متوسطه اول'),
        ('high', 'متوسطه دوم'),
        ('combined', 'یکپارچه')
    ], validators=[DataRequired(message='نوع مدرسه الزامی است')])
    address = StringField('آدرس', validators=[Optional(), Length(max=200)])
    phone = StringField('شماره تماس مدرسه', validators=[Optional(), Length(max=20)])
    email = StringField('ایمیل مدرسه', validators=[Optional(), Email(message='ایمیل معتبر نیست'), Length(max=100)])
    
    # اطلاعات مدیر مدرسه
    admin_username = StringField('نام کاربری مدیر', validators=[
        DataRequired(message='نام کاربری مدیر الزامی است'),
        Length(min=3, max=50, message='نام کاربری باید بین 3 تا 50 کاراکتر باشد')
    ])
    admin_password = PasswordField('رمز عبور مدیر', validators=[
        DataRequired(message='رمز عبور الزامی است'),
        Length(min=8, message='رمز عبور باید حداقل 8 کاراکتر باشد')
    ])
    confirm_password = PasswordField('تایید رمز عبور', validators=[
        DataRequired(message='تایید رمز عبور الزامی است'),
        EqualTo('admin_password', message='رمز عبور‌ها مطابقت ندارند')
    ])
    admin_name = StringField('نام کامل مدیر', validators=[
        DataRequired(message='نام کامل مدیر الزامی است'),
        Length(min=3, max=100, message='نام کامل باید بین 3 تا 100 کاراکتر باشد')
    ])
    admin_phone = StringField('شماره تماس مدیر', validators=[Optional(), Length(max=20)])
    admin_email = StringField('ایمیل مدیر', validators=[Optional(), Email(message='ایمیل معتبر نیست'), Length(max=100)])

class AdminForm(FlaskForm):
    username = StringField('نام کاربری', validators=[
        DataRequired(message='نام کاربری الزامی است'),
        Length(min=3, max=50, message='نام کاربری باید بین 3 تا 50 کاراکتر باشد')
    ])
    password = PasswordField('رمز عبور', validators=[
        DataRequired(message='رمز عبور الزامی است'),
        Length(min=8, message='رمز عبور باید حداقل 8 کاراکتر باشد')
    ])
    confirm_password = PasswordField('تایید رمز عبور', validators=[
        DataRequired(message='تایید رمز عبور الزامی است'),
        EqualTo('password', message='رمز عبور‌ها مطابقت ندارند')
    ])
    name = StringField('نام کامل', validators=[
        DataRequired(message='نام کامل الزامی است'),
        Length(min=3, max=100, message='نام کامل باید بین 3 تا 100 کاراکتر باشد')
    ])
    school_id = SelectField('مدرسه', validators=[DataRequired(message='مدرسه الزامی است')], coerce=int)
    phone = StringField('شماره تماس', validators=[Optional(), Length(max=20)])
    email = StringField('ایمیل', validators=[Optional(), Email(message='ایمیل معتبر نیست'), Length(max=100)])
    
    def validate_username(self, field):
        """Check for duplicate username"""
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('این نام کاربری قبلاً استفاده شده است')

class ImpersonateForm(FlaskForm):
    admin_id = HiddenField('ID مدیر', validators=[DataRequired()])
    confirm = StringField('تأیید', validators=[DataRequired(message='برای تأیید، عبارت "تأیید" را وارد کنید')])
    
    def validate_confirm(self, field):
        if field.data.lower() != 'تأیید':
            raise ValidationError('عبارت تأیید صحیح نیست')

@bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """Super Admin dashboard"""
    try:
        # Get statistics
        stats = {
            'total_schools': School.query.count(),
            'total_admins': User.query.filter_by(role='school_admin').count(),
            'total_students': Student.query.count(),
            'total_teachers': Teacher.query.count(),
        }
        
        # Get recent schools
        recent_schools = School.query.order_by(School.created_at.desc()).limit(10).all()
        
        # Get school type statistics
        school_type_stats = db.session.query(
            School.type,
            db.func.count(School.id).label('count')
        ).group_by(School.type).all()
        
        # Get recent activities
        from app.models import AuditLog
        recent_activities = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
        
        return render_template('super_admin/dashboard.html',
                             stats=stats,
                             recent_schools=recent_schools,
                             school_type_stats=school_type_stats,
                             recent_activities=recent_activities)
    
    except Exception as e:
        logger.error(f"Error in super admin dashboard: {str(e)}")
        flash('خطا در بارگذاری داشبورد. لطفاً دوباره تلاش کنید.', 'danger')
        return redirect(url_for('auth.index'))

@bp.route('/schools', methods=['GET', 'POST'])
@login_required
@super_admin_required
def schools():
    """Manage schools with optional admin creation"""
    # ✅ اصلاح: استفاده از فرم جدید برای ایجاد مدرسه با مدیر
    school_form = SchoolForm()
    school_with_admin_form = SchoolWithAdminForm()
    
    # Handle school creation with admin
    if request.method == 'POST':
        form_type = request.form.get('form_type', 'basic')
        
        if form_type == 'with_admin':
            form = school_with_admin_form
        else:
            form = school_form
        
        if form.validate_on_submit():
            try:
                # ✅ بررسی تکراری نبودن نام مدرسه
                existing_school = School.query.filter_by(name=form.name.data.strip()).first()
                if existing_school:
                    flash('نام مدرسه تکراری است. لطفاً نام متفاوتی انتخاب کنید.', 'danger')
                    return render_template('super_admin/schools.html', 
                                         school_form=school_form,
                                         school_with_admin_form=school_with_admin_form,
                                         schools=School.query.all())
                
                # ✅ ایجاد مدرسه
                school = School(
                    name=form.name.data.strip(),
                    type=form.school_type.data,
                    address=getattr(form, 'address', None).data if hasattr(form, 'address') else None,
                    phone=getattr(form, 'phone', None).data if hasattr(form, 'phone') else None,
                    email=getattr(form, 'email', None).data if hasattr(form, 'email') else None
                )
                
                db.session.add(school)
                db.session.flush()  # برای دریافت ID
                
                # ✅ ایجاد مدیر مدرسه اگر فرم شامل اطلاعات مدیر باشد
                if hasattr(form, 'admin_username'):
                    admin = User(
                        username=form.admin_username.data.strip(),
                        name=form.admin_name.data.strip(),
                        role='school_admin',
                        phone=getattr(form, 'admin_phone', None).data if hasattr(form, 'admin_phone') else None,
                        email=getattr(form, 'admin_email', None).data if hasattr(form, 'admin_email') else None,
                        school_id=school.id,
                        is_active=True
                    )
                    admin.set_password(form.admin_password.data)
                    
                    db.session.add(admin)
                    db.session.flush()  # برای دریافت ID کاربر
                    
                    # ✅ اختصاص مدیر به مدرسه
                    school.principal_id = admin.id
                
                db.session.commit()
                
                # ✅ ایجاد کلاس‌های پیش‌فرض برای مدرسه
                create_default_classes_for_school(school.id)
                
                # ✅ ایجاد مهارت‌های پیش‌فرض
                create_default_skills_for_school(school.id)
                
                # ✅ ایجاد معلم پیش‌فرض (اختیاری)
                create_default_teacher_for_school(school.id)
                
                flash(f'مدرسه "{school.name}" با موفقیت ایجاد شد!', 'success')
                logger.info(f"New school created: {school.name} by {current_user.username}")
                
                # ✅ ریدایرکت به همان صفحه برای نمایش مدرسه جدید
                return redirect(url_for('super_admin.schools'))
                
            except SQLAlchemyError as e:
                db.session.rollback()
                logger.error(f"Database error creating school: {str(e)}")
                flash('خطا در ایجاد مدرسه. لطفاً دوباره تلاش کنید.', 'danger')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Unexpected error creating school: {str(e)}")
                flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    # ✅ نمایش خطاها در صورت وجود
    if school_form.errors:
        for field, errors in school_form.errors.items():
            for error in errors:
                flash(f"خطا در {getattr(school_form, field).label.text}: {error}", 'danger')
    
    if school_with_admin_form.errors:
        for field, errors in school_with_admin_form.errors.items():
            for error in errors:
                flash(f"خطا در {getattr(school_with_admin_form, field).label.text}: {error}", 'danger')
    
    # ✅ گرفتن مدارس با pagination
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    query = School.query
    if search_query:
        query = query.filter(School.name.ilike(f'%{search_query}%'))
    
    schools_pagination = query.order_by(School.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    
    return render_template('super_admin/schools.html', 
                         school_form=school_form,
                         school_with_admin_form=school_with_admin_form,
                         schools=schools_pagination.items,
                         pagination=schools_pagination,
                         search_query=search_query)

@bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_school(school_id):
    """Edit school information"""
    school = School.query.get_or_404(school_id)
    form = SchoolForm()
    
    if request.method == 'GET':
        form.name.data = school.name
        form.school_type.data = school.type
        form.address.data = school.address or ''
        form.phone.data = school.phone or ''
        form.email.data = school.email or ''
    
    if form.validate_on_submit():
        try:
            # Check for duplicate name (excluding current school)
            existing = School.query.filter(School.name == form.name.data, School.id != school_id).first()
            if existing:
                flash('نام مدرسه تکراری است', 'danger')
                return render_template('super_admin/edit_school.html', form=form, school=school)
            
            old_name = school.name
            school.name = form.name.data
            school.type = form.school_type.data
            school.address = form.address.data or None
            school.phone = form.phone.data or None
            school.email = form.email.data or None
            
            db.session.commit()
            
            # Log audit action
            log_audit_action(
                user_id=current_user.id,
                action='edit_school',
                description=f'مدرسه "{old_name}" به "{school.name}" تغییر کرد',
                school_id=school.id
            )
            
            flash(f'اطلاعات مدرسه "{school.name}" با موفقیت بروزرسانی شد', 'success')
            logger.info(f"School updated: {old_name} -> {school.name} by {current_user.username}")
            
            return redirect(url_for('super_admin.schools'))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating school: {str(e)}")
            flash('خطا در بروزرسانی مدرسه. لطفاً دوباره تلاش کنید.', 'danger')
        except Exception as e:
            logger.error(f"Unexpected error updating school: {str(e)}")
            flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return render_template('super_admin/edit_school.html', form=form, school=school)

@bp.route('/schools/<int:school_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_school(school_id):
    """Delete school"""
    school = School.query.get_or_404(school_id)
    
    try:
        # Check for dependencies
        student_count = Student.query.filter_by(school_id=school_id).count()
        teacher_count = Teacher.query.filter_by(school_id=school_id).count()
        class_count = Class.query.filter_by(school_id=school_id).count()
        
        if student_count > 0 or teacher_count > 0 or class_count > 0:
            flash(f'مدرسه "{school.name}" دارای داده‌های فعال است و قابل حذف نیست. ابتدا داده‌ها را حذف یا انتقال دهید.', 'warning')
            return redirect(url_for('super_admin.schools'))
        
        school_name = school.name
        db.session.delete(school)
        db.session.commit()
        
        # Log audit action
        log_audit_action(
            user_id=current_user.id,
            action='delete_school',
            description=f'مدرسه "{school_name}" حذف شد',
            school_id=school_id
        )
        
        flash(f'مدرسه "{school_name}" با موفقیت حذف شد', 'success')
        logger.info(f"School deleted: {school_name} by {current_user.username}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error deleting school: {str(e)}")
        flash('خطا در حذف مدرسه. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error deleting school: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return redirect(url_for('super_admin.schools'))

@bp.route('/admins', methods=['GET', 'POST'])
@login_required
@super_admin_required
def admins():
    """Manage school admins"""
    form = AdminForm()
    
    # Set school choices for form
    schools = School.query.order_by(School.name).all()
    form.school_id.choices = [(school.id, school.name) for school in schools]
    
    # Handle form submission
    if form.validate_on_submit():
        try:
            # Create new user
            user = User(
                username=form.username.data,
                name=form.name.data,
                role='school_admin',
                phone=form.phone.data or None,
                email=form.email.data or None,
                school_id=form.school_id.data,
                is_active=True
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            # Send welcome notification
            send_welcome_notification(user)
            
            # Log audit action
            log_audit_action(
                user_id=current_user.id,
                action='create_admin',
                description=f'مدیر جدید "{user.name}" برای مدرسه "{user.school.name}" ایجاد شد',
                school_id=user.school_id,
                target_user_id=user.id
            )
            
            flash(f'مدیر "{user.name}" با موفقیت اضافه شد', 'success')
            logger.info(f"New admin created: {user.name} for school {user.school.name} by {current_user.username}")
            
            return redirect(url_for('super_admin.admins'))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating admin: {str(e)}")
            flash('خطا در ایجاد مدیر. لطفاً دوباره تلاش کنید.', 'danger')
        except Exception as e:
            logger.error(f"Unexpected error creating admin: {str(e)}")
            flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    # Get admins with pagination and filtering
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    school_filter = request.args.get('school', type=int)
    
    query = User.query.filter_by(role='school_admin').join(School)
    
    if search_query:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search_query}%'),
                User.name.ilike(f'%{search_query}%'),
                School.name.ilike(f'%{search_query}%')
            )
        )
    
    if school_filter:
        query = query.filter(User.school_id == school_filter)
    
    admins_pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    
    # Get school statistics for filters
    school_stats = db.session.query(
        School.id,
        School.name,
        db.func.count(User.id).label('admin_count')
    ).outerjoin(User, db.and_(User.school_id == School.id, User.role == 'school_admin'))\
     .group_by(School.id, School.name)\
     .order_by(School.name).all()
    
    return render_template('super_admin/admins.html',
                         form=form,
                         admins=admins_pagination.items,
                         pagination=admins_pagination,
                         search_query=search_query,
                         school_filter=school_filter,
                         school_stats=school_stats,
                         schools=schools)

@bp.route('/impersonate', methods=['GET', 'POST'])
@login_required
@super_admin_required
def impersonate():
    """Impersonate a school admin"""
    form = ImpersonateForm()
    
    if form.validate_on_submit():
        admin_id = int(form.admin_id.data)
        admin = User.query.get(admin_id)
        
        if not admin or admin.role != 'school_admin':
            flash('مدیر مورد نظر یافت نشد', 'danger')
            return redirect(url_for('super_admin.admins'))
        
        # Store original user in session
        session['original_user'] = {
            'user_id': current_user.id,
            'username': current_user.username,
            'role': current_user.role
        }
        
        # Log audit action
        log_audit_action(
            user_id=session['original_user']['user_id'],
            action='impersonate',
            description=f'ورود به عنوان مدیر "{admin.name}" از مدرسه "{admin.school.name}"',
            school_id=admin.school_id,
            target_user_id=admin.id
        )
        
        # Login as the admin
        from flask_login import login_user
        login_user(admin)
        
        flash(f'شما اکنون به عنوان مدیر "{admin.name}" وارد شده‌اید', 'info')
        logger.info(f"Impersonation: Super Admin {current_user.username} logged in as {admin.name}")
        
        return redirect(url_for('school_admin.dashboard'))
    
    # Get list of admins for selection
    admins = User.query.filter_by(role='school_admin').join(School).order_by(School.name, User.name).all()
    
    return render_template('super_admin/impersonate.html', form=form, admins=admins)

@bp.route('/impersonate/stop')
@login_required
def stop_impersonation():
    """Stop impersonation and return to original account"""
    if 'original_user' not in session:
        flash('شما در حالت impersonation نیستید', 'info')
        return redirect(url_for('auth.index'))
    
    original_user = session['original_user']
    
    # Return to original account
    from flask_login import login_user
    original_admin = User.query.get(original_user['user_id'])
    
    if original_admin:
        login_user(original_admin)
        session.pop('original_user', None)
        
        # Log audit action
        log_audit_action(
            user_id=original_admin.id,
            action='stop_impersonation',
            description='خروج از حالت impersonation'
        )
        
        flash('شما با موفقیت به حساب اصلی خود بازگشتید', 'success')
        logger.info(f"Impersonation stopped: User returned to original account {original_admin.username}")
    
    return redirect(url_for('super_admin.dashboard'))

@bp.route('/audit-log')
@login_required
@super_admin_required
def get_audit_log():
    """Get audit log"""
    from app.models import AuditLog
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('super_admin/audit_log.html', logs=logs.items, pagination=logs)

# Helper functions
def create_default_classes_for_school(school_id):
    """Create default classes for new school"""
    try:
        school = School.query.get(school_id)
        
        if school.type in ['elementary', 'combined']:
            default_grades = ['اول', 'دوم', 'سوم', 'چهارم', 'پنجم', 'ششم']
        elif school.type == 'middle':
            default_grades = ['هفتم', 'هشتم', 'نهم']
        elif school.type == 'high':
            default_grades = ['دهم', 'یازدهم', 'دوازدهم']
        else:
            default_grades = ['اول', 'دوم', 'سوم']
        
        for grade in default_grades:
            class_name = f"{grade} - {school.name}"
            existing_class = Class.query.filter_by(name=class_name, school_id=school_id).first()
            
            if not existing_class:
                default_class = Class(
                    name=class_name,
                    grade=grade,
                    school_id=school_id
                )
                db.session.add(default_class)
        
        db.session.commit()
        logger.info(f"Default classes created for school {school_id}")
        
    except Exception as e:
        logger.error(f"Error creating default classes: {str(e)}")
        db.session.rollback()

def create_default_skills_for_school(school_id):
    """Create default skills for a school"""
    from app.models import Skill
    
    default_skills = [
        {'name': 'شنوایی', 'category': 'academic'},
        {'name': 'نوشتاری', 'category': 'academic'},
        {'name': 'حل مسئله', 'category': 'academic'},
        {'name': 'گفتاری', 'category': 'communication'},
        {'name': 'ارتباطی', 'category': 'communication'},
        {'name': 'فنی', 'category': 'technical'},
        {'name': 'خلاقیت', 'category': 'social'},
        {'name': 'کار گروهی', 'category': 'social'}
    ]
    
    for skill_data in default_skills:
        existing_skill = Skill.query.filter_by(
            name=skill_data['name'],
            school_id=school_id
        ).first()
        
        if not existing_skill:
            skill = Skill(
                name=skill_data['name'],
                category=skill_data['category'],
                school_id=school_id
            )
            db.session.add(skill)
    
    db.session.commit()
    logger.info(f"Default skills created for school {school_id}")

def create_default_teacher_for_school(school_id):
    """Create default teacher account for new school"""
    try:
        # ایجاد یک حساب معلم پیش‌فرض
        default_username = f"teacher_{school_id}"
        default_password = "teacher123"
        
        existing_teacher = User.query.filter_by(username=default_username).first()
        
        if not existing_teacher:
            teacher = User(
                username=default_username,
                name=f"معلم پیش‌فرض مدرسه {school_id}",
                role='teacher',
                school_id=school_id,
                is_active=True
            )
            teacher.set_password(default_password)
            
            db.session.add(teacher)
            db.session.commit()
            
            # ایجاد پروفایل معلم
            teacher_profile = Teacher(
                user_id=teacher.id,
                school_id=school_id
            )
            db.session.add(teacher_profile)
            db.session.commit()
            
            logger.info(f"Default teacher created for school {school_id}")
            
    except Exception as e:
        logger.error(f"Error creating default teacher: {str(e)}")
        db.session.rollback()

def send_welcome_notification(user):
    """Send welcome notification to new admin"""
    try:
        if user.phone:
            message = f"""
سلام {user.name}،
به سیستم مدیریت مدرسه {user.school.name} خوش‌آمدید.
نام کاربری: {user.username}
رمز عبور: (رمز عبور فعلی شما)
لطفاً پس از ورود، رمز عبور خود را تغییر دهید.
            """
            sms_service.send(user.phone, message)
            logger.info(f"Welcome SMS sent to admin {user.username}")
    
    except Exception as e:
        logger.error(f"Error sending welcome notification to {user.username}: {str(e)}")
