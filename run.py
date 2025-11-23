from app import create_app
import os
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys

# تنظیم لاگینگ
if not os.path.exists('logs'):
    os.mkdir('logs')

# تنظیمات لاگینگ برای production
file_handler = RotatingFileHandler(
    '/opt/render/project/src/logs/app.log' if os.environ.get('FLASK_ENV') == 'production' else 'logs/app.log',
    maxBytes=10240,
    backupCount=10
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# ایجاد اپلیکیشن
app = create_app()

# تنظیمات لاگینگ
if not app.debug:
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('School Management System startup')

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    app.logger.info('Received shutdown signal, performing cleanup...')
    sys.exit(0)

# ثبت handler برای سیگنال‌های shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    # تنظیمات پورت برای Render.com
    port = int(os.environ.get('PORT', 10000))  
    
   
    host = '0.0.0.0'
    
    # پیام راه‌اندازی
    app.logger.info(f"Starting application in {app.config.get('FLASK_ENV', 'production')} mode")
    app.logger.info(f"Listening on {host}:{port}")
    
    # راه‌اندازی
    app.run(host=host, port=port, debug=False)
