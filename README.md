# Barbershop Bot

A Telegram bot for managing appointments at a barbershop. The bot allows customers to book appointments, check their position in the queue, and receive notifications when it's their turn. It also provides an admin panel for managing appointments.

## Features

- Book appointments with specific barbers
- Check current queue position
- Estimate wait time
- Receive notifications when it's your turn
- Admin panel for managing appointments
- Real-time queue updates
- Google Sheets integration for data storage

## Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd barbershop-bot
```

2. Create a virtual environment and activate it:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following variables:

```
TELEGRAM_TOKEN=your_telegram_bot_token
GOOGLE_CREDENTIALS=your_google_credentials_json
ADMIN_PASSWORD=your_admin_password
```

5. Set up Google Sheets:
   - Create a new Google Sheet named "3ami tayeb"
   - Share it with the service account email from your credentials
   - The sheet should have the following columns:
     - User ID
     - Name
     - Phone
     - Barber
     - Time
     - Status
     - Ticket Number

## Running the Bot

1. Activate your virtual environment if not already activated:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the bot:

```bash
python src/main.py
```

## Usage

### Customer Commands

- `/start` - Start the bot and show main menu
- "📅 دير رنديفو" - Book a new appointment
- "📋 شوف لاشان" - Check your position in the queue
- "⏳ شحال باقي" - Check estimated wait time

### Admin Commands

- `/admin` - Access the admin panel (requires password)
- "⏳ لي راهم يستناو" - View all waiting appointments
- "✅ لي خلصو" - View completed appointments
- "👤 زبائن [حلاق]" - View appointments for specific barber
- "✅ خلاص" - Mark an appointment as completed
- "❌ امسح" - Delete an appointment
- "➕ زيد واحد" - Add a new appointment manually
- "🔄 شارجي" - Refresh the admin panel

## Project Structure

```
src/
├── config/
│   └── config.py         # Configuration and constants
├── handlers/
│   ├── admin_handlers.py # Admin command handlers
│   ├── booking_handlers.py # Booking process handlers
│   └── queue_handlers.py # Queue-related handlers
├── services/
│   ├── sheets_service.py # Google Sheets operations
│   └── notification_service.py # Notification handling
├── utils/
│   ├── formatters.py     # Text formatting utilities
│   └── validators.py     # Input validation utilities
└── main.py              # Main bot file
```

## Contributing

Feel free to submit issues and enhancement requests!
