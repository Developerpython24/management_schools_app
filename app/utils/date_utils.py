from datetime import datetime, timedelta
import jdatetime  # For Persian calendar support

def format_persian_date(date_obj):
    """Format date as Persian date string"""
    if not date_obj:
        return ''
    
    # Convert to Persian calendar
    jalali_date = jdatetime.date.fromgregorian(
        year=date_obj.year,
        month=date_obj.month,
        day=date_obj.day
    )
    
    return jalali_date.strftime('%Y/%m/%d')

def add_days(date_obj, days):
    """Add days to a date object"""
    return date_obj + timedelta(days=days)

def get_school_year_start():
    """Get the start date of the current school year"""
    today = datetime.now().date()
    
    # School year starts in September (month 9)
    if today.month >= 9:
        school_year_start = datetime(today.year, 9, 1).date()
    else:
        school_year_start = datetime(today.year - 1, 9, 1).date()
    
    return school_year_start
