import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists (for local development)
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

ADMIN_ID = "5333075597"  # Replace with your Telegram ID
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'barber2020')

# Google Sheets Configuration
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDS_JSON = os.getenv('GOOGLE_CREDENTIALS')
if not GOOGLE_CREDS_JSON:
    raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")

# Barber Configuration
BARBERS = {
    "barber_1": "حلاق 1",
    "barber_2": "حلاق 2",
    "barber_3": "حلاق 3"
}

# Button text constants
BTN_VIEW_QUEUE = "📋 شوف لاشان"
BTN_BOOK_APPOINTMENT = "📅 دير رنديفو"
BTN_CHECK_WAIT = "⏳ شحال باقي"
BTN_VIEW_ALL = "👥 كل الرونديفوات"
BTN_VIEW_WAITING = "⏳ لي راهم يستناو"
BTN_VIEW_DONE = "✅ لي خلصو"
BTN_VIEW_BARBER1 = f"👤 زبائن {BARBERS['barber_1']}"
BTN_VIEW_BARBER2 = f"👤 زبائن {BARBERS['barber_2']}"
BTN_CHANGE_STATUS = "✅ خلاص"
BTN_DELETE = "❌ امسح"
BTN_ADD = "➕ زيد واحد"
BTN_REFRESH = "🔄 شارجي"
BTN_BACK = "🔙 ارجع"

# Appointment Configuration
APPOINTMENT_DURATION_MINUTES = 10

# Conversation States
SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE, ADMIN_VERIFICATION = range(4) 