from flask import request, current_app
from app.models import db, AuditLog, User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def log_audit_action(user_id, action, description, school_id=None, target_user_id=None, ip_address=None, user_agent=None):
    """Log an audit action with proper validation and error handling"""
    
    # ✅ بررسی پارامترهای اجباری
    if not all([isinstance(user_id, (int, str)), action, description]):
        logger.warning(f"Invalid parameters for audit log: user_id={user_id}, action={action}")
        return False
    
    # ✅ استفاده از مقادیر پیش‌فرض برای request
    if ip_address is None:
        ip_address = request.remote_addr if request else 'unknown'
    
    if user_agent is None:
        user_agent = request.user_agent.string if request else 'unknown'
    
    try:
        # ✅ بررسی وجود کاربر واقعی
        if not user_id or (isinstance(user_id, (int, str)) and str(user_id).strip() == '0'):
            logger.warning(f"Skipping audit log for invalid user ID: {user_id}")
            return False
        
        # ✅ بررسی وجود کاربر در دیتابیس
        if not User.query.get(user_id):
            logger.warning(f"Skipping audit log for non-existent user ID: {user_id}")
            return False
        
        # ✅ ایجاد رکورد لاگ
        log = AuditLog(
            user_id=user_id,
            action=action,
            description=description,
            school_id=school_id,
            target_user_id=target_user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.session.add(log)
        db.session.commit()
        
        logger.debug(f"Audit log created successfully: {action} by user {user_id}")
        return True
        
    except Exception as e:
        # ✅ رول‌بک در صورت خطا
        db.session.rollback()
        
        # ✅ لاگ دقیق خطا
        logger.error(f"Error logging audit action: {str(e)}", exc_info=True)
        
        # ✅ اطلاعات بیشتر برای دیباگ
        current_app.logger.error(f"Audit log failed details - user_id: {user_id}, action: {action}, description: {description}")
        
        return False
