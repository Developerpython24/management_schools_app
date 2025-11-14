import sqlite3
import os
import hashlib
from flask import g
from config import Config

DATABASE_DIR = Config.DATABASE_DIR
os.makedirs(DATABASE_DIR, exist_ok=True)

def get_db_path(school_id=None):
    if school_id is None:
        return os.path.join(DATABASE_DIR, 'main.db')
    return os.path.join(DATABASE_DIR, f'school_{school_id}.db')

def get_db(school_id=None):
    db_key = f'db_{school_id}'
    if db_key not in g:
        g.db_key = sqlite3.connect(get_db_path(school_id))
        g.db_key.row_factory = sqlite3.Row
    return g.db_key

def close_db(e=None):
    for key in list(g):
        if key.startswith('db_'):
            db = g.pop(key)
            db.close()

def init_main_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT CHECK(type IN ('elementary', 'middle', 'high')) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS school_admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            school_id INTEGER,
            phone TEXT,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        );
    ''')
    
    conn.commit()
    conn.close()

def create_super_admin():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    hashed_pass = hashlib.sha256(Config.SUPER_ADMIN_PASSWORD.encode()).hexdigest()
    
    cursor.execute('''
        INSERT OR IGNORE INTO school_admins (username, password, name, school_id)
        VALUES (?, ?, ?, NULL)
    ''', (Config.SUPER_ADMIN_USERNAME, hashed_pass, 'Super Admin'))
    
    conn.commit()
    conn.close()

def init_school_db(school_id, school_type):
    conn = sqlite3.connect(get_db_path(school_id))
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            grade TEXT NOT NULL,
            parent_phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            subjects TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            UNIQUE(name, grade)
        );
        
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            teacher_id INTEGER,
            room TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        
        CREATE TABLE IF NOT EXISTS class_students (
            class_id INTEGER,
            student_id INTEGER,
            PRIMARY KEY (class_id, student_id),
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER,
            student_id INTEGER,
            date DATE NOT NULL,
            status TEXT CHECK(status IN ('present', 'absent', 'late')) NOT NULL,
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
        
        CREATE TABLE IF NOT EXISTS discipline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            teacher_id INTEGER,
            class_id INTEGER,
            date DATE NOT NULL,
            type TEXT CHECK(type IN ('positive', 'negative')) NOT NULL,
            points INTEGER,
            description TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id),
            FOREIGN KEY (class_id) REFERENCES classes(id)
        );
    ''')
    
    if school_type in ['middle', 'high']:
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                subject_id INTEGER,
                class_id INTEGER,
                teacher_id INTEGER,
                date DATE NOT NULL,
                score REAL,
                max_score REAL DEFAULT 20,
                description TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (teacher_id) REFERENCES teachers(id)
            );
        ''')
    else:
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                subject_id INTEGER,
                class_id INTEGER,
                teacher_id INTEGER,
                date DATE NOT NULL,
                level TEXT CHECK(level IN ('excellent', 'very_good', 'good', 'needs_effort')) NOT NULL,
                description TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (teacher_id) REFERENCES teachers(id)
            );
        ''')
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS skill_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            skill_id INTEGER,
            class_id INTEGER,
            teacher_id INTEGER,
            date DATE NOT NULL,
            level TEXT CHECK(level IN ('excellent', 'very_good', 'good', 'needs_effort')) NOT NULL,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (skill_id) REFERENCES skills(id),
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        
        INSERT OR IGNORE INTO skills (name) VALUES 
            ('شنوایی'), ('نوشتاری'), ('حل مسئله'), ('گفتاری'),
            ('ارتباطی'), ('فنی'), ('خلاقیت'), ('کار گروهی');
    ''')
    
    conn.commit()
    conn.close()