from flask import request
from app.models import db, AuditLog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def log_audit_action(user_id, action, description, school_id=None, target_user_id=None):
    """Log an audit action"""
     try:
        # ✅ بررسی وجود کاربر واقعی
        if not user_id or user_id == 0:
            app.logger.warning(f"Skipping audit log for invalid user ID: {user_id}")
            return
        
        # ✅ بررسی وجود کاربر در دیتابیس
        from app.models import User
        if not User.query.get(user_id):
            app.logger.warning(f"Skipping audit log for non-existent user ID: {user_id}")
            return
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            description=description,
            school_id=school_id,
            target_user_id=target_user_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        db.session.add(log)
        db.session.commit()
        
        logger.debug(f"Audit log created: {action} by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error logging audit action: {str(e)}")
        # Don't raise exception to avoid breaking main functionality
        db.session.rollback()
