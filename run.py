from app import create_app
import os
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys
from urllib.parse import url_parse

# تنظیم لاگینگ
if not os.path.exists('/opt/render/project/src/logs'):
    os.makedirs('/opt/render/project/src/logs', exist_ok=True)

# تنظیمات لاگینگ برای production
file_handler = RotatingFileHandler(
    '/opt/render/project/src/logs/app.log',
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
    # ✅ تنظیمات پورت و هاست برای Render.com
    port = int(os.environ.get('PORT', 10000))  # پورت پیش‌فرض Render.com
    host = '0.0.0.0'  # باید 0.0.0.0 باشد برای Render.com
    
    # ✅ تنظیمات ویژه برای Render.com
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['SESSION_FILE_DIR'] = '/opt/render/project/src/sessions'
        app.config['STATIC_FOLDER'] = '/opt/render/project/src/app/static'
    
    # ✅ پیام راه‌اندازی
    app.logger.info(f"Starting application in {app.config.get('FLASK_ENV', 'production')} mode")
    app.logger.info(f"Listening on {host}:{port}")
    
    # ✅ راه‌اندازی
    app.run(host=host, port=port, debug=False)
