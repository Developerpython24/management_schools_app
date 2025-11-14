import requests
from config import Config

class SMSService:
    def __init__(self):
        self.api_key = Config.SMS_API_KEY
        self.active = Config.SMS_ACTIVE
    
    def send(self, phone, message):
        """Send SMS using Kavenegar API"""
        if not self.active:
            print(f"[MOCK SMS] To: {phone} - Message: {message}")
            return True
        
        if not self.api_key:
            print("SMS API Key not configured!")
            return False
        
        try:
            url = f"https://api.kavenegar.com/v1/{self.api_key}/sms/send.json"
            data = {
                'receptor': phone,
                'message': message
            }
            response = requests.post(url, data=data, timeout=10)
            result = response.json()
            
            if result['return']['status'] == 200:
                print(f"SMS sent successfully to {phone}")
                return True
            else:
                print(f"SMS failed: {result['return']['message']}")
                return False
        except Exception as e:
            print(f"SMS Error: {e}")
            return False

sms_service = SMSService()

def get_status_text(status):
    return {
        'absent': 'غایب',
        'late': 'با تاخیر',
        'present': 'حاضر'
    }.get(status, 'نامشخص')