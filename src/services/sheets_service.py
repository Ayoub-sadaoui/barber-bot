import os
import json
import logging
from datetime import datetime, timedelta
import time
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from src.config.config import SCOPE, GOOGLE_CREDS_JSON

class SheetsService:
    def __init__(self):
        self._init_client()
        self.cache = {}
        self.cache_timeout = 30  # Cache timeout in seconds

    def _init_client(self):
        """Initialize or reinitialize the Google Sheets client"""
        try:
            creds_dict = json.loads(GOOGLE_CREDS_JSON)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            self.client = gspread.authorize(creds)
            
            try:
                # Try to open by name first
                self.sheet = self.client.open("3ami tayeb").sheet1
            except gspread.exceptions.SpreadsheetNotFound:
                logging.warning("Could not find spreadsheet by name '3ami tayeb', trying to list all spreadsheets...")
                # List all available spreadsheets
                spreadsheets = self.client.list_spreadsheet_files()
                if spreadsheets:
                    logging.info(f"Available spreadsheets: {[s['name'] for s in spreadsheets]}")
                    # Use the first available spreadsheet
                    self.sheet = self.client.open(spreadsheets[0]['name']).sheet1
                    logging.info(f"Using spreadsheet: {spreadsheets[0]['name']}")
                else:
                    raise ValueError("No spreadsheets available for this Google account")
            
            logging.info("Successfully initialized Google Sheets client")
        except Exception as e:
            logging.error(f"Error initializing Google Sheets client: {str(e)}")
            raise

    def _get_cached_data(self, key):
        """Get data from cache if valid"""
        if key in self.cache:
            timestamp, data = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                return data
        return None

    def _set_cached_data(self, key, data):
        """Set data in cache"""
        self.cache[key] = (datetime.now(), data)

    def _handle_api_error(self, e, retry_count=0):
        """Handle API errors with exponential backoff"""
        if retry_count >= 3:
            raise e

        if isinstance(e, gspread.exceptions.APIError) and e.response.status_code == 429:
            wait_time = (2 ** retry_count) * 5  # Exponential backoff
            logging.warning(f"API quota exceeded. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            return True
        return False

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

    def get_waiting_bookings(self):
        """Get waiting bookings with caching"""
        try:
            cached_data = self._get_cached_data('waiting_bookings')
            if cached_data:
                return cached_data

            all_bookings = self.get_all_bookings()
            waiting_bookings = [booking for booking in all_bookings[1:] if booking[5] == "Waiting"]
            self._set_cached_data('waiting_bookings', waiting_bookings)
            return waiting_bookings
        except Exception as e:
            logging.error(f"Error getting waiting bookings: {str(e)}")
            raise

    def get_done_bookings(self):
        """Get completed bookings with caching"""
        try:
            cached_data = self._get_cached_data('done_bookings')
            if cached_data:
                return cached_data

            all_bookings = self.get_all_bookings()
            done_bookings = [booking for booking in all_bookings[1:] if booking[5] == "Done"]
            self._set_cached_data('done_bookings', done_bookings)
            return done_bookings
        except Exception as e:
            logging.error(f"Error getting done bookings: {str(e)}")
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

    def has_active_appointment(self, user_id):
        """Check if user has an active appointment"""
        bookings = self.get_all_bookings()
        return any(row[0] == str(user_id) and row[5] == "Waiting" for row in bookings[1:])

    def append_booking(self, booking_data):
        """Add a new booking to the sheet"""
        self.refresh_connection()
        self.sheet.append_row(booking_data)

    def generate_ticket_number(self):
        """Generate a new ticket number based on the number of existing bookings"""
        bookings = self.get_all_bookings()
        return len(bookings)  # Assuming the first row is the header 