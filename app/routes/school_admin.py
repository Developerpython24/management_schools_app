from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from app.models import get_db, get_db_path
import pandas as pd
import hashlib
import sqlite3
from datetime import date
import io

bp = Blueprint('school_admin', __name__)

def school_admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['super_admin', 'school_admin']:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@school_admin_required
def dashboard():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    stats = {
        'students': cursor.execute('SELECT COUNT(*) as c FROM students').fetchone()['c'],
        'teachers': cursor.execute('SELECT COUNT(*) as c FROM teachers').fetchone()['c'],
        'classes': cursor.execute('SELECT COUNT(*) as c FROM classes').fetchone()['c'],
        'today_attendance': cursor.execute(
            'SELECT COUNT(*) as c FROM attendance WHERE date = ?', 
            (date.today(),)
        ).fetchone()['c']
    }
    
    return render_template('school_admin/dashboard.html', stats=stats)

@bp.route('/settings', methods=['GET', 'POST'])
@school_admin_required
def settings():
    school_id = session['school_id']
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM schools WHERE id = ?', (school_id,))
    school = cursor.fetchone()
    
    if request.method == 'POST':
        school_name = request.form['school_name']
        admin_name = request.form['admin_name']
        phone = request.form['phone']
        new_pass = request.form.get('new_password')
        
        cursor.execute('UPDATE schools SET name = ? WHERE id = ?', 
                       (school_name, school_id))
        
        updates = []
        values = []
        if admin_name:
            updates.append("name = ?")
            values.append(admin_name)
        if phone:
            updates.append("phone = ?")
            values.append(phone)
        if new_pass:
            updates.append("password = ?")
            values.append(hashlib.sha256(new_pass.encode()).hexdigest())
        
        if updates:
            values.append(session['user_id'])
            cursor.execute(
                f'UPDATE school_admins SET {", ".join(updates)} WHERE id = ?', 
                values
            )
        
        db.commit()
        flash('تنظیمات با موفقیت بروزرسانی شد', 'success')
        return redirect(url_for('school_admin.settings'))
    
    cursor.execute('SELECT * FROM school_admins WHERE id = ?', (session['user_id'],))
    admin = cursor.fetchone()
    return render_template('school_admin/settings.html', school=school, admin=admin)

@bp.route('/students', methods=['GET', 'POST'])
@school_admin_required
def students():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    if request.method == 'POST':
        if 'excel_file' in request.files:
            file = request.files['excel_file']
            if file and file.filename.endswith('.xlsx'):
                df = pd.read_excel(file)
                for _, row in df.iterrows():
                    cursor.execute('''
                        INSERT OR IGNORE INTO students (code, first_name, last_name, grade, parent_phone)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (str(row.get('کد', '')), row.get('نام', ''), row.get('نام خانوادگی', ''),
                          row.get('پایه', ''), row.get('شماره والدین', '')))
                db.commit()
                flash(f'{len(df)} دانش‌آموز از اکسل اضافه شد', 'success')
        else:
            code = request.form['code']
            fname = request.form['first_name']
            lname = request.form['last_name']
            grade = request.form['grade']
            phone = request.form['parent_phone']
            
            cursor.execute('''
                INSERT INTO students (code, first_name, last_name, grade, parent_phone)
                VALUES (?, ?, ?, ?, ?)
            ''', (code, fname, lname, grade, phone))
            db.commit()
            flash('دانش‌آموز اضافه شد', 'success')
    
    cursor.execute('SELECT * FROM students ORDER BY grade, last_name')
    students_list = cursor.fetchall()
    return render_template('school_admin/students.html', students=students_list)

@bp.route('/students/delete/<int:student_id>')
@school_admin_required
def delete_student(student_id):
    db = get_db(session['school_id'])
    cursor = db.cursor()
    cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
    db.commit()
    flash('دانش‌آموز حذف شد', 'info')
    return redirect(url_for('school_admin.students'))

@bp.route('/teachers', methods=['GET', 'POST'])
@school_admin_required
def teachers():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        name = request.form['name']
        phone = request.form['phone']
        subjects = ','.join(request.form.getlist('subjects'))
        
        cursor.execute('''
            INSERT INTO teachers (username, password, name, phone, subjects)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password, name, phone, subjects))
        db.commit()
        flash('معلم اضافه شد', 'success')
        return redirect(url_for('school_admin.teachers'))
    
    teachers_list = cursor.execute('SELECT * FROM teachers').fetchall()
    subjects = cursor.execute('SELECT * FROM subjects').fetchall()
    return render_template('school_admin/teachers.html', teachers=teachers_list, subjects=subjects)

@bp.route('/subjects', methods=['GET', 'POST'])
@school_admin_required
def subjects():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        grade = request.form['grade']
        cursor.execute('INSERT OR IGNORE INTO subjects (name, grade) VALUES (?, ?)',
                       (name, grade))
        db.commit()
        flash('درس اضافه شد', 'success')
        return redirect(url_for('school_admin.subjects'))
    
    subjects_list = cursor.execute('SELECT * FROM subjects ORDER BY grade, name').fetchall()
    grades = [g[0] for g in cursor.execute('SELECT DISTINCT grade FROM students').fetchall()]
    return render_template('school_admin/subjects.html', subjects=subjects_list, grades=grades)

@bp.route('/classes', methods=['GET', 'POST'])
@school_admin_required
def classes():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        grade = request.form['grade']
        teacher_id = request.form.get('teacher_id')
        room = request.form.get('room')
        
        cursor.execute('''
            INSERT INTO classes (name, grade, teacher_id, room)
            VALUES (?, ?, ?, ?)
        ''', (name, grade, teacher_id or None, room))
        db.commit()
        flash('کلاس اضافه شد', 'success')
        return redirect(url_for('school_admin.classes'))
    
    classes_list = cursor.execute('''
        SELECT c.*, t.name as teacher_name 
        FROM classes c 
        LEFT JOIN teachers t ON c.teacher_id = t.id
        ORDER BY c.grade, c.name
    ''').fetchall()
    teachers = cursor.execute('SELECT * FROM teachers').fetchall()
    return render_template('school_admin/classes.html', classes=classes_list, teachers=teachers)

@bp.route('/classes/<int:class_id>/assign', methods=['GET', 'POST'])
@school_admin_required
def assign_students(class_id):
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    if request.method == 'POST':
        cursor.execute('DELETE FROM class_students WHERE class_id = ?', (class_id,))
        for student_id in request.form.getlist('students'):
            cursor.execute('INSERT INTO class_students VALUES (?, ?)',
                           (class_id, student_id))
        db.commit()
        flash('دانش‌آموزان اختصاص داده شدند', 'success')
        return redirect(url_for('school_admin.classes'))
    
    class_info = cursor.execute('SELECT * FROM classes WHERE id = ?', (class_id,)).fetchone()
    students = cursor.execute('SELECT * FROM students WHERE grade = ?', 
                              (class_info['grade'],)).fetchall()
    assigned = [s[0] for s in cursor.execute(
        'SELECT student_id FROM class_students WHERE class_id = ?', (class_id,)
    ).fetchall()]
    return render_template('school_admin/assign_students.html',
                         class_info=class_info, students=students, assigned=assigned)

@bp.route('/discipline')
@school_admin_required
def discipline():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    records = cursor.execute('''
        SELECT d.*, s.first_name, s.last_name, t.name as teacher_name, c.name as class_name
        FROM discipline d
        JOIN students s ON d.student_id = s.id
        JOIN teachers t ON d.teacher_id = t.id
        JOIN classes c ON d.class_id = c.id
        WHERE d.date = ?
        ORDER BY d.id DESC
    ''', (selected_date,)).fetchall()
    
    return render_template('school_admin/discipline.html', records=records, 
                         selected_date=selected_date)

@bp.route('/attendance')
@school_admin_required
def attendance():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    records = cursor.execute('''
        SELECT a.*, s.first_name, s.last_name, c.name as class_name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN classes c ON a.class_id = c.id
        WHERE a.date = ?
        ORDER BY c.name, s.last_name
    ''', (selected_date,)).fetchall()
    
    return render_template('school_admin/attendance.html', 
                         records=records, selected_date=selected_date)

@bp.route('/reports', methods=['GET', 'POST'])
@school_admin_required
def reports():
    school_id = session['school_id']
    db = get_db(school_id)
    cursor = db.cursor()
    
    if request.method == 'POST':
        report_type = request.form['report_type']
        
        if report_type == 'student':
            student_id = request.form['student_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            
            student = cursor.execute('SELECT * FROM students WHERE id = ?', 
                                   (student_id,)).fetchone()
            
            grades = cursor.execute('''
                SELECT g.*, s.name as subject_name, c.name as class_name
                FROM grades g
                JOIN subjects s ON g.subject_id = s.id
                JOIN classes c ON g.class_id = c.id
                WHERE g.student_id = ? AND g.date BETWEEN ? AND ?
            ''', (student_id, start_date, end_date)).fetchall()
            
            # Export to Excel
            df = pd.DataFrame([dict(g) for g in grades])
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            
            return send_file(output, download_name='report.xlsx', 
                           as_attachment=True)
    
    students = cursor.execute('SELECT * FROM students ORDER BY last_name').fetchall()
    classes = cursor.execute('SELECT * FROM classes ORDER BY name').fetchall()
    return render_template('school_admin/reports.html', students=students, classes=classes)
