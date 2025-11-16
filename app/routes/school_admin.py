from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FileField, DateField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import io
from datetime import datetime, date, timedelta
import logging
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps

from app.models import db, Student, Teacher, Class, Subject, Attendance, Discipline, Grade, SkillAssessment
from app.utils.sms_service import sms_service
from app.decorators import school_admin_required, role_required

logger = logging.getLogger(__name__)
bp = Blueprint('school_admin', __name__, url_prefix='/school_admin')

# === فرم‌های اعتبارسنجی ===
class SchoolSettingsForm(FlaskForm):
    school_name = StringField('نام مدرسه', validators=[
        DataRequired(message='نام مدرسه الزامی است'),
        Length(min=3, max=100, message='نام مدرسه باید بین 3 تا 100 کاراکتر باشد')
    ])
    admin_name = StringField('نام مدیر', validators=[
        DataRequired(message='نام مدیر الزامی است'),
        Length(min=3, max=100, message='نام مدیر باید بین 3 تا 100 کاراکتر باشد')
    ])
    phone = StringField('شماره تماس', validators=[
        Optional(),
        Length(max=20, message='شماره تماس باید حداکثر 20 کاراکتر باشد')
    ])
    new_password = PasswordField('رمز عبور جدید', validators=[
        Optional(),
        Length(min=8, message='رمز عبور باید حداقل 8 کاراکتر باشد')
    ])
    confirm_password = PasswordField('تایید رمز عبور', validators=[
        EqualTo('new_password', message='رمز عبور‌ها مطابقت ندارند')
    ])

class StudentForm(FlaskForm):
    code = StringField('کد دانش‌آموز', validators=[
        DataRequired(message='کد دانش‌آموز الزامی است'),
        Length(min=3, max=20, message='کد دانش‌آموز باید بین 3 تا 20 کاراکتر باشد')
    ])
    first_name = StringField('نام', validators=[
        DataRequired(message='نام الزامی است'),
        Length(min=2, max=50, message='نام باید بین 2 تا 50 کاراکتر باشد')
    ])
    last_name = StringField('نام خانوادگی', validators=[
        DataRequired(message='نام خانوادگی الزامی است'),
        Length(min=2, max=50, message='نام خانوادگی باید بین 2 تا 50 کاراکتر باشد')
    ])
    grade = SelectField('پایه', validators=[DataRequired(message='پایه الزامی است')])
    parent_phone = StringField('شماره والدین', validators=[
        Optional(),
        Length(max=20, message='شماره والدین باید حداکثر 20 کاراکتر باشد')
    ])
    parent_email = StringField('ایمیل والدین', validators=[
        Optional(),
        Email(message='ایمیل معتبر نیست')
    ])
    excel_file = FileField('فایل اکسل', validators=[Optional()])

class TeacherForm(FlaskForm):
    username = StringField('نام کاربری', validators=[
        DataRequired(message='نام کاربری الزامی است'),
        Length(min=3, max=50, message='نام کاربری باید بین 3 تا 50 کاراکتر باشد')
    ])
    password = PasswordField('رمز عبور', validators=[
        DataRequired(message='رمز عبور الزامی است'),
        Length(min=8, message='رمز عبور باید حداقل 8 کاراکتر باشد')
    ])
    name = StringField('نام کامل', validators=[
        DataRequired(message='نام کامل الزامی است'),
        Length(min=3, max=100, message='نام کامل باید بین 3 تا 100 کاراکتر باشد')
    ])
    phone = StringField('شماره تماس', validators=[
        Optional(),
        Length(max=20, message='شماره تماس باید حداکثر 20 کاراکتر باشد')
    ])
    subjects = SelectMultipleField('درسهای تدریس شده', validators=[Optional()])
    email = StringField('ایمیل', validators=[
        Optional(),
        Email(message='ایمیل معتبر نیست')
    ])

class ClassForm(FlaskForm):
    name = StringField('نام کلاس', validators=[
        DataRequired(message='نام کلاس الزامی است'),
        Length(min=2, max=50, message='نام کلاس باید بین 2 تا 50 کاراکتر باشد')
    ])
    grade = SelectField('پایه', validators=[DataRequired(message='پایه الزامی است')])
    teacher_id = SelectField('معلم کلاس', validators=[Optional()], coerce=int)
    room = StringField('شماره کلاس', validators=[Optional(), Length(max=20)])

class SubjectForm(FlaskForm):
    name = StringField('نام درس', validators=[
        DataRequired(message='نام درس الزامی است'),
        Length(min=2, max=50, message='نام درس باید بین 2 تا 50 کاراکتر باشد')
    ])
    grade = SelectField('پایه', validators=[DataRequired(message='پایه الزامی است')])
    teacher_id = SelectField('معلم', validators=[Optional()], coerce=int)

class ReportForm(FlaskForm):
    report_type = SelectField('نوع گزارش', choices=[
        ('student', 'گزارش دانش‌آموز'),
        ('class', 'گزارش کلاس'),
        ('attendance', 'گزارش حضور و غیاب'),
        ('discipline', 'گزارش انضباطی')
    ], validators=[DataRequired(message='نوع گزارش الزامی است')])
    
    student_id = SelectField('دانش‌آموز', validators=[Optional()], coerce=int)
    class_id = SelectField('کلاس', validators=[Optional()], coerce=int)
    start_date = DateField('تاریخ شروع', validators=[DataRequired(message='تاریخ شروع الزامی است')])
    end_date = DateField('تاریخ پایان', validators=[DataRequired(message='تاریخ پایان الزامی است')])

# === مسیرهای اصلی ===
@bp.route('/dashboard')
@login_required
@school_admin_required
def dashboard():
    """داشبورد مدیر مدرسه با آمار دقیق"""
    try:
        school_id = current_user.school_id
        
        # آمار اصلی
        stats = {
            'total_students': Student.query.filter_by(school_id=school_id).count(),
            'total_teachers': Teacher.query.filter_by(school_id=school_id).count(),
            'total_classes': Class.query.filter_by(school_id=school_id).count(),
            'total_subjects': Subject.query.filter_by(school_id=school_id).count()
        }
        
        # حضور و غیاب امروز
        today = date.today()
        today_attendance = Attendance.query.filter_by(date=today).join(Student).filter(Student.school_id == school_id).count()
        stats['today_attendance'] = today_attendance
        
        # آخرین فعالیت‌ها
        recent_activities = get_recent_activities(school_id)
        
        return render_template('school_admin/dashboard.html', 
                             stats=stats, 
                             recent_activities=recent_activities,
                             today=today)
    
    except Exception as e:
        logger.error(f"Error in dashboard: {str(e)}")
        flash('خطا در بارگذاری داشبورد. لطفاً دوباره تلاش کنید.', 'danger')
        return redirect(url_for('auth.index'))

def get_recent_activities(school_id, limit=10):
    """دریافت آخرین فعالیت‌ها برای داشبورد"""
    recent_activities = []
    
    # حضور و غیاب امروز
    today_attendances = Attendance.query.join(Student).filter(
        Student.school_id == school_id,
        Attendance.date == date.today()
    ).order_by(Attendance.created_at.desc()).limit(5).all()
    
    for att in today_attendances:
        recent_activities.append({
            'type': 'attendance',
            'student': att.student.full_name,
            'status': att.status,
            'time': att.created_at.strftime('%H:%M')
        })
    
    # رکوردهای انضباطی امروز
    today_disciplines = Discipline.query.join(Student).filter(
        Student.school_id == school_id,
        Discipline.date == date.today()
    ).order_by(Discipline.created_at.desc()).limit(5).all()
    
    for disc in today_disciplines:
        recent_activities.append({
            'type': 'discipline',
            'student': disc.student.full_name,
            'type_fa': 'مثبت' if disc.type == 'positive' else 'منفی',
            'points': disc.points,
            'time': disc.created_at.strftime('%H:%M')
        })
    
    # مرتب‌سازی بر اساس زمان
    recent_activities.sort(key=lambda x: x.get('time', ''), reverse=True)
    return recent_activities[:limit]

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@school_admin_required
def settings():
    """تنظیمات مدرسه و پروفایل مدیر"""
    try:
        form = SchoolSettingsForm()
        school = current_user.school
        
        # تنظیم گزینه‌های پایه برای فرم
        if request.method == 'GET':
            form.school_name.data = school.name
            form.admin_name.data = current_user.name
            form.phone.data = current_user.phone
        
        if form.validate_on_submit():
            # به‌روزرسانی نام مدرسه
            school.name = form.school_name.data
            
            # به‌روزرسانی اطلاعات مدیر
            current_user.name = form.admin_name.data
            current_user.phone = form.phone.data
            
            # تغییر رمز عبور
            if form.new_password:
                current_user.set_password(form.new_password.data)
            
            db.session.commit()
            flash('تنظیمات با موفقیت بروزرسانی شد', 'success')
            logger.info(f"School settings updated by {current_user.username}")
            return redirect(url_for('school_admin.settings'))
        
        return render_template('school_admin/settings.html', 
                             form=form, 
                             school=school,
                             admin=current_user)
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in settings: {str(e)}")
        flash('خطا در بروزرسانی تنظیمات. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error in settings: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return render_template('school_admin/settings.html', 
                         form=form, 
                         school=current_user.school,
                         admin=current_user)

@bp.route('/students', methods=['GET', 'POST'])
@login_required
@school_admin_required
def students():
    """مدیریت دانش‌آموزان با پشتیبانی از اکسل و pagination"""
    try:
        form = StudentForm()
        school_id = current_user.school_id
        
        # تنظیم گزینه‌های پایه
        grades = db.session.query(Student.grade).filter_by(school_id=school_id).distinct().order_by(Student.grade).all()
        form.grade.choices = [(g[0], g[0]) for g in grades] if grades else [('1', 'اول'), ('2', 'دوم'), ('3', 'سوم')]
        
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # پردازش فرم
        if form.validate_on_submit():
            if form.excel_file.data:
                return handle_excel_upload(form.excel_file.data, school_id)
            else:
                return handle_new_student(form, school_id)
        
        # دریافت لیست دانش‌آموزان
        students_pagination = Student.query.filter_by(school_id=school_id).order_by(
            Student.grade, Student.last_name
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('school_admin/students.html',
                             form=form,
                             students=students_pagination.items,
                             pagination=students_pagination)
    
    except Exception as e:
        logger.error(f"Error in students page: {str(e)}")
        flash('خطا در بارگذاری لیست دانش‌آموزان', 'danger')
        return render_template('school_admin/students.html', form=StudentForm(), students=[])

def handle_excel_upload(file, school_id):
    """پردازش فایل اکسل دانش‌آموزان"""
    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('فرمت فایل نامعتبر است. فقط فایل‌های اکسل مجاز هستند.', 'danger')
            return redirect(url_for('school_admin.students'))
        
        df = pd.read_excel(file)
        required_columns = ['کد', 'نام', 'نام خانوادگی', 'پایه']
        
        if not all(col in df.columns for col in required_columns):
            flash(f'ستون‌های اجباری {", ".join(required_columns)} در فایل وجود ندارند.', 'danger')
            return redirect(url_for('school_admin.students'))
        
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                student = Student(
                    code=str(row['کد']).strip(),
                    first_name=row['نام'].strip(),
                    last_name=row['نام خانوادگی'].strip(),
                    grade=row['پایه'].strip(),
                    parent_phone=str(row.get('شماره والدین', '')).strip() if not pd.isna(row.get('شماره والدین')) else None,
                    parent_email=row.get('ایمیل والدین', '').strip() if not pd.isna(row.get('ایمیل والدین')) else None,
                    school_id=school_id
                )
                db.session.add(student)
                success_count += 1
            except Exception as e:
                logger.error(f"Error adding student from excel: {str(e)}")
                error_count += 1
        
        db.session.commit()
        flash(f'دانش‌آموزان از فایل اکسل اضافه شدند. موفق: {success_count}، خطا: {error_count}', 'success')
        logger.info(f"Excel upload: {success_count} students added successfully")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing Excel file: {str(e)}")
        flash('خطا در پردازش فایل اکسل. لطفاً فرمت فایل را بررسی کنید.', 'danger')
    
    return redirect(url_for('school_admin.students'))

def handle_new_student(form, school_id):
    """افزودن دانش‌آموز جدید"""
    try:
        # بررسی تکراری بودن کد دانش‌آموز
        if Student.query.filter_by(code=form.code.data, school_id=school_id).first():
            flash('کد دانش‌آموز تکراری است', 'danger')
            return redirect(url_for('school_admin.students'))
        
        student = Student(
            code=form.code.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            grade=form.grade.data,
            parent_phone=form.parent_phone.data or None,
            parent_email=form.parent_email.data or None,
            school_id=school_id
        )
        
        db.session.add(student)
        db.session.commit()
        
        flash(f'دانش‌آموز {student.full_name} با موفقیت اضافه شد', 'success')
        logger.info(f"New student added: {student.full_name} by {current_user.username}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error adding student: {str(e)}")
        flash('خطا در افزودن دانش‌آموز. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error adding student: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return redirect(url_for('school_admin.students'))

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@school_admin_required
def edit_student(student_id):
    """ویرایش اطلاعات دانش‌آموز"""
    student = Student.query.get_or_404(student_id)
    
    # بررسی دسترسی
    if student.school_id != current_user.school_id:
        flash('شما دسترسی به این دانش‌آموز را ندارید', 'danger')
        return redirect(url_for('school_admin.students'))
    
    form = StudentForm()
    
    # تنظیم گزینه‌های پایه
    grades = db.session.query(Student.grade).filter_by(school_id=current_user.school_id).distinct().order_by(Student.grade).all()
    form.grade.choices = [(g[0], g[0]) for g in grades] if grades else [('1', 'اول'), ('2', 'دوم'), ('3', 'سوم')]
    
    if request.method == 'GET':
        form.code.data = student.code
        form.first_name.data = student.first_name
        form.last_name.data = student.last_name
        form.grade.data = student.grade
        form.parent_phone.data = student.parent_phone
        form.parent_email.data = student.parent_email
    
    if form.validate_on_submit():
        # بررسی تکراری بودن کد (به جز خود این دانش‌آموز)
        existing = Student.query.filter(Student.code == form.code.data, 
                                      Student.id != student_id,
                                      Student.school_id == current_user.school_id).first()
        if existing:
            flash('کد دانش‌آموز تکراری است', 'danger')
            return render_template('school_admin/edit_student.html', form=form, student=student)
        
        student.code = form.code.data
        student.first_name = form.first_name.data
        student.last_name = form.last_name.data
        student.grade = form.grade.data
        student.parent_phone = form.parent_phone.data or None
        student.parent_email = form.parent_email.data or None
        
        db.session.commit()
        flash('اطلاعات دانش‌آموز با موفقیت بروزرسانی شد', 'success')
        logger.info(f"Student updated: {student.full_name} by {current_user.username}")
        return redirect(url_for('school_admin.students'))
    
    return render_template('school_admin/edit_student.html', form=form, student=student)

@bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
@school_admin_required
def delete_student(student_id):
    """حذف دانش‌آموز با تأیید"""
    student = Student.query.get_or_404(student_id)
    
    # بررسی دسترسی
    if student.school_id != current_user.school_id:
        flash('شما دسترسی به این دانش‌آموز را ندارید', 'danger')
        return redirect(url_for('school_admin.students'))
    
    try:
        # بررسی حضور در کلاس‌ها
        if Class.students.any():
            flash('دانش‌آموز در کلاس‌ها ثبت شده است و قابل حذف نیست', 'warning')
            return redirect(url_for('school_admin.students'))
        
        # حذف سوابق مرتبط
        Attendance.query.filter_by(student_id=student_id).delete()
        Discipline.query.filter_by(student_id=student_id).delete()
        Grade.query.filter_by(student_id=student_id).delete()
        SkillAssessment.query.filter_by(student_id=student_id).delete()
        
        db.session.delete(student)
        db.session.commit()
        
        flash(f'دانش‌آموز {student.full_name} با موفقیت حذف شد', 'success')
        logger.info(f"Student deleted: {student.full_name} by {current_user.username}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting student: {str(e)}")
        flash('خطا در حذف دانش‌آموز. لطفاً دوباره تلاش کنید.', 'danger')
    
    return redirect(url_for('school_admin.students'))

@bp.route('/teachers', methods=['GET', 'POST'])
@login_required
@school_admin_required
def teachers():
    """مدیریت معلمان"""
    form = TeacherForm()
    school_id = current_user.school_id
    
    # تنظیم گزینه‌های فرم
    subjects = Subject.query.filter_by(school_id=school_id).all()
    form.subjects.choices = [(str(s.id), s.name) for s in subjects]
    
    if form.validate_on_submit():
        try:
            # بررسی تکراری بودن نام کاربری
            if Teacher.query.join(Teacher.user).filter_by(username=form.username.data).first():
                flash('نام کاربری تکراری است', 'danger')
                return render_template('school_admin/teachers.html', form=form, teachers=[])
            
            # ایجاد کاربر جدید
            from app.models import User
            
            user = User(
                username=form.username.data,
                name=form.name.data,
                role='teacher',
                phone=form.phone.data,
                email=form.email.data,
                school_id=school_id
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.flush()  # برای دریافت user.id
            
            # ایجاد پروفایل معلم
            teacher = Teacher(
                user_id=user.id,
                subjects=','.join(form.subjects.data) if form.subjects.data else None,
                phone=form.phone.data,
                school_id=school_id
            )
            
            db.session.add(teacher)
            db.session.commit()
            
            flash(f'معلم {form.name.data} با موفقیت اضافه شد', 'success')
            logger.info(f"New teacher added: {form.name.data} by {current_user.username}")
            return redirect(url_for('school_admin.teachers'))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error adding teacher: {str(e)}")
            flash('خطا در افزودن معلم. لطفاً دوباره تلاش کنید.', 'danger')
        except Exception as e:
            logger.error(f"Unexpected error adding teacher: {str(e)}")
            flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    teachers_list = Teacher.query.filter_by(school_id=school_id).join(Teacher.user).all()
    return render_template('school_admin/teachers.html', form=form, teachers=teachers_list)

@bp.route('/attendance', methods=['GET', 'POST'])
@login_required
@school_admin_required
def attendance():
    """مدیریت حضور و غیاب با قابلیت ارسال SMS"""
    school_id = current_user.school_id
    selected_date = request.args.get('date', date.today().isoformat())
    
    try:
        # دریافت کلاس‌ها
        classes = Class.query.filter_by(school_id=school_id).order_by(Class.grade, Class.name).all()
        
        # انتخاب کلاس
        class_id = request.args.get('class_id', type=int)
        selected_class = None
        students = []
        
        if class_id:
            selected_class = Class.query.get(class_id)
            if selected_class and selected_class.school_id == school_id:
                students = selected_class.students
                
                if request.method == 'POST':
                    return handle_attendance_submission(selected_class, students, selected_date)
        
        # دریافت حضور و غیاب روز جاری برای تمام کلاس‌ها
        today_attendance = get_today_attendance_summary(school_id, selected_date)
        
        return render_template('school_admin/attendance.html',
                             classes=classes,
                             selected_class=selected_class,
                             students=students,
                             selected_date=selected_date,
                             today_attendance=today_attendance)
    
    except Exception as e:
        logger.error(f"Error in attendance page: {str(e)}")
        flash('خطا در بارگذاری صفحه حضور و غیاب', 'danger')
        return render_template('school_admin/attendance.html', 
                             classes=[], 
                             selected_class=None,
                             students=[],
                             selected_date=selected_date,
                             today_attendance=[])

def handle_attendance_submission(selected_class, students, date_str):
    """پردازش ثبت حضور و غیاب"""
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        teacher_id = current_user.id
        
        # حذف حضور و غیاب قبلی برای این کلاس و تاریخ
        Attendance.query.filter_by(
            class_id=selected_class.id,
            date=attendance_date
        ).delete()
        
        sent_sms_count = 0
        
        for student in students:
            status = request.form.get(f'status_{student.id}', 'present')
            
            if status not in ['present', 'absent', 'late']:
                status = 'present'
            
            attendance = Attendance(
                class_id=selected_class.id,
                student_id=student.id,
                date=attendance_date,
                status=status,
                teacher_id=teacher_id
            )
            
            db.session.add(attendance)
            
            # ارسال SMS به والدین در صورت غیبت یا تأخیر
            if status in ['absent', 'late'] and student.parent_phone:
                sms_service.send_attendance_notification(
                    parent_phone=student.parent_phone,
                    student_name=student.full_name,
                    status=status
                )
                sent_sms_count += 1
        
        db.session.commit()
        
        flash_message = f'حضور و غیاب کلاس {selected_class.name} ثبت شد'
        if sent_sms_count > 0:
            flash_message += f' و {sent_sms_count} پیام به والدین ارسال شد'
        
        flash(flash_message, 'success')
        logger.info(f"Attendance recorded for class {selected_class.name} with {sent_sms_count} SMS notifications")
        
        return redirect(url_for('school_admin.attendance', 
                              date=date_str, 
                              class_id=selected_class.id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error recording attendance: {str(e)}")
        flash('خطا در ثبت حضور و غیاب. لطفاً دوباره تلاش کنید.', 'danger')
        return redirect(url_for('school_admin.attendance', 
                              date=date_str, 
                              class_id=selected_class.id))

def get_today_attendance_summary(school_id, date_str):
    """دریافت خلاصه حضور و غیاب روز جاری"""
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        query = db.session.query(
            Class.id,
            Class.name,
            Class.grade,
            db.func.count(Attendance.id).filter(Attendance.status == 'present').label('present_count'),
            db.func.count(Attendance.id).filter(Attendance.status == 'absent').label('absent_count'),
            db.func.count(Attendance.id).filter(Attendance.status == 'late').label('late_count'),
            db.func.count(Student.id).label('total_students')
        ).join(Attendance, Class.id == Attendance.class_id, isouter=True)\
         .join(Student, Class.students)\
         .filter(Class.school_id == school_id, 
                db.or_(Attendance.date == attendance_date, Attendance.date == None))\
         .group_by(Class.id, Class.name, Class.grade)
        
        return query.all()
    except Exception as e:
        logger.error(f"Error getting attendance summary: {str(e)}")
        return []

# === API Endpoints برای عملکردهای پویا ===
@bp.route('/api/classes/<int:class_id>/students')
@login_required
@school_admin_required
def get_class_students(class_id):
    """دریافت دانش‌آموزان یک کلاس به صورت JSON"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.school_id != current_user.school_id:
            return jsonify({'error': 'دسترسی غیرمجاز'}), 403
        
        students = [{
            'id': student.id,
            'name': student.full_name,
            'code': student.code,
            'grade': student.grade
        } for student in class_obj.students]
        
        return jsonify({
            'success': True,
            'students': students,
            'class_name': class_obj.name,
            'grade': class_obj.grade
        })
    
    except Exception as e:
        logger.error(f"Error in get_class_students API: {str(e)}")
        return jsonify({'error': 'خطای داخلی سرور'}), 500

@bp.route('/api/students/search')
@login_required
@school_admin_required
def search_students():
    """جستجوی دانش‌آموزان به صورت پویا"""
    query = request.args.get('q', '').strip()
    grade = request.args.get('grade', '').strip()
    
    if not query and not grade:
        return jsonify([])
    
    try:
        school_id = current_user.school_id
        students_query = Student.query.filter_by(school_id=school_id)
        
        if query:
            students_query = students_query.filter(
                db.or_(
                    Student.first_name.ilike(f'%{query}%'),
                    Student.last_name.ilike(f'%{query}%'),
                    Student.code.ilike(f'%{query}%')
                )
            )
        
        if grade:
            students_query = students_query.filter_by(grade=grade)
        
        students = students_query.limit(20).all()
        
        results = [{
            'id': student.id,
            'text': f"{student.full_name} ({student.code})",
            'grade': student.grade,
            'parent_phone': student.parent_phone or 'ندارد'
        } for student in students]
        
        return jsonify(results)
    
    except Exception as e:
        logger.error(f"Error in search_students API: {str(e)}")
        return jsonify([])

# === توابع کمکی ===
def format_date_for_display(date_obj):
    """تبدیل تاریخ به فرمت نمایشی فارسی"""
    if not date_obj:
        return ''
    return date_obj.strftime('%Y/%m/%d')

def get_grade_options(school_type='elementary'):
    """دریافت گزینه‌های پایه بر اساس نوع مدرسه"""
    grade_options = {
        'elementary': [('1', 'اول ابتدایی'), ('2', 'دوم ابتدایی'), ('3', 'سوم ابتدایی'), 
                      ('4', 'چهارم ابتدایی'), ('5', 'پنجم ابتدایی'), ('6', 'ششم ابتدایی')],
        'middle': [('7', 'اول متوسطه'), ('8', 'دوم متوسطه'), ('9', 'سوم متوسطه')],
        'high': [('10', 'دهم'), ('11', 'یازدهم'), ('12', 'دوازدهم')]
    }
    return grade_options.get(school_type, grade_options['elementary'])
