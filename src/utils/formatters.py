from datetime import datetime, timedelta
from src.config.config import APPOINTMENT_DURATION_MINUTES

def format_wait_time(minutes: int) -> str:
    """Format wait time in Algerian dialect"""
    if minutes == 0:
        return "ما كان والو"
    elif minutes < 60:
        if minutes == 1:
            return "دقيقة"
        elif minutes == 2:
            return "دقيقتين"
        else:
            return f"{minutes} دقايق"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    hours_text = ""
    if hours == 1:
        hours_text = "ساعة"
    elif hours == 2:
        hours_text = "ساعتين"
    else:
        hours_text = f"{hours} سوايع"
    
    if remaining_minutes == 0:
        return hours_text
    elif remaining_minutes == 1:
        return f"{hours_text} و دقيقة"
    elif remaining_minutes == 2:
        return f"{hours_text} و دقيقتين"
    else:
        return f"{hours_text} و {remaining_minutes} دقايق"

def get_estimated_completion_time(wait_minutes: int) -> str:
    """Calculate the estimated completion time in Algerian format"""
    current_time = datetime.now()
    completion_time = current_time.replace(microsecond=0) + timedelta(minutes=wait_minutes)
    hour = completion_time.hour
    minute = completion_time.minute
    
    # Format time in Algerian style
    if hour < 12:
        period = "صباح"
        if hour == 0:
            hour = 12
    else:
        period = "مساء"
        if hour > 12:
            hour = hour - 12
    
    return f"{hour}:{minute:02d} {period}" 