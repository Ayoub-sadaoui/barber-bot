import gspread
import logging
import time
import re
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler, ConversationHandler
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------------- Setup Logging ----------------
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ---------------- Google Sheets Authentication ----------------
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Get and validate environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_CREDS_JSON = os.getenv('GOOGLE_CREDENTIALS')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not found")
if not GOOGLE_CREDS_JSON:
    raise ValueError("GOOGLE_CREDENTIALS environment variable not found")

# Parse the Google credentials JSON string into a dictionary
CREDS_DICT = json.loads(GOOGLE_CREDS_JSON)
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_DICT, SCOPE)

client = gspread.authorize(CREDS)
SHEET = client.open("3ami tayeb").sheet1

# Define conversation states
SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE, ADMIN_VERIFICATION = range(4)
ADMIN_ID = "5333075597"  # Replace with your Telegram ID
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'barber2020')  # Default to 'KIKO' if not set

# Store notification status to prevent duplicate notifications
NOTIFICATION_CACHE = {}

# Define a constant for appointment duration
APPOINTMENT_DURATION_MINUTES = 10

# Barber configuration
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

# ---------------- Helper Functions ----------------
def is_valid_phone(phone):
    # Check if phone number matches Algerian format (e.g., 0677366125)
    # Remove any spaces or special characters from the input
    phone = phone.strip().replace(' ', '').replace('-', '')
    phone_pattern = re.compile(r'^0[567]\d{8}$')
    return bool(phone_pattern.match(phone))

def is_valid_name(name):
    # Check if name contains only letters and spaces, and is between 3 and 30 characters
    name_pattern = re.compile(r'^[A-Za-z\s]{3,30}$')
    return bool(name_pattern.match(name))

def has_active_appointment(user_id):
    bookings = SHEET.get_all_values()
    return any(row[0] == str(user_id) and row[5] == "Waiting" for row in bookings[1:])

def refresh_google_sheets_connection():
    """Refresh Google Sheets connection if needed"""
    global client, SHEET
    try:
        # Test the connection by getting values
        SHEET.get_all_values()
    except Exception:
        # Reconnect if there's an error
        client = gspread.authorize(CREDS)
        SHEET = client.open("3ami tayeb").sheet1

def save_notification_status(user_id: str, notification_type: str):
    """Save that a notification has been sent"""
    NOTIFICATION_CACHE[f"{user_id}_{notification_type}"] = datetime.now().timestamp()

def was_recently_notified(user_id: str, notification_type: str) -> bool:
    """Check if user was recently notified (within last 5 minutes)"""
    key = f"{user_id}_{notification_type}"
    if key not in NOTIFICATION_CACHE:
        return False
    time_diff = datetime.now().timestamp() - NOTIFICATION_CACHE[key]
    return time_diff < 300  # 5 minutes

async def check_and_notify_users(context: CallbackContext):
    """Periodically check queue and notify users of their turn"""
    try:
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()
        
        # Get all waiting appointments
        waiting_appointments = [row for row in bookings[1:] if row[5] == "Waiting"]
        
        # Clear old notifications for users no longer in queue
        current_user_ids = [appointment[0] for appointment in waiting_appointments]
        for key in list(NOTIFICATION_CACHE.keys()):
            user_id = key.split('_')[0]
            if user_id not in current_user_ids:
                del NOTIFICATION_CACHE[key]
        
        for position, appointment in enumerate(waiting_appointments):
            user_id = appointment[0]
            user_name = appointment[1]
            barber = appointment[3]
            
            try:
                # Send turn notification to first in line
                if position == 0 and not was_recently_notified(user_id, "turn"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🎉 {user_name}، دورك توا!\n"
                             f"روح لـ {barber}.\n"
                             f"إذا ما جيتش في 5 دقايق، تقدر تخسر دورك."
                    )
                    save_notification_status(user_id, "turn")
                    logging.info(f"Sent turn notification to user {user_id}")
                
                # Send 15-minute warning to next in line
                elif position == 1 and not was_recently_notified(user_id, "warning"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔔 {user_name}! دورك قريب يجي مع {barber} في 15 دقيقة.\n"
                             f"ابدا تقرب للصالون باش ما تخسرش دورك."
                    )
                    save_notification_status(user_id, "warning")
                    logging.info(f"Sent 15-min warning to user {user_id}")
                
                # Send 30-minute warning to third in line
                elif position == 2 and not was_recently_notified(user_id, "warning_30"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔔 {user_name}! دورك غادي يجي مع {barber} في 30 دقيقة.\n"
                             f"ابدا تقرب للصالون باش ما تخسرش دورك."
                    )
                    save_notification_status(user_id, "warning_30")
                    logging.info(f"Sent 30-min warning to user {user_id}")
                
                # Send 45-minute warning to fourth in line
                elif position == 3 and not was_recently_notified(user_id, "warning_45"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔔 {user_name}! دورك غادي يجي مع {barber} في 45 دقيقة.\n"
                             f"ابدا تقرب للصالون باش ما تخسرش دورك."
                    )
                    save_notification_status(user_id, "warning_45")
                    logging.info(f"Sent 45-min warning to user {user_id}")
                
                # Send 1-hour warning to fifth in line
                elif position == 4 and not was_recently_notified(user_id, "warning_60"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔔 {user_name}! دورك غادي يجي مع {barber} في ساعة.\n"
                             f"ابدا تقرب للصالون باش ما تخسرش دورك."
                    )
                    save_notification_status(user_id, "warning_60")
                    logging.info(f"Sent 60-min warning to user {user_id}")
                
            except Exception as e:
                logging.error(f"Failed to send notification to user {user_id}: {str(e)}")
                continue
                    
    except Exception as e:
        logging.error(f"Error in check_and_notify_users: {str(e)}")

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

# Add a function to generate a ticket number
def generate_ticket_number() -> int:
    """Generate a new ticket number based on the number of existing bookings"""
    bookings = SHEET.get_all_values()
    return len(bookings)  # Assuming the first row is the header

# ---------------- Telegram Bot Handlers ----------------
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [["📋 شوف لاشان", "📅 دير رنديفو"],  # Changed to match BTN_BOOK_APPOINTMENT
                ["⏳ شحال باقي"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("مرحبا بيك عند الحلاق! شنو تحب دير:", reply_markup=reply_markup)
    return ConversationHandler.END

async def choose_barber(update: Update, context: CallbackContext) -> int:
    logging.info(f"Booking button clicked. Message text: {update.message.text}")
    user_id = update.message.chat_id
    
    if has_active_appointment(user_id):
        await update.message.reply_text("❌ عندك رندي فو مازال ما كملش. لازم تستنى حتى يكمل قبل ما دير واحد اخر.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(name, callback_data=id)] for id, name in BARBERS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("شكون من حلاق تحب:", reply_markup=reply_markup)
    return SELECTING_BARBER

async def barber_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    selected_barber = query.data.replace("barber_", "الحلاق ")  # Changed to Arabic
    context.user_data['barber'] = selected_barber
    await query.message.reply_text(
        f"اخترت {selected_barber}. من فضلك دخل اسمك الكامل:\n"
        "(الاسم لازم يكون بين 3 و 30 حرف)"
    )
    return ENTERING_NAME

async def handle_name(update: Update, context: CallbackContext) -> int:
    user_name = update.message.text

    if not is_valid_name(user_name):
        await update.message.reply_text(
            "❌ الاسم ماشي صحيح. من فضلك دخل اسم صحيح:\n"
            "- استخدم غير الحروف والمسافات\n"
            "- الاسم لازم يكون بين 3 و 30 حرف\n"
            "- بلا أرقام ولا رموز خاصة"
        )
        return ENTERING_NAME
    
    context.user_data['name'] = user_name
    await update.message.reply_text(
        "دخل رقم تيليفونك:\n"
        "(مثال: 06XXXXXXXX وﻻ 07XXXXXXXX)"
    )
    return ENTERING_PHONE

async def handle_phone(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    phone = update.message.text.strip().replace(' ', '').replace('-', '')  # Clean the input
    
    if not is_valid_phone(phone):
        await update.message.reply_text(
            "❌ Invalid phone number format. Please enter a valid Algerian phone number:\n"
            "- Should start with 06 or 07\n"
            "- Should be exactly 10 digits\n"
            "Example: 0677366125"
        )
        return ENTERING_PHONE
    
    user_name = context.user_data.get('name')
    selected_barber = context.user_data.get('barber')
    
    if not all([user_name, selected_barber]):
        await update.message.reply_text("Something went wrong. Please start the booking process again by selecting '📅 Book Appointment'.")
        return ConversationHandler.END
    
    try:
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()
        waiting_appointments = [row for row in bookings[1:] if row[5] == "Waiting"]
        position = len(waiting_appointments)  # New position will be at the end

        # Generate a ticket number
        ticket_number = generate_ticket_number()

    # Add the new booking to Google Sheets
        SHEET.append_row([user_id, user_name, phone, selected_barber, time.strftime("%Y-%m-%d %H:%M:%S"), "Waiting", ticket_number])
        
        # Send confirmation message with position info
        if position == 0:
            await update.message.reply_text(
                f"✅ {user_name}، تسجل رونديفو مع {selected_barber}!\n"
                f"📱 رقم التيليفون: {phone}\n"
                f"🎟️ رقم التذكرة: {ticket_number}\n"
                "🎉 مبروك! راك الأول - دورك توا!"
            )
            save_notification_status(str(user_id), "turn")
        else:
            estimated_minutes = position * APPOINTMENT_DURATION_MINUTES
            formatted_wait_time = format_wait_time(estimated_minutes)
            estimated_time = get_estimated_completion_time(estimated_minutes)
            
            await update.message.reply_text(
                f"✅ {user_name}، تسجل رونديفو مع {selected_barber}!\n"
                f"📱 رقم التيليفون: {phone}\n"
                f"🎟️ رقم التذكرة: {ticket_number}\n"
                f"📊 مرتبتك في الطابور: {position + 1}\n"
                f"⏳ وقت الانتظار تقريبا: {formatted_wait_time}\n"
                f"🕒 دورك غادي يجي على: {estimated_time}"
            )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"Error in handle_phone for user {user_id}: {str(e)}")
        await update.message.reply_text("Sorry, we couldn't process your booking right now. Please try again in a few moments.")
        context.user_data.clear()
        return ConversationHandler.END

async def check_queue(update: Update, context: CallbackContext) -> None:
    try:
        refresh_google_sheets_connection()
        user_id = str(update.message.chat_id)
        bookings = SHEET.get_all_values()
        
        waiting_appointments = [row for row in bookings[1:] if row[5] == "Waiting"]
        user_position = next((i for i, row in enumerate(waiting_appointments) if row[0] == user_id), -1)
        
        if user_position == -1:
            total_waiting = len(waiting_appointments)
            if total_waiting == 0:
                msg = "ما كاين حتى واحد في لاشان"
            elif total_waiting == 1:
                msg = "كاين غير بنادم واحد في لاشان"
            elif total_waiting == 2:
                msg = "كاين زوج في لاشان"
            else:
                msg = f"كاين {total_waiting} ناس في لاشان"
            
            await update.message.reply_text(
                f"📋 {msg}\n"
                "ما عندكش رندي فو."
            )
        elif user_position == 0:
            await update.message.reply_text("🎉 دورك توا! روح للحلاق.")
        else:
            if user_position == 1:
                people_msg = "قدامك غير واحد"
            elif user_position == 2:
                people_msg = "قدامك زوج"
            else:
                people_msg = f"قدامك {user_position} ناس"
                
            await update.message.reply_text(
                f"📋 مرتبتك في لاشان: {user_position + 1}\n"
                f"{people_msg}"
            )
            
    except Exception as e:
        logging.error(f"Error in check_queue: {str(e)}")
        await update.message.reply_text("سمحلي، كاين مشكل. عاود حاول مرة أخرى.")

async def estimated_wait_time(update: Update, context: CallbackContext) -> None:
    try:
        refresh_google_sheets_connection()
        user_id = str(update.message.chat_id)
        bookings = SHEET.get_all_values()
        
        waiting_appointments = [row for row in bookings[1:] if row[5] == "Waiting"]
        user_position = next((i for i, row in enumerate(waiting_appointments) if row[0] == user_id), -1)
        
        if user_position == -1:
            # User is not in queue
            total_waiting = len(waiting_appointments)
            estimated_minutes = total_waiting * APPOINTMENT_DURATION_MINUTES
            formatted_wait_time = format_wait_time(estimated_minutes)
            estimated_time = get_estimated_completion_time(estimated_minutes)
            
            await update.message.reply_text(
                f"⏳ إذا دير رندي فو دروك:\n"
                f"• تستنى: {formatted_wait_time}\n"
                f"• دورك غادي يجي على: {estimated_time}\n"
                f"📊 كاين {total_waiting} ناس في لاشان"
            )
        elif user_position == 0:
            # User is first in line
            await update.message.reply_text(
                "✨ مبروك! راك الأول - دورك توا!\n"
                "روح للحلاق."
            )
        else:
            # User is in queue but not first
            estimated_minutes = user_position * APPOINTMENT_DURATION_MINUTES
            formatted_wait_time = format_wait_time(estimated_minutes)
            estimated_time = get_estimated_completion_time(estimated_minutes)
            
            await update.message.reply_text(
                f"📊 مرتبتك: {user_position + 1}\n"
                f"👥 قدامك: {user_position} ناس\n"
                f"⏳ باقي تستنى: {formatted_wait_time}\n"
                f"🕒 دورك غادي يجي على: {estimated_time}"
            )
            
    except Exception as e:
        logging.error(f"Error in estimated_wait_time: {str(e)}")
        await update.message.reply_text("سمحلي، كاين مشكل. عاود حاول مرة أخرى.")

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("تم إلغاء الحجز. يمكنك حجز موعد جديد في أي وقت.")
    return ConversationHandler.END

async def admin_panel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.chat_id)
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ممنوع. هذا الأمر للمسؤول فقط.")
        return
    
    # Ask for password
    await update.message.reply_text("من فضلك أدخل كلمة السر للدخول إلى لوحة التحكم:")
    return ADMIN_VERIFICATION  # Move to the password verification state

async def verify_admin_password(update: Update, context: CallbackContext) -> int:
    entered_password = update.message.text.strip()
    
    if entered_password == ADMIN_PASSWORD:
        keyboard = [
            [BTN_VIEW_WAITING, BTN_VIEW_DONE],
            [BTN_VIEW_BARBER1, BTN_VIEW_BARBER2],
            [BTN_CHANGE_STATUS, BTN_DELETE],
            [BTN_ADD, BTN_REFRESH]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🔐 مرحبا بيك في لوحة التحكم\n"
            "اختار واش تحب دير:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ كلمة السر غير صحيحة. حاول مرة أخرى.")
        return ADMIN_VERIFICATION  # Stay in the password verification state

async def view_all_bookings(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.chat_id)
    
    if user_id != ADMIN_ID:
        return
    
    try:
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()[1:]  # Skip header row
        
        if not bookings:
            await update.message.reply_text("No bookings found.")
            return
        
        waiting_message = "📋 Waiting Appointments:\n\n"
        done_message = "📋 Done Appointments:\n\n"
        
        for i, booking in enumerate(bookings, 1):
            booking_info = (f"{i}. Name: {booking[1]}\n"
                            f"   Phone: {booking[2]}\n"
                            f"   Barber: {booking[3]}\n"
                            f"   Time: {booking[4]}\n"
                            f"   Status: {booking[5]}\n"
                            f"   Ticket: {booking[6]}\n"
                            f"   ID: {booking[0]}\n"
                            f"{'─' * 20}\n")
            
            if booking[5] == "Waiting":
                waiting_message += booking_info
            else:
                done_message += booking_info
        
        # Send messages
        if len(waiting_message) > 4096:
            messages = [waiting_message[i:i+4096] for i in range(0, len(waiting_message), 4096)]
            for msg in messages:
                await update.message.reply_text(msg)
        else:
            await update.message.reply_text(waiting_message)
        
        if len(done_message) > 4096:
            messages = [done_message[i:i+4096] for i in range(0, len(done_message), 4096)]
            for msg in messages:
                await update.message.reply_text(msg)
        else:
            await update.message.reply_text(done_message)
            
    except Exception as e:
        logging.error(f"Error in view_all_bookings: {str(e)}")
        await update.message.reply_text("Error fetching bookings. Please try again.")

async def view_waiting_bookings(update: Update, context: CallbackContext) -> None:
    if str(update.message.chat_id) != ADMIN_ID:
        return

    try:
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()[1:]  # Skip header row
        waiting_bookings = [b for b in bookings if b[5] == "Waiting"]

        if not waiting_bookings:
            await update.message.reply_text("ما كاين حتى واحد يستنى 🤷‍♂️")
            return

        message = "📋 لي راهم يستناو:\n\n"
        for i, booking in enumerate(waiting_bookings, 1):
            # Add status change and delete buttons for each booking
            keyboard = [
                [
                    InlineKeyboardButton("✅ خلاص", callback_data=f"status_{booking[0]}"),
                    InlineKeyboardButton("❌ امسح", callback_data=f"delete_{booking[0]}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (f"{i}. الاسم: {booking[1]}\n"
                      f"   التيليفون: {booking[2]}\n"
                      f"   الحلاق: {booking[3]}\n"
                      f"   الوقت: {booking[4]}\n"
                      f"   التذكرة: {booking[6]}\n"
                      f"{'─' * 20}\n")
            
            await update.message.reply_text(message, reply_markup=reply_markup)

    except Exception as e:
        logging.error(f"Error in view_waiting_bookings: {str(e)}")
        await update.message.reply_text("كاين مشكل. عاود حاول.")

async def handle_status_change(update: Update, context: CallbackContext) -> None:
    """Handle changing the status of a booking"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != ADMIN_ID:
        await query.message.reply_text("⛔ ممنوع. هذا الأمر للمسؤول فقط.")
        return
    
    try:
        # Extract booking ID from callback data
        booking_id = query.data.split('_')[1]
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()
        
        # Find the booking and update its status
        for i, row in enumerate(bookings[1:], start=2):  # Start from 2 because of 1-based index and header row
            if row[0] == booking_id:
                SHEET.update_cell(i, 6, "Done")  # Update status column
                await query.message.reply_text(f"✅ تم تغيير حالة الحجز إلى 'تم'")
                return
        
        await query.message.reply_text("❌ لم يتم العثور على الحجز")
        
    except Exception as e:
        logging.error(f"Error in handle_status_change: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ أثناء تغيير حالة الحجز")

async def handle_delete_booking(update: Update, context: CallbackContext) -> None:
    """Handle deleting a booking"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != ADMIN_ID:
        await query.message.reply_text("⛔ ممنوع. هذا الأمر للمسؤول فقط.")
        return
    
    try:
        # Extract booking ID from callback data
        booking_id = query.data.split('_')[1]
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()
        
        # Find the booking and delete it
        for i, row in enumerate(bookings[1:], start=2):  # Start from 2 because of 1-based index and header row
            if row[0] == booking_id:
                SHEET.delete_rows(i)
                await query.message.reply_text(f"✅ تم حذف الحجز بنجاح")
                return
        
        await query.message.reply_text("❌ لم يتم العثور على الحجز")
        
    except Exception as e:
        logging.error(f"Error in handle_delete_booking: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ أثناء حذف الحجز")

async def view_done_bookings(update: Update, context: CallbackContext) -> None:
    """View all completed bookings"""
    if str(update.message.chat_id) != ADMIN_ID:
        return

    try:
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()[1:]  # Skip header row
        done_bookings = [b for b in bookings if b[5] == "Done"]

        if not done_bookings:
            await update.message.reply_text("ما كاين حتى حجز مكمل 🤷‍♂️")
            return

        message = "📋 الحجوزات المكملة:\n\n"
        for i, booking in enumerate(done_bookings, 1):
            message += (f"{i}. الاسم: {booking[1]}\n"
                       f"   التيليفون: {booking[2]}\n"
                       f"   الحلاق: {booking[3]}\n"
                       f"   الوقت: {booking[4]}\n"
                       f"   التذكرة: {booking[6]}\n"
                       f"{'─' * 20}\n")

        await update.message.reply_text(message)

    except Exception as e:
        logging.error(f"Error in view_done_bookings: {str(e)}")
        await update.message.reply_text("كاين مشكل. عاود حاول.")

async def view_barber_bookings(update: Update, context: CallbackContext) -> None:
    """View bookings for a specific barber"""
    if str(update.message.chat_id) != ADMIN_ID:
        return

    try:
        refresh_google_sheets_connection()
        bookings = SHEET.get_all_values()[1:]  # Skip header row
        
        # Determine which barber's bookings to show
        message_text = update.message.text
        if BTN_VIEW_BARBER1 in message_text:
            barber_name = BARBERS['barber_1']
        elif BTN_VIEW_BARBER2 in message_text:
            barber_name = BARBERS['barber_2']
        else:
            await update.message.reply_text("❌ لم يتم تحديد الحلاق")
            return

        barber_bookings = [b for b in bookings if b[3] == barber_name]
        
        if not barber_bookings:
            await update.message.reply_text(f"ما كاين حتى حجز مع {barber_name} 🤷‍♂️")
            return

        message = f"📋 حجوزات {barber_name}:\n\n"
        for i, booking in enumerate(barber_bookings, 1):
            status_emoji = "⏳" if booking[5] == "Waiting" else "✅"
            message += (f"{i}. {status_emoji} {booking[1]}\n"
                       f"   التيليفون: {booking[2]}\n"
                       f"   الوقت: {booking[4]}\n"
                       f"   التذكرة: {booking[6]}\n"
                       f"{'─' * 20}\n")

        await update.message.reply_text(message)

    except Exception as e:
        logging.error(f"Error in view_barber_bookings: {str(e)}")
        await update.message.reply_text("كاين مشكل. عاود حاول.")

async def handle_add_client(update: Update, context: CallbackContext) -> None:
    """Handle adding a new client directly"""
    if str(update.message.chat_id) != ADMIN_ID:
        return
    
    try:
        # Start the booking process for admin
        keyboard = [[InlineKeyboardButton(name, callback_data=id)] for id, name in BARBERS.items()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("شكون من حلاق تحب:", reply_markup=reply_markup)
        context.user_data['is_admin_booking'] = True
        return SELECTING_BARBER
    except Exception as e:
        logging.error(f"Error in handle_add_client: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء إضافة العميل")

async def handle_refresh(update: Update, context: CallbackContext) -> None:
    """Handle refreshing the admin panel"""
    if str(update.message.chat_id) != ADMIN_ID:
        return
    
    try:
        refresh_google_sheets_connection()
        keyboard = [
            [BTN_VIEW_WAITING, BTN_VIEW_DONE],
            [BTN_VIEW_BARBER1, BTN_VIEW_BARBER2],
            [BTN_CHANGE_STATUS, BTN_DELETE],
            [BTN_ADD, BTN_REFRESH]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🔄 تم تحديث البيانات\n"
            "اختار واش تحب دير:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Error in handle_refresh: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء تحديث البيانات")

def main():
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex(f"^{BTN_BOOK_APPOINTMENT}$"), choose_barber),
                CommandHandler("admin", admin_panel),
                MessageHandler(filters.Regex(f"^{BTN_ADD}$"), handle_add_client)
            ],
            states={
                SELECTING_BARBER: [
                    CallbackQueryHandler(barber_selection, pattern="^barber_")
                ],
                ENTERING_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)
                ],
                ENTERING_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)
                ],
                ADMIN_VERIFICATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, verify_admin_password)
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )

        # Add all handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_QUEUE}$"), check_queue))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_CHECK_WAIT}$"), estimated_wait_time))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_WAITING}$"), view_waiting_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_DONE}$"), view_done_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_BARBER1}$"), view_barber_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_BARBER2}$"), view_barber_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_REFRESH}$"), handle_refresh))
        app.add_handler(CallbackQueryHandler(handle_status_change, pattern="^status_"))
        app.add_handler(CallbackQueryHandler(handle_delete_booking, pattern="^delete_"))

        # Initialize job queue with more frequent checks
        if app.job_queue:
            # Clear any existing jobs
            app.job_queue.remove_all_jobs()
            # Add the notification job
            app.job_queue.run_repeating(check_and_notify_users, interval=30, first=5)
            logging.info("Job queue initialized successfully")
        else:
            logging.error("Job queue not available")

        logging.info("Bot is starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logging.error(f"Error starting bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()
