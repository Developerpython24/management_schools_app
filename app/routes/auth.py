from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..models import get_db, get_db_path
from config import Config  # ✅ اضافه کنید
import hashlib
from functools import wraps

bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'super_admin':
            return redirect(url_for('super_admin.dashboard'))
        elif session.get('role') == 'school_admin':
            return redirect(url_for('school_admin.dashboard'))
        elif session.get('role') == 'teacher':
            return redirect(url_for('teacher.dashboard'))
    return redirect(url_for('auth.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        
        # ✅ اصلاح این بخش
        if username == Config.SUPER_ADMIN_USERNAME:
            # رمز را از Config می‌خوانیم که از Environment Variables می‌آید
            if password == Config.SUPER_ADMIN_PASSWORD:
                session['user_id'] = 0
                session['username'] = Config.SUPER_ADMIN_USERNAME
                session['role'] = 'super_admin'
                session['school_id'] = None
                flash('ورود Super Admin با موفقیت', 'success')
                return redirect(url_for('super_admin.dashboard'))
        
        # بقیه کد بدون تغییر...
        # School admin check
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM school_admins WHERE username = ?', (username,))
        admin = cursor.fetchone()
        
        if admin and admin['password'] == hashed_pass:
            session['user_id'] = admin['id']
            session['username'] = admin['username']
            session['role'] = 'school_admin'
            session['school_id'] = admin['school_id']
            flash('ورود مدیر مدرسه با موفقیت', 'success')
            return redirect(url_for('school_admin.dashboard'))
        
        # Teacher check
        schools = cursor.execute('SELECT id FROM schools').fetchall()
        for school in schools:
            school_id = school['id']
            try:
                school_db = get_db(school_id)
                school_cursor = school_db.cursor()
                school_cursor.execute('SELECT * FROM teachers WHERE username = ?', (username,))
                teacher = school_cursor.fetchone()
                
                if teacher and teacher['password'] == hashed_pass:
                    session['user_id'] = teacher['id']
                    session['username'] = teacher['username']
                    session['role'] = 'teacher'
                    session['school_id'] = school_id
                    session['teacher_id'] = teacher['id']
                    flash('ورود معلم با موفقیت', 'success')
                    return redirect(url_for('teacher.dashboard'))
            except:
                continue
        
        flash('نام کاربری یا رمز عبور اشتباه است', 'error')
    
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    flash('خروج با موفقیت', 'info')
    return redirect(url_for('auth.login'))
