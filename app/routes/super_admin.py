from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models import get_db, init_school_db
from app.sms_service import sms_service
import hashlib

bp = Blueprint('super_admin', __name__)

def super_admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('username') != 'superadmin':
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@super_admin_required
def dashboard():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM schools')
    schools = cursor.fetchall()
    return render_template('super_admin/dashboard.html', schools=schools)

@bp.route('/schools', methods=['GET', 'POST'])
@super_admin_required
def schools():
    db = get_db()
    cursor = db.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        school_type = request.form['type']
        
        cursor.execute('INSERT INTO schools (name, type) VALUES (?, ?)', 
                       (name, school_type))
        school_id = cursor.lastrowid
        
        init_school_db(school_id, school_type)
        
        flash(f'مدرسه "{name}" با موفقیت ایجاد شد', 'success')
        return redirect(url_for('super_admin.schools'))
    
    cursor.execute('SELECT * FROM schools ORDER BY id DESC')
    schools = cursor.fetchall()
    return render_template('super_admin/schools.html', schools=schools)

@bp.route('/admins', methods=['GET', 'POST'])
@super_admin_required
def admins():
    db = get_db()
    cursor = db.cursor()
    
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        name = request.form['name']
        school_id = request.form['school_id']
        phone = request.form['phone']
        
        cursor.execute('''
            INSERT INTO school_admins (username, password, name, school_id, phone)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password, name, school_id, phone))
        
        flash(f'مدیر "{name}" با موفقیت اضافه شد', 'success')
        return redirect(url_for('super_admin.admins'))
    
    cursor.execute('''
        SELECT a.*, s.name as school_name, s.type as school_type
        FROM school_admins a
        LEFT JOIN schools s ON a.school_id = s.id
        ORDER BY a.id DESC
    ''')
    admins = cursor.fetchall()
    
    cursor.execute('SELECT * FROM schools')
    schools = cursor.fetchall()
    return render_template('super_admin/admins.html', admins=admins, schools=schools)

@bp.route('/impersonate/<int:admin_id>')
@super_admin_required
def impersonate(admin_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM school_admins WHERE id = ?', (admin_id,))
    admin = cursor.fetchone()
    
    if admin:
        session['original_user'] = session['user_id']
        session['user_id'] = admin['id']
        session['username'] = admin['username']
        session['role'] = 'school_admin'
        session['school_id'] = admin['school_id']
        flash(f'شما اکنون به عنوان مدیر {admin["name"]} وارد شده‌اید', 'info')
        return redirect(url_for('school_admin.dashboard'))
    
    flash('مدیر یافت نشد', 'error')
    return redirect(url_for('super_admin.admins'))
