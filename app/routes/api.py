from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.decorators import role_required
from datetime import datetime
from app.models import db, Student, Grade, Attendance, Class
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        db_status = 'connected'
    except Exception as e:
        db_status = f'disconnected: {str(e)}'
        logger.error(f"Database health check failed: {str(e)}")

    return jsonify({
        'status': 'healthy',
        'service': 'school-management-system',
        'database': db_status,
        'timestamp': datetime.now().isoformat(),
        'environment': app.config.get('FLASK_ENV', 'development')
    }), 200

@bp.route('/students/<int:student_id>/grades')
@login_required
@role_required('teacher', 'school_admin', 'super_admin')
def get_student_grades(student_id):
    """Get grades for a specific student"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Get grades with related data
        grades = Grade.query.filter_by(student_id=student_id)\
            .join(Grade.subject)\
            .join(Grade.class_obj)\
            .order_by(Grade.date.desc())\
            .limit(20)\
            .all()
        
        grades_data = [{
            'id': grade.id,
            'date': grade.date.strftime('%Y-%m-%d'),
            'subject': grade.subject.name,
            'class': grade.class_obj.name,
            'score': grade.score,
            'max_score': grade.max_score,
            'level': grade.level,
            'description': grade.description
        } for grade in grades]
        
        return jsonify({
            'success': True,
            'student': {
                'id': student.id,
                'name': student.full_name,
                'code': student.code,
                'grade': student.grade
            },
            'grades': grades_data,
            'total_grades': len(grades_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting student grades: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/classes/<int:class_id>/attendance')
@login_required
@role_required('teacher', 'school_admin', 'super_admin')
def get_class_attendance(class_id):
    """Get attendance for a specific class"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        # Get today's attendance
        today = datetime.now().date()
        attendance_records = Attendance.query.filter_by(
            class_id=class_id,
            date=today
        ).join(Attendance.student).all()
        
        attendance_data = [{
            'student_id': record.student_id,
            'student_name': record.student.full_name,
            'student_code': record.student.code,
            'status': record.status,
            'status_text': get_status_text(record.status),
            'timestamp': record.created_at.isoformat() if record.created_at else None
        } for record in attendance_records]
        
        stats = {
            'total_students': len(class_obj.students),
            'present': sum(1 for r in attendance_records if r.status == 'present'),
            'absent': sum(1 for r in attendance_records if r.status == 'absent'),
            'late': sum(1 for r in attendance_records if r.status == 'late')
        }
        
        return jsonify({
            'success': True,
            'class': {
                'id': class_obj.id,
                'name': class_obj.name,
                'grade': class_obj.grade
            },
            'date': today.isoformat(),
            'attendance': attendance_data,
            'stats': stats,
            'total_records': len(attendance_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting class attendance: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/students/search')
@login_required
@role_required('teacher', 'school_admin', 'super_admin')
def search_students():
    """Search students by name, code, or grade"""
    try:
        query = request.args.get('q', '').strip()
        grade = request.args.get('grade', '').strip()
        limit = min(int(request.args.get('limit', 20)), 50)
        
        if not query and not grade:
            return jsonify({
                'success': False,
                'error': 'Search query or grade is required'
            }), 400
        
        # Build query
        students_query = Student.query.filter_by(school_id=current_user.school_id)
        
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
        
        students = students_query.limit(limit).all()
        
        students_data = [{
            'id': student.id,
            'name': student.full_name,
            'code': student.code,
            'grade': student.grade,
            'parent_phone': student.parent_phone or 'N/A'
        } for student in students]
        
        return jsonify({
            'success': True,
            'query': query,
            'grade': grade,
            'limit': limit,
            'results': students_data,
            'total': len(students_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching students: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/error')
def trigger_error():
    """Endpoint for testing error handling (remove in production)"""
    if app.config.get('FLASK_ENV') == 'production':
        return jsonify({
            'success': False,
            'error': 'This endpoint is disabled in production'
        }), 403
    
    raise Exception("Test exception for error handling")

def get_status_text(status):
    """Convert status to Persian text"""
    status_map = {
        'absent': 'غایب',
        'late': 'با تأخیر',
        'present': 'حاضر'
    }
    return status_map.get(status, status)
