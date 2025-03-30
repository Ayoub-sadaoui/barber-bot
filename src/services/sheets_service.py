import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from src.config.config import SCOPE, GOOGLE_CREDS_JSON

class SheetsService:
    def __init__(self):
        if not GOOGLE_CREDS_JSON:
            raise ValueError("GOOGLE_CREDENTIALS environment variable not found")
        
        # Parse the Google credentials JSON string into a dictionary
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open("3ami tayeb").sheet1

    def refresh_connection(self):
        """Refresh Google Sheets connection if needed"""
        try:
            # Test the connection by getting values
            self.sheet.get_all_values()
        except Exception:
            # Reconnect if there's an error
            self.client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(
                json.loads(GOOGLE_CREDS_JSON), SCOPE))
            self.sheet = self.client.open("3ami tayeb").sheet1

    def get_all_bookings(self):
        """Get all bookings from the sheet"""
        self.refresh_connection()
        return self.sheet.get_all_values()

    def append_booking(self, booking_data):
        """Add a new booking to the sheet"""
        self.refresh_connection()
        self.sheet.append_row(booking_data)

    def update_booking_status(self, row_index, status):
        """Update the status of a booking"""
        self.refresh_connection()
        self.sheet.update_cell(row_index, 6, status)  # Status is in column 6

    def delete_booking(self, row_index):
        """Delete a booking from the sheet"""
        self.refresh_connection()
        self.sheet.delete_rows(row_index)

    def get_waiting_bookings(self):
        """Get all waiting bookings"""
        bookings = self.get_all_bookings()
        return [row for row in bookings[1:] if row[5] == "Waiting"]

    def get_done_bookings(self):
        """Get all completed bookings"""
        bookings = self.get_all_bookings()
        return [row for row in bookings[1:] if row[5] == "Done"]

    def get_barber_bookings(self, barber_name):
        """Get all bookings for a specific barber"""
        bookings = self.get_all_bookings()
        return [row for row in bookings[1:] if row[3] == barber_name]

    def generate_ticket_number(self):
        """Generate a new ticket number based on the number of existing bookings"""
        bookings = self.get_all_bookings()
        return len(bookings)  # Assuming the first row is the header 