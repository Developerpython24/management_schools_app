from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import logging
from app import db
from config import Config
from flask_login import UserMixin  

logger = logging.getLogger(__name__)

class School(db.Model):
    __tablename__ = 'schools'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # elementary, middle, high, combined
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Relationships
    users = db.relationship('User', backref='school', lazy=True, foreign_keys='User.school_id')
    students = db.relationship('Student', backref='school', lazy=True)
    teachers = db.relationship('Teacher', backref='school', lazy=True)
    classes = db.relationship('Class', backref='school', lazy=True)
    subjects = db.relationship('Subject', backref='school', lazy=True)
    skills = db.relationship('Skill', backref='school', lazy=True)
    
    __table_args__ = (
        db.Index('ix_schools_name', 'name'),
        db.Index('ix_schools_type', 'type'),
    )
    
    @property
    def type_fa(self):
        """Get Persian name for school type"""
        return Config.SCHOOL_TYPES.get(self.type, self.type)
    
    def __repr__(self):
        return f'<School {self.name}>'


class User(db.Model, UserMixin):  # ✅ ارث‌بری از UserMixin
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # super_admin, school_admin, teacher
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100), unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    #last_login = db.Column(db.DateTime)
    
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    
    # Relationships
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('ix_users_username', 'username'),
        db.Index('ix_users_role', 'role'),
        db.Index('ix_users_school_id', 'school_id'),
    )
    
    def set_password(self, password):
        """Hash and set password"""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    @property
    def is_school_admin(self):
        return self.role == 'school_admin'
    
    @property
    def is_teacher(self):
        return self.role == 'teacher'
    
    #  تابع get_id برای Flask-Login
    def get_id(self):
        """Return the user ID as a string for Flask-Login"""
        return str(self.id)
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    parent_phone = db.Column(db.String(20))
    parent_email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    
    # Relationships
    classes = db.relationship('Class', secondary='class_students', backref='students')
    attendances = db.relationship('Attendance', backref='student', lazy=True, cascade='all, delete-orphan')
    discipline_records = db.relationship('Discipline', backref='student', lazy=True, cascade='all, delete-orphan')
    grades = db.relationship('Grade', backref='student', lazy=True, cascade='all, delete-orphan')
    skill_assessments = db.relationship('SkillAssessment', backref='student', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('ix_students_code', 'code'),
        db.Index('ix_students_school_id', 'school_id'),
        db.Index('ix_students_grade', 'grade'),
    )
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<Student {self.full_name} ({self.code})>'

class Teacher(db.Model):
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    subjects = db.Column(db.Text)  # JSON string or comma-separated
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    
    # Relationships
    classes = db.relationship('Class', backref='teacher', lazy=True)
    subjects_taught = db.relationship('Subject', backref='teacher', lazy=True)
    
    __table_args__ = (
        db.Index('ix_teachers_school_id', 'school_id'),
        db.Index('ix_teachers_user_id', 'user_id'),
    )
    
    @property
    def name(self):
        return self.user.name if self.user else ''
    
    @property
    def username(self):
        return self.user.username if self.user else ''
    
    def __repr__(self):
        return f'<Teacher {self.name}>'

class Subject(db.Model):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    
    # Relationships
    grades = db.relationship('Grade', backref='subject', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('name', 'grade', 'school_id', name='uix_subject_grade_school'),
        db.Index('ix_subjects_school_id', 'school_id'),
        db.Index('ix_subjects_grade', 'grade'),
    )
    
    def __repr__(self):
        return f'<Subject {self.name} ({self.grade})>'

class Class(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    room = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    
    # Relationships
    attendances = db.relationship('Attendance', backref='class_obj', lazy=True, cascade='all, delete-orphan')
    discipline_records = db.relationship('Discipline', backref='class_obj', lazy=True, cascade='all, delete-orphan')
    grades = db.relationship('Grade', backref='class_obj', lazy=True, cascade='all, delete-orphan')
    skill_assessments = db.relationship('SkillAssessment', backref='class_obj', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('ix_classes_school_id', 'school_id'),
        db.Index('ix_classes_grade', 'grade'),
        db.Index('ix_classes_teacher_id', 'teacher_id'),
    )
    
    def __repr__(self):
        return f'<Class {self.name} ({self.grade})>'

# Association table for class-student many-to-many relationship
class_students = db.Table('class_students',
    db.Column('class_id', db.Integer, db.ForeignKey('classes.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True)
)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # present, absent, late
    
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    __table_args__ = (
        db.UniqueConstraint('class_id', 'student_id', 'date', name='uix_attendance_class_student_date'),
        db.Index('ix_attendance_date', 'date'),
        db.Index('ix_attendance_status', 'status'),
    )
    
    def __repr__(self):
        return f'<Attendance {self.student_id} - {self.status} on {self.date}>'

class Discipline(db.Model):
    __tablename__ = 'discipline'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # positive, negative
    points = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=False)
    
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    __table_args__ = (
        db.Index('ix_discipline_date', 'date'),
        db.Index('ix_discipline_type', 'type'),
    )
    
    def __repr__(self):
        return f'<Discipline {self.type} for student {self.student_id}>'

class Grade(db.Model):
    __tablename__ = 'grades'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # For middle/high school: numeric scores
    score = db.Column(db.Float)
    max_score = db.Column(db.Float, default=20.0)
    
    # For elementary school: qualitative levels
    level = db.Column(db.String(20))  # excellent, very_good, good, needs_effort
    
    school_type = db.Column(db.String(20), nullable=False)  # elementary, middle, high
    
    __table_args__ = (
        db.Index('ix_grades_date', 'date'),
        db.Index('ix_grades_student_id', 'student_id'),
        db.Index('ix_grades_class_id', 'class_id'),
    )
    
    def __repr__(self):
        return f'<Grade for student {self.student_id} on {self.date}>'

class Skill(db.Model):
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(20))  # academic, social, technical
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    
    __table_args__ = (
        db.Index('ix_skills_school_id', 'school_id'),
    )
    
    def __repr__(self):
        return f'<Skill {self.name}>'

class SkillAssessment(db.Model):
    __tablename__ = 'skill_assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today, nullable=False)
    level = db.Column(db.String(20), nullable=False)  # excellent, very_good, good, needs_effort
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    __table_args__ = (
        db.Index('ix_skill_assessments_date', 'date'),
        db.Index('ix_skill_assessments_student_id', 'student_id'),
    )
    
    def __repr__(self):
        return f'<SkillAssessment {self.skill_id} for student {self.student_id}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='audit_logs')
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref='targeted_audit_logs')
    school = db.relationship('School', backref='audit_logs')
    
    __table_args__ = (
        db.Index('ix_audit_logs_timestamp', 'timestamp'),
        db.Index('ix_audit_logs_action', 'action'),
    )
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_id}>'

def init_database(app):
    """Initialize database with tables and default data"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            app.logger.info("Database tables created successfully")
            
            # Create Super Admin if not exists
            create_super_admin(app)
            
            # Create default skills
            create_default_skills(app)
            
        except Exception as e:
            app.logger.error(f"Database initialization failed: {str(e)}")
            raise

def create_super_admin(app):
    """Create Super Admin user if not exists"""
    from app.models import User
    
    super_admin = User.query.filter_by(username=Config.SUPER_ADMIN_USERNAME).first()
    
    if not super_admin:
        super_admin = User(
            username=Config.SUPER_ADMIN_USERNAME,
            name='Super Admin',
            role='super_admin',
            phone='09120000000',
            email='superadmin@example.com',
            is_active=True
        )
        super_admin.set_password(Config.SUPER_ADMIN_PASSWORD)
        
        db.session.add(super_admin)
        db.session.commit()
        app.logger.info(f"✅ Super Admin account created with ID: {super_admin.id}")
        return True
    
    app.logger.info(f"✅ Super Admin account verified with ID: {super_admin.id}")
    return False

def create_default_skills(app):
    """Create default skills for all schools"""
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
    
    from app.models import School, Skill
    
    schools = School.query.all()
    for school in schools:
        for skill_data in default_skills:
            existing_skill = Skill.query.filter_by(
                name=skill_data['name'],
                school_id=school.id
            ).first()
            
            if not existing_skill:
                skill = Skill(
                    name=skill_data['name'],
                    category=skill_data['category'],
                    school_id=school.id
                )
                db.session.add(skill)
    
    db.session.commit()
    app.logger.info("Default skills created for all schools")
