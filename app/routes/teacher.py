from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, IntegerField, TextAreaField, DateField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from werkzeug.datastructures import MultiDict
import logging
from datetime import date, datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, case, and_, or_
from functools import wraps

from app.models import db, Class, Student, Subject, Grade, Attendance, Discipline, SkillAssessment, Skill
from app.decorators import teacher_required, role_required
from app.utils.sms_service import sms_service, get_status_text, get_status_badge
from app.utils.export_utils import export_to_excel

logger = logging.getLogger(__name__)
bp = Blueprint('teacher', __name__, url_prefix='/teacher')

# === فرم‌های اعتبارسنجی ===
class GradeForm(FlaskForm):
    student_id = HiddenField('ID دانش‌آموز', validators=[DataRequired()])
    subject_id = SelectField('درس', validators=[DataRequired(message='درس الزامی است')], coerce=int)
    date = DateField('تاریخ', default=date.today, validators=[DataRequired(message='تاریخ الزامی است')])
    
    # برای متوسطه
    score = FloatField('نمره', validators=[Optional(), NumberRange(min=0, max=20, message='نمره باید بین 0 تا 20 باشد')])
    max_score = FloatField('حداکثر نمره', default=20.0, validators=[Optional(), NumberRange(min=1, message='حداکثر نمره باید حداقل 1 باشد')])
    
    # برای ابتدایی
    level = SelectField('سطح', choices=[
        ('excellent', 'عالی'),
        ('very_good', 'خیلی خوب'),
        ('good', 'خوب'),
        ('needs_effort', 'نیاز به تلاش')
    ], validators=[Optional()])
    
    description = TextAreaField('توضیحات', validators=[Optional(), Length(max=500)])
    
    def validate(self, extra_validators=None):
        """اعتبارسنجی مشترک برای هر دو نوع مدرسه"""
        if not super().validate(extra_validators):
            return False
        
        school = current_user.school
        if not school:
            self.subject_id.errors.append('مدرسه یافت نشد')
            return False
        
        if school.type in ['middle', 'high']:
            if self.score.data is None:
                self.score.errors.append('نمره الزامی است')
                return False
        else:
            if not self.level.data:
                self.level.errors.append('سطح الزامی است')
                return False
        
        return True

class AttendanceForm(FlaskForm):
    date = DateField('تاریخ', default=date.today, validators=[DataRequired(message='تاریخ الزامی است')])
    # وضعیت‌ها به صورت داینامیک از طریق JavaScript اضافه می‌شوند

class DisciplineForm(FlaskForm):
    student_id = SelectField('دانش‌آموز', validators=[DataRequired(message='دانش‌آموز الزامی است')], coerce=int)
    date = DateField('تاریخ', default=date.today, validators=[DataRequired(message='تاریخ الزامی است')])
    type = SelectField('نوع', choices=[
        ('positive', 'مثبت'),
        ('negative', 'منفی')
    ], validators=[DataRequired(message='نوع الزامی است')])
    points = IntegerField('امتیاز', validators=[
        DataRequired(message='امتیاز الزامی است'),
        NumberRange(min=-10, max=10, message='امتیاز باید بین -10 تا 10 باشد')
    ])
    description = TextAreaField('توضیحات', validators=[
        DataRequired(message='توضیحات الزامی است'),
        Length(min=5, max=500, message='توضیحات باید بین 5 تا 500 کاراکتر باشد')
    ])

class SkillAssessmentForm(FlaskForm):
    student_id = SelectField('دانش‌آموز', validators=[DataRequired(message='دانش‌آموز الزامی است')], coerce=int)
    skill_id = SelectField('مهارت', validators=[DataRequired(message='مهارت الزامی است')], coerce=int)
    date = DateField('تاریخ', default=date.today, validators=[DataRequired(message='تاریخ الزامی است')])
    level = SelectField('سطح', choices=[
        ('excellent', 'عالی'),
        ('very_good', 'خیلی خوب'),
        ('good', 'خوب'),
        ('needs_effort', 'نیاز به تلاش')
    ], validators=[DataRequired(message='سطح الزامی است')])
    notes = TextAreaField('یادداشت‌ها', validators=[Optional(), Length(max=500)])

# === مسیرهای اصلی ===
@bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    """داشبورد معلم با آمار کامل"""
    try:
        teacher = current_user.teacher_profile
        if not teacher:
            flash('پروفایل معلم یافت نشد', 'danger')
            return redirect(url_for('auth.index'))
        
        # کلاس‌های معلم
        classes = Class.query.filter_by(teacher_id=teacher.id).order_by(Class.grade, Class.name).all()
        
        # آمار کلاس‌ها
        class_stats = []
        for cls in classes:
            student_count = len(cls.students)
            today_attendance = Attendance.query.filter_by(
                class_id=cls.id,
                date=date.today()
            ).count()
            
            class_stats.append({
                'class': cls,
                'student_count': student_count,
                'today_attendance': today_attendance,
                'attendance_percentage': round((today_attendance / student_count * 100), 1) if student_count > 0 else 0
            })
        
        # آخرین فعالیت‌ها
        recent_grades = get_recent_grades(teacher.id)
        recent_attendance = get_recent_attendance(teacher.id)
        
        return render_template('teacher/dashboard.html',
                             class_stats=class_stats,
                             recent_grades=recent_grades,
                             recent_attendance=recent_attendance,
                             today=date.today())
    
    except Exception as e:
        logger.error(f"Error in teacher dashboard: {str(e)}")
        flash('خطا در بارگذاری داشبورد. لطفاً دوباره تلاش کنید.', 'danger')
        return redirect(url_for('auth.index'))

def get_recent_grades(teacher_id, limit=5):
    """دریافت آخرین نمرات ثبت شده توسط معلم"""
    return Grade.query.filter_by(teacher_id=teacher_id)\
        .join(Student)\
        .join(Subject)\
        .order_by(Grade.date.desc(), Grade.created_at.desc())\
        .limit(limit)\
        .all()

def get_recent_attendance(teacher_id, limit=5):
    """دریافت آخرین حضور و غیاب‌های ثبت شده توسط معلم"""
    return Attendance.query.filter_by(teacher_id=teacher_id)\
        .join(Student)\
        .join(Class)\
        .order_by(Attendance.date.desc(), Attendance.created_at.desc())\
        .limit(limit)\
        .all()

@bp.route('/class/<int:class_id>/grades', methods=['GET', 'POST'])
@login_required
@teacher_required
def grades(class_id):
    """مدیریت نمرات کلاس با پشتیبانی از هر دو نوع مدرسه"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.teacher_id != current_user.teacher_profile.id:
            flash('شما دسترسی به این کلاس را ندارید', 'danger')
            return redirect(url_for('teacher.dashboard'))
        
        # دریافت تاریخ انتخاب شده
        selected_date_str = request.args.get('date', date.today().isoformat())
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except:
            selected_date = date.today()
        
        form = GradeForm()
        
        # تنظیم گزینه‌های درس‌ها
        subjects = Subject.query.filter_by(
            grade=class_obj.grade,
            school_id=current_user.school_id
        ).order_by(Subject.name).all()
        form.subject_id.choices = [(subject.id, subject.name) for subject in subjects]
        
        # پردازش فرم
        if form.validate_on_submit():
            return handle_grade_submission(form, class_obj, selected_date)
        
        # دریافت داده‌ها
        students = sorted(class_obj.students, key=lambda x: (x.last_name, x.first_name))
        grades_list = get_class_grades(class_obj.id, selected_date)
        grades_summary = get_grades_summary(class_obj.id, selected_date)
        
        return render_template('teacher/grades.html',
                             class_info=class_obj,
                             students=students,
                             form=form,
                             grades=grades_list,
                             grades_summary=grades_summary,
                             selected_date=selected_date,
                             school_type=current_user.school.type)
    
    except Exception as e:
        logger.error(f"Error in grades page: {str(e)}")
        flash('خطا در بارگذاری صفحه نمرات', 'danger')
        return redirect(url_for('teacher.dashboard'))

def handle_grade_submission(form, class_obj, selected_date):
    """پردازش ثبت نمره جدید"""
    try:
        school = current_user.school
        teacher_id = current_user.teacher_profile.id
        student_id = int(form.student_id.data)
        
        # بررسی وجود نمره برای همین دانش‌آموز، درس و تاریخ
        existing_grade = Grade.query.filter_by(
            student_id=student_id,
            subject_id=form.subject_id.data,
            class_id=class_obj.id,
            date=selected_date
        ).first()
        
        if existing_grade:
            flash('نمره برای این دانش‌آموز و درس در این تاریخ قبلاً ثبت شده است', 'warning')
            return redirect(url_for('teacher.grades', class_id=class_obj.id, date=selected_date))
        
        # ایجاد نمره جدید
        grade = Grade(
            student_id=student_id,
            subject_id=form.subject_id.data,
            class_id=class_obj.id,
            teacher_id=teacher_id,
            date=selected_date,
            description=form.description.data or None,
            school_type=school.type
        )
        
        if school.type in ['middle', 'high']:
            grade.score = form.score.data
            grade.max_score = form.max_score.data or 20.0
        else:
            grade.level = form.level.data
        
        db.session.add(grade)
        db.session.commit()
        
        student = Student.query.get(student_id)
        subject = Subject.query.get(form.subject_id.data)
        
        flash(f'نمره {student.full_name} برای درس {subject.name} با موفقیت ثبت شد', 'success')
        logger.info(f"Grade recorded for {student.full_name} in {subject.name} by {current_user.username}")
        
        return redirect(url_for('teacher.grades', class_id=class_obj.id, date=selected_date))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error recording grade: {str(e)}")
        flash('خطا در ثبت نمره. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error recording grade: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return redirect(url_for('teacher.grades', class_id=class_obj.id, date=selected_date))

def get_class_grades(class_id, selected_date):
    """دریافت نمرات کلاس برای تاریخ مشخص"""
    return Grade.query.filter_by(class_id=class_id, date=selected_date)\
        .join(Student)\
        .join(Subject)\
        .order_by(Student.last_name, Student.first_name, Subject.name)\
        .all()

def get_grades_summary(class_id, selected_date):
    """دریافت خلاصه نمرات کلاس"""
    school_type = current_user.school.type
    
    if school_type in ['middle', 'high']:
        return db.session.query(
            Subject.name,
            func.avg(Grade.score).label('avg_score'),
            func.count(Grade.id).label('count')
        ).join(Subject)\
         .filter(Grade.class_id == class_id, Grade.date == selected_date)\
         .group_by(Subject.id, Subject.name)\
         .order_by(Subject.name)\
         .all()
    else:
        return db.session.query(
            Subject.name,
            Grade.level,
            func.count(Grade.id).label('count')
        ).join(Subject)\
         .filter(Grade.class_id == class_id, Grade.date == selected_date)\
         .group_by(Subject.id, Subject.name, Grade.level)\
         .order_by(Subject.name, Grade.level)\
         .all()

@bp.route('/class/<int:class_id>/attendance', methods=['GET', 'POST'])
@login_required
@teacher_required
def attendance(class_id):
    """مدیریت حضور و غیاب با ارسال خودکار SMS"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.teacher_id != current_user.teacher_profile.id:
            flash('شما دسترسی به این کلاس را ندارید', 'danger')
            return redirect(url_for('teacher.dashboard'))
        
        # دریافت تاریخ انتخاب شده
        selected_date_str = request.args.get('date', date.today().isoformat())
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except:
            selected_date = date.today()
        
        form = AttendanceForm()
        
        # پردازش فرم
        if request.method == 'POST' and form.validate_on_submit():
            return handle_attendance_submission(class_obj, selected_date)
        
        # دریافت داده‌ها
        students = sorted(class_obj.students, key=lambda x: (x.last_name, x.first_name))
        attendance_records = get_class_attendance(class_obj.id, selected_date)
        
        # تبدیل به دیکشنری برای دسترسی سریع
        attendance_dict = {att.student_id: att.status for att in attendance_records}
        
        return render_template('teacher/attendance.html',
                             class_info=class_obj,
                             students=students,
                             attendance=attendance_dict,
                             form=form,
                             selected_date=selected_date,
                             today=date.today())
    
    except Exception as e:
        logger.error(f"Error in attendance page: {str(e)}")
        flash('خطا در بارگذاری صفحه حضور و غیاب', 'danger')
        return redirect(url_for('teacher.dashboard'))

def handle_attendance_submission(class_obj, selected_date):
    """پردازش ثبت حضور و غیاب"""
    try:
        teacher_id = current_user.teacher_profile.id
        school_id = current_user.school_id
        
        # حذف حضور و غیاب قبلی برای این کلاس و تاریخ
        Attendance.query.filter_by(
            class_id=class_obj.id,
            date=selected_date
        ).delete()
        
        sent_sms_count = 0
        absent_count = 0
        late_count = 0
        
        # دریافت تمام دانش‌آموزان کلاس
        students = class_obj.students
        
        for student in students:
            status_key = f'status_{student.id}'
            if status_key in request.form:
                status = request.form[status_key]
                
                if status not in ['present', 'absent', 'late']:
                    status = 'present'
                
                # ایجاد رکورد حضور و غیاب
                attendance = Attendance(
                    class_id=class_obj.id,
                    student_id=student.id,
                    date=selected_date,
                    status=status,
                    teacher_id=teacher_id
                )
                
                db.session.add(attendance)
                
                # ارسال SMS برای غیبت یا تأخیر
                if status in ['absent', 'late'] and student.parent_phone:
                    sms_service.send_attendance_notification(
                        parent_phone=student.parent_phone,
                        student_name=student.full_name,
                        status=status
                    )
                    sent_sms_count += 1
                    
                    if status == 'absent':
                        absent_count += 1
                    else:
                        late_count += 1
        
        db.session.commit()
        
        # پیام موفقیت‌آمیز
        flash_message = f'حضور و غیاب کلاس {class_obj.name} برای تاریخ {selected_date} ثبت شد'
        if sent_sms_count > 0:
            flash_message += f' و {sent_sms_count} پیام ({absent_count} غیبت، {late_count} تأخیر) به والدین ارسال شد'
        
        flash(flash_message, 'success')
        logger.info(f"Attendance recorded for class {class_obj.name} ({len(students)} students) with {sent_sms_count} SMS notifications")
        
        return redirect(url_for('teacher.attendance', class_id=class_obj.id, date=selected_date))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error recording attendance: {str(e)}")
        flash('خطا در ثبت حضور و غیاب. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error recording attendance: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return redirect(url_for('teacher.attendance', class_id=class_obj.id, date=selected_date))

def get_class_attendance(class_id, selected_date):
    """دریافت حضور و غیاب کلاس برای تاریخ مشخص"""
    return Attendance.query.filter_by(class_id=class_id, date=selected_date).all()

@bp.route('/class/<int:class_id>/discipline', methods=['GET', 'POST'])
@login_required
@teacher_required
def discipline(class_id):
    """مدیریت نمرات انضباطی"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.teacher_id != current_user.teacher_profile.id:
            flash('شما دسترسی به این کلاس را ندارید', 'danger')
            return redirect(url_for('teacher.dashboard'))
        
        # دریافت تاریخ انتخاب شده
        selected_date_str = request.args.get('date', date.today().isoformat())
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except:
            selected_date = date.today()
        
        form = DisciplineForm()
        
        # تنظیم گزینه‌های دانش‌آموزان
        students = sorted(class_obj.students, key=lambda x: (x.last_name, x.first_name))
        form.student_id.choices = [(student.id, student.full_name) for student in students]
        
        # پردازش فرم
        if form.validate_on_submit():
            return handle_discipline_submission(form, class_obj, selected_date)
        
        # دریافت داده‌ها
        discipline_records = get_class_discipline(class_obj.id, selected_date)
        discipline_summary = get_discipline_summary(class_obj.id, selected_date)
        
        return render_template('teacher/discipline.html',
                             class_info=class_obj,
                             form=form,
                             discipline=discipline_records,
                             discipline_summary=discipline_summary,
                             students=students,
                             selected_date=selected_date)
    
    except Exception as e:
        logger.error(f"Error in discipline page: {str(e)}")
        flash('خطا در بارگذاری صفحه انضباط', 'danger')
        return redirect(url_for('teacher.dashboard'))

def handle_discipline_submission(form, class_obj, selected_date):
    """پردازش ثبت نمره انضباطی"""
    try:
        teacher_id = current_user.teacher_profile.id
        
        discipline = Discipline(
            student_id=form.student_id.data,
            teacher_id=teacher_id,
            class_id=class_obj.id,
            date=selected_date,
            type=form.type.data,
            points=form.points.data,
            description=form.description.data
        )
        
        db.session.add(discipline)
        db.session.commit()
        
        student = Student.query.get(form.student_id.data)
        
        flash_type = 'success' if form.type.data == 'positive' else 'warning'
        flash_message = f'نمره {"مثبت" if form.type.data == "positive" else "منفی"} برای {student.full_name} با موفقیت ثبت شد'
        
        flash(flash_message, flash_type)
        logger.info(f"Discipline recorded for {student.full_name} ({form.type.data}) by {current_user.username}")
        
        return redirect(url_for('teacher.discipline', class_id=class_obj.id, date=selected_date))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error recording discipline: {str(e)}")
        flash('خطا در ثبت نمره انضباطی. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error recording discipline: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return redirect(url_for('teacher.discipline', class_id=class_obj.id, date=selected_date))

def get_class_discipline(class_id, selected_date):
    """دریافت نمرات انضباطی کلاس برای تاریخ مشخص"""
    return Discipline.query.filter_by(class_id=class_id, date=selected_date)\
        .join(Student)\
        .order_by(Discipline.created_at.desc())\
        .all()

def get_discipline_summary(class_id, selected_date):
    """دریافت خلاصه نمرات انضباطی کلاس"""
    return db.session.query(
        Discipline.type,
        func.sum(Discipline.points).label('total_points'),
        func.count(Discipline.id).label('count')
    ).filter_by(class_id=class_id, date=selected_date)\
     .group_by(Discipline.type)\
     .all()

@bp.route('/class/<int:class_id>/skills', methods=['GET', 'POST'])
@login_required
@teacher_required
def skills(class_id):
    """مدیریت ارزیابی مهارت‌ها"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.teacher_id != current_user.teacher_profile.id:
            flash('شما دسترسی به این کلاس را ندارید', 'danger')
            return redirect(url_for('teacher.dashboard'))
        
        # دریافت تاریخ انتخاب شده
        selected_date_str = request.args.get('date', date.today().isoformat())
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except:
            selected_date = date.today()
        
        form = SkillAssessmentForm()
        
        # تنظیم گزینه‌ها
        students = sorted(class_obj.students, key=lambda x: (x.last_name, x.first_name))
        form.student_id.choices = [(student.id, student.full_name) for student in students]
        
        skills = Skill.query.filter_by(school_id=current_user.school_id).order_by(Skill.name).all()
        form.skill_id.choices = [(skill.id, skill.name) for skill in skills]
        
        # پردازش فرم
        if form.validate_on_submit():
            return handle_skill_assessment_submission(form, class_obj, selected_date)
        
        # دریافت داده‌ها
        assessments = get_class_skill_assessments(class_obj.id, selected_date)
        skills_summary = get_skills_summary(class_obj.id, selected_date)
        
        return render_template('teacher/skills.html',
                             class_info=class_obj,
                             form=form,
                             assessments=assessments,
                             skills_summary=skills_summary,
                             students=students,
                             skills=skills,
                             selected_date=selected_date)
    
    except Exception as e:
        logger.error(f"Error in skills page: {str(e)}")
        flash('خطا در بارگذاری صفحه مهارت‌ها', 'danger')
        return redirect(url_for('teacher.dashboard'))

def handle_skill_assessment_submission(form, class_obj, selected_date):
    """پردازش ثبت ارزیابی مهارت"""
    try:
        teacher_id = current_user.teacher_profile.id
        
        assessment = SkillAssessment(
            student_id=form.student_id.data,
            skill_id=form.skill_id.data,
            class_id=class_obj.id,
            teacher_id=teacher_id,
            date=selected_date,
            level=form.level.data,
            notes=form.notes.data or None
        )
        
        db.session.add(assessment)
        db.session.commit()
        
        student = Student.query.get(form.student_id.data)
        skill = Skill.query.get(form.skill_id.data)
        
        flash(f'ارزیابی مهارت {skill.name} برای {student.full_name} با موفقیت ثبت شد', 'success')
        logger.info(f"Skill assessment recorded for {student.full_name} - {skill.name} by {current_user.username}")
        
        return redirect(url_for('teacher.skills', class_id=class_obj.id, date=selected_date))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error recording skill assessment: {str(e)}")
        flash('خطا در ثبت ارزیابی مهارت. لطفاً دوباره تلاش کنید.', 'danger')
    except Exception as e:
        logger.error(f"Unexpected error recording skill assessment: {str(e)}")
        flash('خطایی رخ داده است. لطفاً با پشتیبانی تماس بگیرید.', 'danger')
    
    return redirect(url_for('teacher.skills', class_id=class_obj.id, date=selected_date))

def get_class_skill_assessments(class_id, selected_date):
    """دریافت ارزیابی مهارت‌های کلاس برای تاریخ مشخص"""
    return SkillAssessment.query.filter_by(class_id=class_id, date=selected_date)\
        .join(Student)\
        .join(Skill)\
        .order_by(SkillAssessment.created_at.desc())\
        .all()

def get_skills_summary(class_id, selected_date):
    """دریافت خلاصه ارزیابی مهارت‌های کلاس"""
    return db.session.query(
        Skill.name,
        SkillAssessment.level,
        func.count(SkillAssessment.id).label('count')
    ).join(Skill)\
     .filter(SkillAssessment.class_id == class_id, SkillAssessment.date == selected_date)\
     .group_by(Skill.id, Skill.name, SkillAssessment.level)\
     .order_by(Skill.name, SkillAssessment.level)\
     .all()

# === API Endpoints برای عملکردهای پویا ===
@bp.route('/api/grades/<int:grade_id>/edit', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_grade(grade_id):
    """ویرایش نمره موجود"""
    grade = Grade.query.get_or_404(grade_id)
    
    # بررسی دسترسی
    if grade.teacher_id != current_user.teacher_profile.id:
        return jsonify({'error': 'دسترسی غیرمجاز'}), 403
    
    form = GradeForm()
    
    # تنظیم گزینه‌های درس‌ها
    subjects = Subject.query.filter_by(
        grade=grade.class_obj.grade,
        school_id=current_user.school_id
    ).order_by(Subject.name).all()
    form.subject_id.choices = [(subject.id, subject.name) for subject in subjects]
    
    if request.method == 'GET':
        # پر کردن فرم با داده‌های فعلی
        form.student_id.data = grade.student_id
        form.subject_id.data = grade.subject_id
        form.date.data = grade.date
        form.description.data = grade.description
        
        if current_user.school.type in ['middle', 'high']:
            form.score.data = grade.score
            form.max_score.data = grade.max_score
        else:
            form.level.data = grade.level
    
    if form.validate_on_submit():
        try:
            # به‌روزرسانی نمره
            grade.subject_id = form.subject_id.data
            grade.date = form.date.data
            grade.description = form.description.data
            
            if current_user.school.type in ['middle', 'high']:
                grade.score = form.score.data
                grade.max_score = form.max_score.data
            else:
                grade.level = form.level.data
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'نمره با موفقیت بروزرسانی شد',
                'redirect_url': url_for('teacher.grades', class_id=grade.class_id, date=grade.date.isoformat())
            })
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating grade: {str(e)}")
            return jsonify({'error': 'خطا در بروزرسانی نمره'}), 500
    
    # برای GET یا خطای اعتبارسنجی
    return render_template('teacher/edit_grade.html', form=form, grade=grade)

@bp.route('/api/attendance/toggle', methods=['POST'])
@login_required
@teacher_required
def toggle_attendance():
    """تغییر وضعیت حضور و غیاب به صورت AJAX"""
    try:
        class_id = int(request.form['class_id'])
        student_id = int(request.form['student_id'])
        date_str = request.form['date']
        new_status = request.form['status']
        
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.teacher_id != current_user.teacher_profile.id:
            return jsonify({'error': 'دسترسی غیرمجاز'}), 403
        
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # پیدا کردن یا ایجاد رکورد حضور و غیاب
        attendance = Attendance.query.filter_by(
            class_id=class_id,
            student_id=student_id,
            date=attendance_date
        ).first()
        
        if attendance:
            attendance.status = new_status
        else:
            attendance = Attendance(
                class_id=class_id,
                student_id=student_id,
                date=attendance_date,
                status=new_status,
                teacher_id=current_user.teacher_profile.id
            )
            db.session.add(attendance)
        
        db.session.commit()
        
        # ارسال SMS در صورت نیاز
        if new_status in ['absent', 'late']:
            student = Student.query.get(student_id)
            if student and student.parent_phone:
                sms_service.send_attendance_notification(
                    parent_phone=student.parent_phone,
                    student_name=student.full_name,
                    status=new_status
                )
        
        return jsonify({
            'success': True,
            'new_status': new_status,
            'status_text': get_status_text(new_status),
            'status_badge': get_status_badge(new_status)
        })
        
    except Exception as e:
        logger.error(f"Error in toggle_attendance: {str(e)}")
        return jsonify({'error': 'خطا در تغییر وضعیت حضور و غیاب'}), 500

# === گزارش‌ها و خروجی‌ها ===
@bp.route('/class/<int:class_id>/grades/export')
@login_required
@teacher_required
def export_grades(class_id):
    """خروجی اکسل نمرات کلاس"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # بررسی دسترسی
        if class_obj.teacher_id != current_user.teacher_profile.id:
            flash('شما دسترسی به این کلاس را ندارید', 'danger')
            return redirect(url_for('teacher.dashboard'))
        
        start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).isoformat())
        end_date = request.args.get('end_date', date.today().isoformat())
        
        # دریافت نمرات
        grades = Grade.query.filter(
            Grade.class_id == class_id,
            Grade.date.between(start_date, end_date)
        ).join(Student).join(Subject).order_by(Grade.date, Student.last_name).all()
        
        if not grades:
            flash('داده‌ای برای خروجی وجود ندارد', 'warning')
            return redirect(url_for('teacher.grades', class_id=class_id))
        
        # ایجاد دیتافریم
        data = []
        for grade in grades:
            row = {
                'تاریخ': grade.date.strftime('%Y/%m/%d'),
                'نام دانش‌آموز': grade.student.full_name,
                'کد دانش‌آموز': grade.student.code,
                'درس': grade.subject.name,
                'توضیحات': grade.description or ''
            }
            
            if current_user.school.type in ['middle', 'high']:
                row.update({
                    'نمره': grade.score,
                    'حداکثر': grade.max_score,
                    'درصد': f"{(grade.score / grade.max_score * 100):.1f}%" if grade.max_score > 0 else 'N/A'
                })
            else:
                row.update({
                    'سطح': get_level_text(grade.level),
                    'نمره کیفی': grade.level
                })
            
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # ایجاد فایل اکسل
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name='نمرات')
        output.seek(0)
        
        filename = f"grades_{class_obj.name}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.xlsx"
        
        return send_file(
            output,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Error exporting grades: {str(e)}")
        flash('خطا در ایجاد فایل خروجی. لطفاً دوباره تلاش کنید.', 'danger')
        return redirect(url_for('teacher.grades', class_id=class_id))

def get_level_text(level):
    """تبدیل سطح به متن فارسی"""
    levels = {
        'excellent': 'عالی',
        'very_good': 'خیلی خوب', 
        'good': 'خوب',
        'needs_effort': 'نیاز به تلاش'
    }
    return levels.get(level, level)

# === مدیریت خطا ===
@bp.app_errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 error: {request.url}")
    return render_template('errors/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    db.session.rollback()
    return render_template('errors/500.html'), 500
