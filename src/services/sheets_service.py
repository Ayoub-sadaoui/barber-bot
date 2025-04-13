import os
import json
import logging
from datetime import datetime, timedelta
import time
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from src.config.config import SCOPE, GOOGLE_CREDS_JSON
from typing import List, Dict, Optional
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

class SheetsService:
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 60  # Cache timeout in seconds
        self.last_request_time = 0
        self.min_request_interval = 1.1  # Minimum time between requests in seconds
        self.is_sheets_enabled = False
        try:
            self._init_client()
            self.is_sheets_enabled = True
        except Exception as e:
            logger.warning(f"Google Sheets integration is disabled: {str(e)}")
            self.is_sheets_enabled = False

    def _init_client(self):
        """Initialize the Google Sheets client with proper credentials"""
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            
            # Get credentials from environment variable
            creds_json = os.getenv('GOOGLE_CREDENTIALS')
            if not creds_json:
                raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")
            
            # Parse the JSON string from environment variable
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=scope)
            
            self.client = gspread.authorize(creds)
            logger.info("Successfully initialized Google Sheets client")
            
        except Exception as e:
            logger.error(f"Error initializing Google Sheets client: {str(e)}")
            raise

    def _rate_limit(self):
        """Implement rate limiting to prevent quota exceeded errors"""
        if not self.is_sheets_enabled:
            return
            
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    def _get_cached_data(self, sheet_id: str, key: str) -> Optional[dict]:
        """Get cached data if it exists and is not expired"""
        cache_entry = self.cache.get(f"{sheet_id}_{key}")
        if cache_entry:
            timestamp, data = cache_entry
            if time.time() - timestamp < self.cache_timeout:
                return data
        return None

    def _set_cached_data(self, sheet_id: str, key: str, data: dict):
        """Cache data with current timestamp"""
        self.cache[f"{sheet_id}_{key}"] = (time.time(), data)

    def get_sheet(self, sheet_id: str):
        """Get a worksheet with rate limiting"""
        self._rate_limit()
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            return spreadsheet.sheet1
        except Exception as e:
            logger.error(f"Error accessing sheet {sheet_id}: {str(e)}")
            raise

    def get_waiting_bookings(self, sheet_id: str = None) -> List[Dict]:
        """Get waiting bookings with caching"""
        if not self.is_sheets_enabled:
            return []
            
        cache_key = "waiting_bookings"
        cached_data = self._get_cached_data(sheet_id, cache_key) if sheet_id else None
        if cached_data:
            return cached_data

        self._rate_limit()
        try:
            if sheet_id:
                sheet = self.get_sheet(sheet_id)
                all_records = sheet.get_all_records()
                waiting_bookings = [
                    booking for booking in all_records 
                    if booking.get('Status', '').lower() == 'waiting'
                ]
                self._set_cached_data(sheet_id, cache_key, waiting_bookings)
                return waiting_bookings
            return []
        except Exception as e:
            logger.error(f"Error getting waiting bookings: {str(e)}")
            return []

    def get_done_bookings(self, sheet_id: str = None) -> List[Dict]:
        """Get completed bookings with caching"""
        if not self.is_sheets_enabled:
            return []
            
        cache_key = "done_bookings"
        cached_data = self._get_cached_data(sheet_id, cache_key) if sheet_id else None
        if cached_data:
            return cached_data

        self._rate_limit()
        try:
            if sheet_id:
                sheet = self.get_sheet(sheet_id)
                all_records = sheet.get_all_records()
                done_bookings = [
                    booking for booking in all_records 
                    if booking.get('Status', '').lower() == 'done'
                ]
                self._set_cached_data(sheet_id, cache_key, done_bookings)
                return done_bookings
            return []
        except Exception as e:
            logger.error(f"Error getting done bookings: {str(e)}")
            return []

    def add_booking(self, sheet_id: str, booking_data: Dict) -> bool:
        """Add a new booking with rate limiting"""
        if not self.is_sheets_enabled:
            return True  # Return success in limited mode
            
        self._rate_limit()
        try:
            if sheet_id:
                sheet = self.get_sheet(sheet_id)
                # Clear relevant cache entries
                self.cache.pop(f"{sheet_id}_waiting_bookings", None)
                self.cache.pop(f"{sheet_id}_done_bookings", None)
                
                # Add the booking
                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    booking_data.get('name', ''),
                    booking_data.get('phone', ''),
                    booking_data.get('barber', ''),
                    booking_data.get('ticket_number', ''),
                    'Waiting'
                ])
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding booking: {str(e)}")
            return False

    def update_booking_status(self, sheet_id: str, row_number: int, status: str) -> bool:
        """Update booking status with rate limiting"""
        if not self.is_sheets_enabled:
            return True  # Return success in limited mode
            
        self._rate_limit()
        try:
            if sheet_id:
                sheet = self.get_sheet(sheet_id)
                # Clear relevant cache entries
                self.cache.pop(f"{sheet_id}_waiting_bookings", None)
                self.cache.pop(f"{sheet_id}_done_bookings", None)
                
                # Update the status
                sheet.update_cell(row_number, 6, status)  # Assuming status is in column F
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating booking status: {str(e)}")
            return False

    def delete_booking(self, sheet_id: str, row_number: int) -> bool:
        """Delete a booking with rate limiting"""
        if not self.is_sheets_enabled:
            return True  # Return success in limited mode
            
        self._rate_limit()
        try:
            if sheet_id:
                sheet = self.get_sheet(sheet_id)
                # Clear relevant cache entries
                self.cache.pop(f"{sheet_id}_waiting_bookings", None)
                self.cache.pop(f"{sheet_id}_done_bookings", None)
                
                # Delete the row
                sheet.delete_rows(row_number)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting booking: {str(e)}")
            return False

    def clear_cache(self, sheet_id: str = None):
        """Clear cache for a specific sheet or all sheets"""
        if sheet_id:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{sheet_id}_")]
            for key in keys_to_remove:
                self.cache.pop(key, None)
        else:
            self.cache.clear()

    def get_all_bookings(self):
        """Get all bookings with caching"""
        try:
            cached_data = self._get_cached_data('all_bookings')
            if cached_data:
                return cached_data

            data = self.sheet.get_all_values()
            self._set_cached_data('all_bookings', data)
            return data
        except gspread.exceptions.APIError as e:
            if self._handle_api_error(e):
                return self.get_all_bookings()
            raise
        except Exception as e:
            logging.error(f"Error getting all bookings: {str(e)}")
            raise

    def get_barber_bookings(self, barber_name):
        """Get bookings for a specific barber with caching"""
        try:
            cache_key = f'barber_bookings_{barber_name}'
            cached_data = self._get_cached_data(cache_key)
            if cached_data:
                return cached_data

            all_bookings = self.get_all_bookings()
            barber_bookings = [booking for booking in all_bookings[1:] if booking[3] == barber_name]
            self._set_cached_data(cache_key, barber_bookings)
            return barber_bookings
        except Exception as e:
            logging.error(f"Error getting barber bookings: {str(e)}")
            raise

    def get_booking_status(self, booking_id: int) -> str:
        """Get the current status of a booking"""
        try:
            bookings = self.get_all_bookings()
            for row in bookings[1:]:  # Skip header row
                if row[0] == str(booking_id):
                    return row[5]  # Status is in column 6
            return None
        except Exception as e:
            logging.error(f"Error getting booking status: {str(e)}")
            return None

    def update_booking_status(self, booking_id: int, new_status: str) -> bool:
        """Update the status of a booking"""
        try:
            bookings = self.get_all_bookings()
            for i, row in enumerate(bookings[1:], start=2):  # Skip header row
                if row[0] == str(booking_id):
                    self.sheet.update_cell(i, 6, new_status)  # Status is in column 6
                    return True
            return False
        except Exception as e:
            logging.error(f"Error updating booking status: {str(e)}")
            return False

    def delete_booking(self, row):
        """Delete booking with retry logic"""
        try:
            self.sheet.delete_row(row)
            self.cache = {}  # Invalidate all cache
        except gspread.exceptions.APIError as e:
            if self._handle_api_error(e):
                return self.delete_booking(row)
            raise
        except Exception as e:
            logging.error(f"Error deleting booking: {str(e)}")
            raise

    def refresh_connection(self):
        """Refresh the Google Sheets connection and clear cache"""
        self._init_client()
        self.cache = {}

    def has_active_appointment(self, user_id: str) -> bool:
        """Check if the user has an active appointment"""
        bookings = self.get_all_bookings()
        for booking in bookings[1:]:  # Skip header row
            if booking[0] == user_id and booking[5] != "Done" and booking[5] != "Deleted":
                return True
        return False

    def append_booking(self, booking_data):
        """Add a new booking to the sheet"""
        self.refresh_connection()
        self.sheet.append_row(booking_data)

    def generate_ticket_number(self):
        """Generate a new ticket number based on the number of existing bookings"""
        bookings = self.get_all_bookings()
        return len(bookings)  # Assuming the first row is the header 

    def update_cell(self, row, col, value):
        """Update a specific cell with retry logic"""
        try:
            self.sheet.update_cell(row, col, value)
            # Invalidate cache after update
            self.cache = {}
            logging.info(f"Updated cell ({row}, {col}) to '{value}'")
            return True
        except gspread.exceptions.APIError as e:
            if self._handle_api_error(e):
                return self.update_cell(row, col, value)
            raise
        except Exception as e:
            logging.error(f"Error updating cell: {str(e)}")
            return False 

    def get_appointment_status(self, user_id: str) -> str:
        """Get the status of the user's active appointment"""
        bookings = self.get_all_bookings()
        for booking in bookings[1:]:  # Skip header row
            if booking[0] == user_id:
                return booking[5]  # Assuming status is in the 6th column
        return "None"  # No active appointment 