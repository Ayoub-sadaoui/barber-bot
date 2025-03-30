import re

def is_valid_phone(phone):
    """Check if phone number matches Algerian format (e.g., 0677366125)"""
    # Remove any spaces or special characters from the input
    phone = phone.strip().replace(' ', '').replace('-', '')
    phone_pattern = re.compile(r'^0[567]\d{8}$')
    return bool(phone_pattern.match(phone))

def is_valid_name(name):
    """Check if name contains only letters and spaces, and is between 3 and 30 characters"""
    name_pattern = re.compile(r'^[A-Za-z\s]{3,30}$')
    return bool(name_pattern.match(name)) 