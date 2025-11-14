from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..models import get_db
from ..sms_service import sms_service, get_status_text
from datetime import date, datetime

bp = Blueprint('teacher', __name__)

def teacher_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['super_admin', 'teacher']:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@teacher_required
def dashboard():
    school_id = session['school_id']
    teacher_id = session['teacher_id']
    db = get_db(school_id)
    
    classes = db.execute('''
        SELECT c.*, COUNT(cs.student_id) as student_count
        FROM classes c
        LEFT JOIN class_students cs ON c.id = cs.class_id
        WHERE c.teacher_id = ?
        GROUP BY c.id
    ''', (teacher_id,)).fetchall()
    
    return render_template('teacher/dashboard.html', classes=classes)

@bp.route('/class/<int:class_id>/grades', methods=['GET', 'POST'])
@teacher_required
def grades(class_id):
    school_id = session['school_id']
    teacher_id = session['teacher_id']
    db = get_db(school_id)
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    # Verify ownership
    class_info = db.execute(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?', 
        (class_id, teacher_id)
    ).fetchone()
    if not class_info:
        from flask import abort
        abort(403)
    
    if request.method == 'POST':
        student_id = request.form['student_id']
        subject_id = request.form['subject_id']
        
        school_type = get_db().execute(
            'SELECT type FROM schools WHERE id = ?', (school_id,)
        ).fetchone()['type']
        
        if school_type == 'elementary':
            level = request.form['level']
            db.execute('''
                INSERT INTO grades (student_id, subject_id, class_id, teacher_id, date, level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, subject_id, class_id, teacher_id, selected_date, level))
        else:
            score = request.form['score']
            max_score = request.form.get('max_score', 20)
            db.execute('''
                INSERT INTO grades (student_id, subject_id, class_id, teacher_id, date, score, max_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, subject_id, class_id, teacher_id, selected_date, score, max_score))
        
        db.commit()
        flash('نمره ثبت شد', 'success')
        return redirect(url_for('teacher.grades', class_id=class_id, date=selected_date))
    
    students = db.execute('''
        SELECT s.* FROM students s
        JOIN class_students cs ON s.id = cs.student_id
        WHERE cs.class_id = ?
        ORDER BY s.last_name, s.first_name
    ''', (class_id,)).fetchall()
    
    subjects = db.execute(
        'SELECT * FROM subjects WHERE grade = ?', 
        (class_info['grade'],)
    ).fetchall()
    
    grades_list = db.execute('''
        SELECT g.*, s.first_name, s.last_name, sub.name as subject_name
        FROM grades g
        JOIN students s ON g.student_id = s.id
        JOIN subjects sub ON g.subject_id = sub.id
        WHERE g.class_id = ? AND g.date = ?
    ''', (class_id, selected_date)).fetchall()
    
    return render_template('teacher/grades.html', class_info=class_info,
                         students=students, subjects=subjects, 
                         grades=grades_list, selected_date=selected_date)

@bp.route('/class/<int:class_id>/attendance', methods=['GET', 'POST'])
@teacher_required
def attendance(class_id):
    school_id = session['school_id']
    teacher_id = session['teacher_id']
    db = get_db(school_id)
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    class_info = db.execute(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?', 
        (class_id, teacher_id)
    ).fetchone()
    if not class_info:
        from flask import abort
        abort(403)
    
    if request.method == 'POST':
        db.execute('DELETE FROM attendance WHERE class_id = ? AND date = ?',
                   (class_id, selected_date))
        
        for key, status in request.form.items():
            if key.startswith('status_'):
                student_id = key.replace('status_', '')
                db.execute('''
                    INSERT INTO attendance (class_id, student_id, date, status)
                    VALUES (?, ?, ?, ?)
                ''', (class_id, student_id, selected_date, status))
                
                if status in ['absent', 'late']:
                    phone = db.execute(
                        'SELECT parent_phone FROM students WHERE id = ?', 
                        (student_id,)
                    ).fetchone()['parent_phone']
                    
                    message = f"دانش‌آموز شما در تاریخ {selected_date} {get_status_text(status)} بوده است."
                    sms_service.send(phone, message)
        
        db.commit()
        flash('حضور/غیاب ثبت شد', 'success')
        return redirect(url_for('teacher.attendance', class_id=class_id, date=selected_date))
    
    students = db.execute('''
        SELECT s.* FROM students s
        JOIN class_students cs ON s.id = cs.student_id
        WHERE cs.class_id = ?
        ORDER BY s.last_name, s.first_name
    ''', (class_id,)).fetchall()
    
    attendance_data = {
        a['student_id']: a['status'] 
        for a in db.execute(
            'SELECT student_id, status FROM attendance WHERE class_id = ? AND date = ?',
            (class_id, selected_date)
        ).fetchall()
    }
    
    return render_template('teacher/attendance.html', class_info=class_info,
                         students=students, attendance=attendance_data,
                         selected_date=selected_date)

@bp.route('/class/<int:class_id>/discipline', methods=['GET', 'POST'])
@teacher_required
def discipline(class_id):
    school_id = session['school_id']
    teacher_id = session['teacher_id']
    db = get_db(school_id)
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    class_info = db.execute(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?', 
        (class_id, teacher_id)
    ).fetchone()
    if not class_info:
        from flask import abort
        abort(403)
    
    if request.method == 'POST':
        student_id = request.form['student_id']
        d_type = request.form['type']
        points = request.form['points']
        description = request.form['description']
        
        db.execute('''
            INSERT INTO discipline (student_id, teacher_id, class_id, date, type, points, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, teacher_id, class_id, selected_date, d_type, points, description))
        db.commit()
        flash('نمره انضباط ثبت شد', 'success')
        return redirect(url_for('teacher.discipline', class_id=class_id, date=selected_date))
    
    students = db.execute('''
        SELECT s.* FROM students s
        JOIN class_students cs ON s.id = cs.student_id
        WHERE cs.class_id = ?
        ORDER BY s.last_name, s.first_name
    ''', (class_id,)).fetchall()
    
    discipline_list = db.execute('''
        SELECT d.*, s.first_name, s.last_name
        FROM discipline d
        JOIN students s ON d.student_id = s.id
        WHERE d.class_id = ? AND d.date = ?
        ORDER BY d.id DESC
    ''', (class_id, selected_date)).fetchall()
    
    return render_template('teacher/discipline.html', class_info=class_info,
                         students=students, discipline=discipline_list,
                         selected_date=selected_date)

@bp.route('/class/<int:class_id>/skills', methods=['GET', 'POST'])
@teacher_required
def skills(class_id):
    school_id = session['school_id']
    teacher_id = session['teacher_id']
    db = get_db(school_id)
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    class_info = db.execute(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?', 
        (class_id, teacher_id)
    ).fetchone()
    if not class_info:
        from flask import abort
        abort(403)
    
    if request.method == 'POST':
        student_id = request.form['student_id']
        skill_id = request.form['skill_id']
        level = request.form['level']
        notes = request.form['notes']
        
        db.execute('''
            INSERT INTO skill_assessments (student_id, skill_id, class_id, teacher_id, date, level, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, skill_id, class_id, teacher_id, selected_date, level, notes))
        db.commit()
        flash('ارزیابی مهارت ثبت شد', 'success')
        return redirect(url_for('teacher.skills', class_id=class_id, date=selected_date))
    
    students = db.execute('''
        SELECT s.* FROM students s
        JOIN class_students cs ON s.id = cs.student_id
        WHERE cs.class_id = ?
        ORDER BY s.last_name, s.first_name
    ''', (class_id,)).fetchall()
    
    skills_list = db.execute('SELECT * FROM skills').fetchall()
    
    assessments = db.execute('''
        SELECT sa.*, s.first_name, s.last_name, sk.name as skill_name
        FROM skill_assessments sa
        JOIN students s ON sa.student_id = s.id
        JOIN skills sk ON sa.skill_id = sk.id
        WHERE sa.class_id = ? AND sa.date = ?
        ORDER BY sa.id DESC
    ''', (class_id, selected_date)).fetchall()
    
    return render_template('teacher/skills.html', class_info=class_info,
                         students=students, skills=skills_list,
                         assessments=assessments, selected_date=selected_date)