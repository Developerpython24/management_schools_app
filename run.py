from app import create_app
import os
import logging
from logging.handlers import RotatingFileHandler

# تنظیم لاگینگ
if not os.path.exists('logs'):
    os.mkdir('logs')

# تنظیم لاگینگ برای production
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
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

if __name__ == '__main__':
    # تنظیمات پورت برای render.com
    port = int(os.environ.get('PORT', 5000))
    
    # تنظیمات میزبان
    host = '0.0.0.0'
    
    # پیام راه‌اندازی
    app.logger.info(f"Starting application in {app.config.get('FLASK_ENV', 'production')} mode")
    app.logger.info(f"Listening on {host}:{port}")
    
    # راه‌اندازی
    app.run(host=host, port=port, debug=False)
