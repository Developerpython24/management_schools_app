import requests
import logging
from datetime import datetime
from config import Config
from functools import lru_cache
import re
from threading import Thread
import time

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        self.api_key = Config.SMS_API_KEY
        self.active = Config.SMS_ACTIVE
        self.provider = Config.SMS_PROVIDER.lower()
        self.sender = Config.SMS_SENDER or '10008663'
        
        # Message templates
        self.message_templates = {
            'absent': 'دانش‌آموز {student_name} در تاریخ {date} غایب بوده است.',
            'late': 'دانش‌آموز {student_name} در تاریخ {date} با تأخیر حضور پیدا کرده است.',
            'welcome': 'سلام {name}، به سیستم مدیریت مدرسه {school_name} خوش‌آمدید. نام کاربری: {username}',
            'password_reset': 'کد بازیابی رمز عبور شما: {code}'
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_interval = 1.0
        
        if not self.active:
            logger.info("SMS service is disabled (mock mode)")
        elif not self.api_key:
            logger.warning("SMS API key not configured - service will run in mock mode")
            self.active = False
    
    def _validate_phone(self, phone):
        """Validate and format phone number"""
        if not phone:
            return None
        
        # Remove non-digit characters
        phone = re.sub(r'[^\d]', '', phone)
        
        # Format for Iran
        if phone.startswith('0'):
            phone = phone[1:]
        if not phone.startswith('9'):
            phone = '9' + phone
        
        if len(phone) != 10 or not phone.startswith('9'):
            logger.warning(f"Invalid phone number format: {phone}")
            return None
        
        return phone
    
    def _get_current_date(self):
        """Get current date in Persian or Gregorian format"""
        today = datetime.now()
        return today.strftime("%Y/%m/%d")
    
    def _apply_rate_limit(self):
        """Apply rate limiting to prevent API blocking"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _send_kavenegar(self, phone, message):
        """Send SMS via Kavenegar API"""
        try:
            self._apply_rate_limit()
            
            url = f"https://api.kavenegar.com/v1/{self.api_key}/sms/send.json"
            data = {
                'receptor': phone,
                'message': message[:300],
                'sender': self.sender
            }
            
            response = requests.post(url, data=data, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('return', {}).get('status') == 200:
                logger.info(f"SMS sent successfully to {phone}")
                return True
            else:
                error_msg = result.get('return', {}).get('message', 'Unknown error')
                logger.error(f"Kavenegar API error: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in Kavenegar API: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Kavenegar API: {str(e)}")
            return False
    
    def _send_mock(self, phone, message):
        """Mock SMS sending for development"""
        logger.info(f"[MOCK SMS] To: {phone} - Message: {message}")
        print(f"📱 [MOCK SMS] To: {phone}")
        print(f"   Message: {message}")
        print(f"   Length: {len(message)} characters")
        return True
    
    def send(self, phone, message, template_type=None, **kwargs):
        """Send SMS with template support"""
        phone = self._validate_phone(phone)
        if not phone:
            logger.error("Invalid phone number - SMS not sent")
            return False
        
        # Format message using template
        if template_type and template_type in self.message_templates:
            template = self.message_templates[template_type]
            message = template.format(**kwargs, date=self._get_current_date())
        
        # Truncate long messages
        if len(message) > 300:
            message = message[:297] + "..."
            logger.warning("Message truncated to 300 characters")
        
        if not self.active:
            return self._send_mock(phone, message)
        
        if self.provider == 'kavenegar':
            return self._send_kavenegar(phone, message)
        else:
            logger.warning(f"Unsupported SMS provider: {self.provider}")
            return self._send_mock(phone, message)
    
    def send_attendance_notification(self, parent_phone, student_name, status):
        """Send attendance notification (only for absent/late)"""
        if not parent_phone or not student_name:
            logger.warning("Missing required parameters for attendance notification")
            return False
        
        if status not in ['absent', 'late']:
            logger.debug(f"No SMS needed for status: {status}")
            return False
        
        template_type = 'absent' if status == 'absent' else 'late'
        
        # Send asynchronously
        Thread(target=self._async_send_attendance, args=(parent_phone, student_name, template_type)).start()
        return True
    
    def _async_send_attendance(self, parent_phone, student_name, template_type):
        """Send attendance notification asynchronously"""
        try:
            success = self.send(
                phone=parent_phone,
                template_type=template_type,
                student_name=student_name
            )
            
            if success:
                logger.info(f"Attendance notification sent successfully for {student_name}")
            else:
                logger.error(f"Failed to send attendance notification for {student_name}")
        except Exception as e:
            logger.error(f"Error in async attendance notification: {str(e)}")

# Create global instance
sms_service = SMSService()

def get_status_text(status):
    """Convert status to Persian text"""
    status_map = {
        'absent': 'غایب',
        'late': 'با تأخیر',
        'present': 'حاضر'
    }
    return status_map.get(status, 'نامشخص')

def get_status_badge(status):
    """Get CSS class for status badge"""
    badge_classes = {
        'absent': 'badge bg-danger',
        'late': 'badge bg-warning text-dark',
        'present': 'badge bg-success'
    }
    return badge_classes.get(status, 'badge bg-secondary')

@lru_cache(maxsize=100)
def format_phone_for_display(phone):
    """Format phone number for display"""
    if not phone:
        return ''
    
    phone = re.sub(r'[^\d]', '', phone)
    if len(phone) == 10 and phone.startswith('9'):
        return f"۰{phone}"
    return phone
