import os
import logging
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'barber2020')
GOOGLE_CREDS_JSON = os.getenv('GOOGLE_CREDENTIALS')

# Barber Configuration
BARBERS = {
    "barber_1": "حلاق 1",
    "barber_2": "حلاق 2"
}

# Button text constants
BTN_VIEW_QUEUE = "📋 شوف لاشان"
BTN_BOOK_APPOINTMENT = "📅 دير رنديفو"
BTN_CHECK_WAIT = "⏳ شحال باقي"
BTN_VIEW_WAITING = "⏳ لي راهم يستناو"
BTN_VIEW_DONE = "✅ لي خلصو"
BTN_VIEW_BARBER1 = f"👤 زبائن {BARBERS['barber_1']}"
BTN_VIEW_BARBER2 = f"👤 زبائن {BARBERS['barber_2']}"
BTN_CHANGE_STATUS = "✅ خلاص"
BTN_DELETE = "❌ امسح"
BTN_ADD = "➕ زيد واحد"
BTN_REFRESH = "🔄 شارجي"
BTN_BACK = "🔙 ارجع"

# Conversation States
SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE, ADMIN_VERIFICATION = range(4)

# Google Sheets Service
class SheetsService:
    def __init__(self):
        if not GOOGLE_CREDS_JSON:
            raise ValueError("GOOGLE_CREDENTIALS environment variable not found")
        
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, 
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open("3ami tayeb").sheet1

    def refresh_connection(self):
        try:
            self.sheet.get_all_values()
    except Exception:
            creds_dict = json.loads(GOOGLE_CREDS_JSON)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                creds_dict, 
                ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            )
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open("3ami tayeb").sheet1

    def get_all_bookings(self):
        self.refresh_connection()
        return self.sheet.get_all_values()

    def append_booking(self, booking_data):
        self.refresh_connection()
        self.sheet.append_row(booking_data)

    def update_booking_status(self, row_index, status):
        self.refresh_connection()
        self.sheet.update_cell(row_index, 6, status)

    def delete_booking(self, row_index):
        self.refresh_connection()
        self.sheet.delete_rows(row_index)

    def get_waiting_bookings(self):
        bookings = self.get_all_bookings()
        return [row for row in bookings[1:] if row[5] == "Waiting"]

    def get_done_bookings(self):
        bookings = self.get_all_bookings()
        return [row for row in bookings[1:] if row[5] == "Done"]

    def get_barber_bookings(self, barber_name):
        bookings = self.get_all_bookings()
        return [row for row in bookings[1:] if row[3] == barber_name]

    def generate_ticket_number(self):
        bookings = self.get_all_bookings()
        return len(bookings)

# Notification Service
class NotificationService:
    def __init__(self):
        self.notification_cache = {}

    def save_notification_status(self, user_id: str, notification_type: str):
        self.notification_cache[f"{user_id}_{notification_type}"] = datetime.now().timestamp()

    def was_recently_notified(self, user_id: str, notification_type: str) -> bool:
    key = f"{user_id}_{notification_type}"
        if key not in self.notification_cache:
        return False
        time_diff = datetime.now().timestamp() - self.notification_cache[key]
        return time_diff < 300

    def clear_notifications_for_user(self, user_id: str):
        keys_to_remove = [key for key in self.notification_cache.keys() if key.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            del self.notification_cache[key]

    async def send_notifications(self, context, waiting_appointments):
        try:
        current_user_ids = [appointment[0] for appointment in waiting_appointments]
            for key in list(self.notification_cache.keys()):
            user_id = key.split('_')[0]
            if user_id not in current_user_ids:
                    del self.notification_cache[key]
        
        for position, appointment in enumerate(waiting_appointments):
            user_id = appointment[0]
            user_name = appointment[1]
            barber = appointment[3]
            
            try:
                    if position == 0 and not self.was_recently_notified(user_id, "turn"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🎉 {user_name}، دورك توا!\n"
                             f"روح لـ {barber}.\n"
                             f"إذا ما جيتش في 5 دقايق، تقدر تخسر دورك."
                    )
                        self.save_notification_status(user_id, "turn")
                    logging.info(f"Sent turn notification to user {user_id}")
                
                    elif position == 1 and not self.was_recently_notified(user_id, "warning"):
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔔 {user_name}! دورك قريب يجي مع {barber} في 15 دقيقة.\n"
                             f"ابدا تقرب للصالون باش ما تخسرش دورك."
                    )
                        self.save_notification_status(user_id, "warning")
                    logging.info(f"Sent 15-min warning to user {user_id}")
                
            except Exception as e:
                    logging.error(f"Error sending notification to user {user_id}: {str(e)}")
                    
    except Exception as e:
            logging.error(f"Error in send_notifications: {str(e)}")

# Initialize services
sheets_service = SheetsService()
notification_service = NotificationService()

# Handlers
async def start(update: Update, context):
    keyboard = [
        ["📋 شوف لاشان", "✂️ دير رنديفو"],
        ["⏳ شحال باقي"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👋 مرحبا بيك عند الحلاق!\n🤔 شنو تحب دير:", reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context):
    await update.message.reply_text("تم إلغاء الحجز. يمكنك حجز موعد جديد في أي وقت.")
        return ConversationHandler.END
    
async def choose_barber(update: Update, context):
    keyboard = [
        [InlineKeyboardButton(f"👨‍💇‍♂️ {BARBERS['barber_1']}", callback_data="barber_1")],
        [InlineKeyboardButton(f"👨‍💇‍♂️ {BARBERS['barber_2']}", callback_data="barber_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("💈 شوف منين تحب تحلق:", reply_markup=reply_markup)
    return SELECTING_BARBER

async def barber_selection(update: Update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["barber"] = BARBERS[query.data]
    await query.edit_message_text("✏️ كتب سميتك من فضلك:")
    return ENTERING_NAME

async def handle_name(update: Update, context):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📱 كتب رقم تيلفونك (مثال: 0677366125):")
    return ENTERING_PHONE

async def handle_phone(update: Update, context):
    phone = update.message.text.strip().replace(' ', '').replace('-', '')
    if not phone.startswith(('05', '06', '07')) or len(phone) != 10 or not phone.isdigit():
        await update.message.reply_text("❌ الرقم ماشي صحيح.\n📱 كتب رقم صحيح (مثال: 0677366125):")
        return ENTERING_PHONE
    
    context.user_data["phone"] = phone
    user_id = str(update.message.chat_id)
    name = context.user_data["name"]
    barber = context.user_data["barber"]
    ticket_number = sheets_service.generate_ticket_number()

    booking_data = [user_id, name, phone, barber, datetime.now().strftime("%Y-%m-%d %H:%M"), "Waiting", str(ticket_number)]
    sheets_service.append_booking(booking_data)
            
    await update.message.reply_text(
        f"✅ تم حجز موعدك!\n"
        f"🎫 رقم تيكيتك: {ticket_number}\n"
        f"💇‍♂️ الحلاق: {barber}\n"
        f"📋 شوف لاشان باش تعرف مرتبتك"
    )
    return ConversationHandler.END

async def admin_panel(update: Update, context):
    await update.message.reply_text("🔐 كتب كلمة السر:")
    return ADMIN_VERIFICATION

async def verify_admin_password(update: Update, context):
    if update.message.text != ADMIN_PASSWORD:
        await update.message.reply_text("❌ كلمة السر ماشي صحيحة.")
        return ConversationHandler.END
        
    keyboard = [
        [BTN_VIEW_WAITING, BTN_VIEW_DONE],
        [BTN_VIEW_BARBER1, BTN_VIEW_BARBER2],
        [BTN_ADD, BTN_REFRESH]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👋 مرحبا بيك في لوحة التحكم:", reply_markup=reply_markup)
    return ConversationHandler.END

async def view_waiting_bookings(update: Update, context):
    waiting_appointments = sheets_service.get_waiting_bookings()
    if not waiting_appointments:
        await update.message.reply_text("ما كاين حتى واحد في لاشان")
        return

    message = "⏳ لي راهم يستناو:\n\n"
    for i, appointment in enumerate(waiting_appointments, 1):
        message += f"{i}. {appointment[1]} - {appointment[3]} - رقم: {appointment[6]}\n"
    await update.message.reply_text(message)

async def view_done_bookings(update: Update, context):
    done_appointments = sheets_service.get_done_bookings()
    if not done_appointments:
        await update.message.reply_text("ما كاين حتى واحد خلص")
        return

    message = "✅ لي خلصو:\n\n"
    for i, appointment in enumerate(done_appointments, 1):
        message += f"{i}. {appointment[1]} - {appointment[3]} - رقم: {appointment[6]}\n"
    await update.message.reply_text(message)

async def view_barber_bookings(update: Update, context):
    barber_name = BARBERS["barber_1"] if update.message.text == BTN_VIEW_BARBER1 else BARBERS["barber_2"]
    barber_appointments = sheets_service.get_barber_bookings(barber_name)
    
    if not barber_appointments:
        await update.message.reply_text(f"ما كاين حتى واحد مع {barber_name}")
        return

    message = f"👤 زبائن {barber_name}:\n\n"
    for i, appointment in enumerate(barber_appointments, 1):
        status = "⏳ يستنا" if appointment[5] == "Waiting" else "✅ خلص"
        message += f"{i}. {appointment[1]} - {status} - رقم: {appointment[6]}\n"
    await update.message.reply_text(message)

async def handle_status_change(update: Update, context):
    query = update.callback_query
    await query.answer()
    row_index = int(query.data.split('_')[1])
    sheets_service.update_booking_status(row_index, "Done")
    await query.edit_message_text("✅ تم تغيير الحالة")

async def handle_delete_booking(update: Update, context):
    query = update.callback_query
    await query.answer()
    row_index = int(query.data.split('_')[1])
    sheets_service.delete_booking(row_index)
    await query.edit_message_text("❌ تم حذف الحجز")

async def handle_refresh(update: Update, context):
    await update.message.reply_text("🔄 تم تحديث البيانات")

async def check_queue(update: Update, context):
    user_id = str(update.message.chat_id)
    waiting_appointments = sheets_service.get_waiting_bookings()
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
            "❌ ما عندكش رندي فو."
        )
    elif user_position == 0:
        await update.message.reply_text("🎉 دورك توا!\n💈 روح للحلاق.")
    else:
        if user_position == 1:
            people_msg = "قدامك غير واحد"
        elif user_position == 2:
            people_msg = "قدامك زوج"
        else:
            people_msg = f"قدامك {user_position} ناس"
                
        await update.message.reply_text(
            f"📋 مرتبتك في لاشان: {user_position + 1}\n"
            f"👥 {people_msg}"
        )
            
async def estimated_wait_time(update: Update, context):
    waiting_appointments = sheets_service.get_waiting_bookings()
            total_waiting = len(waiting_appointments)
    
    if total_waiting == 0:
        await update.message.reply_text("ما كاين حتى واحد في لاشان. تقدر تحجز توا!")
    else:
        estimated_minutes = total_waiting * 10  # Assuming 10 minutes per appointment
        if estimated_minutes < 60:
            await update.message.reply_text(f"⏳ تقدير وقت الانتظار: {estimated_minutes} دقيقة")
        else:
            hours = estimated_minutes // 60
            minutes = estimated_minutes % 60
            await update.message.reply_text(f"⏳ تقدير وقت الانتظار: {hours} ساعة و {minutes} دقيقة")

async def check_and_notify_users(context):
    try:
        waiting_appointments = sheets_service.get_waiting_bookings()
        await notification_service.send_notifications(context, waiting_appointments)
    except Exception as e:
        logging.error(f"Error in check_and_notify_users: {str(e)}")

# Add these functions to handle button callbacks properly
async def book_appointment_callback(update: Update, context):
    await choose_barber(update, context)
    return SELECTING_BARBER

async def admin_callback(update: Update, context):
    await admin_panel(update, context)
    return ADMIN_VERIFICATION

async def add_callback(update: Update, context):
    await choose_barber(update, context)
    return SELECTING_BARBER

async def cancel_callback(update: Update, context):
    await cancel(update, context)
    return ConversationHandler.END

# Modify the main function to fix the event loop issue
def main():
    """Set up and run the bot."""
    # Get bot token from environment variable
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("No TELEGRAM_TOKEN found in environment variables")
        return
    
    # Create the Application
    application = Application.builder().token(token).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_BOOK_APPOINTMENT}$"), choose_barber))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_ADD}$"), choose_barber))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_QUEUE}$"), check_queue))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_CHECK_WAIT}$"), estimated_wait_time))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_WAITING}$"), view_waiting_bookings))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_DONE}$"), view_done_bookings))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_BARBER1}$"), view_barber_bookings))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_BARBER2}$"), view_barber_bookings))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_REFRESH}$"), handle_refresh))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Register conversation states
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name), group=1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone), group=2)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_admin_password), group=3)
    
    # Register callback handlers
    application.add_handler(CallbackQueryHandler(handle_status_change, pattern="^status_"))
    application.add_handler(CallbackQueryHandler(handle_delete_booking, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(barber_selection, pattern="^barber_"))

    # Initialize job queue for notifications
    if application.job_queue:
        application.job_queue.run_repeating(check_and_notify_users, interval=15, first=1)
        logger.info("Job queue initialized successfully")
        else:
        logger.error("Job queue not available")

    # Start the bot
    logger.info("Starting bot...")
    
    # Use the non-async method to start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    return application

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Error: {e}") 