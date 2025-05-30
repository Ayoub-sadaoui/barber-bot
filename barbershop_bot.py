import os
import logging
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import time

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
BTN_BOOK_APPOINTMENT = "✂️ دير رنديفو"
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
BTN_ADMIN = "👋 مرحبا بيك في لوحة التحكم"

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
        except Exception as e:
            logger.error(f"Error refreshing connection: {e}")
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
        """Update the status of a booking in the sheet."""
        self.refresh_connection()
        try:
            # Get all values to find the correct row
            all_values = self.sheet.get_all_values()
            logger.info(f"All values in sheet: {all_values}")
            logger.info(f"Looking for row with index {row_index}")
            
            # Find the row with matching ticket number
            for i, row in enumerate(all_values[1:], start=2):  # Skip header row
                logger.info(f"Checking row {i}: {row}")
                if str(row[6]) == str(row_index):  # Check ticket number column
                    logger.info(f"Found matching row at index {i}")
                    logger.info(f"Updating status to {status}")
                    self.sheet.update_cell(i, 6, status)  # Update status column
                    logger.info("Status updated successfully")
                    return True
            
            logger.error(f"No matching row found for ticket {row_index}")
        except Exception as e:
            logger.error(f"Error updating status: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            return False

    def delete_booking(self, row_index):
        """Delete a booking from the sheet."""
        self.refresh_connection()
        try:
            # Get all values to find the correct row
            all_values = self.sheet.get_all_values()
            logger.info(f"All values in sheet: {all_values}")
            logger.info(f"Looking for row with index {row_index}")
            
            # Find the row with matching ticket number
            for i, row in enumerate(all_values[1:], start=2):  # Skip header row
                logger.info(f"Checking row {i}: {row}")
                if str(row[6]) == str(row_index):  # Check ticket number column
                    logger.info(f"Found matching row at index {i}")
                    logger.info("Deleting row")
                    self.sheet.delete_rows(i)
                    logger.info("Row deleted successfully")
                    return True
            
            logger.error(f"No matching row found for ticket {row_index}")
            return False
        except Exception as e:
            logger.error(f"Error deleting booking: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            return False

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
        return time_diff < 300  # 5 minutes cooldown

    def clear_notifications_for_user(self, user_id: str):
        keys_to_remove = [key for key in self.notification_cache.keys() if key.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            del self.notification_cache[key]

    async def send_notifications(self, context, waiting_appointments):
        try:
            # Clean up old notifications
            current_user_ids = [appointment[0] for appointment in waiting_appointments]
            for key in list(self.notification_cache.keys()):
                user_id = key.split('_')[0]
                if user_id not in current_user_ids:
                    del self.notification_cache[key]
        
            # Send notifications to users
            for position, appointment in enumerate(waiting_appointments):
                user_id = appointment[0]
                user_name = appointment[1]
                barber = appointment[3]
                
                try:
                    # Notify user when it's their turn
                    if position == 0 and not self.was_recently_notified(user_id, "turn"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🎉 {user_name}، دورك توا!\n"
                                 f"روح لـ {barber}.\n"
                                 f"إذا ما جيتش في 5 دقايق، تقدر تخسر دورك."
                        )
                        self.save_notification_status(user_id, "turn")
                        logging.info(f"Sent turn notification to user {user_id}")
                    
                    # Notify user 10 minutes before their turn
                    elif position == 1 and not self.was_recently_notified(user_id, "10min"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔔 {user_name}! دورك قريب يجي مع {barber} في 10 دقايق.\n"
                                 f"ابدا تقرب للصالون باش ما تخسرش دورك."
                        )
                        self.save_notification_status(user_id, "10min")
                        logging.info(f"Sent 10-min warning to user {user_id}")
                    
                    # Notify user 20 minutes before their turn
                    elif position == 2 and not self.was_recently_notified(user_id, "20min"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔔 {user_name}! دورك قريب يجي مع {barber} في 20 دقيقة.\n"
                                 f"ابدا تقرب للصالون باش ما تخسرش دورك."
                        )
                        self.save_notification_status(user_id, "20min")
                        logging.info(f"Sent 20-min warning to user {user_id}")
                
                except Exception as e:
                    logging.error(f"Error sending notification to user {user_id}: {str(e)}")
        except Exception as e:
            logging.error(f"Error in send_notifications: {str(e)}")

# Initialize services
sheets_service = SheetsService()
notification_service = NotificationService()

# Handlers
async def start(update: Update, context):
    """Start the conversation and show available options."""
    logger.info(f"Start command received from user {update.message.chat_id}")
    user_id = str(update.message.chat_id)
    
    # Get user's active booking
    waiting_appointments = sheets_service.get_waiting_bookings()
    logger.info(f"Found {len(waiting_appointments)} waiting appointments")
    
    # Check if user has an active booking
    user_booking = None
    for booking in waiting_appointments:
        if booking[0] == user_id:
            user_booking = booking
            logger.info(f"Found active booking for user {user_id}: {booking}")
            break
    
    # Base keyboard
    keyboard = [
        [BTN_VIEW_QUEUE, BTN_BOOK_APPOINTMENT],
        [BTN_CHECK_WAIT]
    ]
    
    # Add management buttons if user has an active booking
    if user_booking:
        logger.info(f"Adding management buttons for user {user_id}")
        keyboard.append([BTN_DELETE, BTN_CHANGE_STATUS])
    else:
        logger.info(f"No active booking found for user {user_id}")
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 مرحبا بيك عند الحلاق!\n"
        "🤔 شنو تحب دير:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def cancel(update: Update, context):
    await update.message.reply_text("تم إلغاء الحجز. يمكنك حجز موعد جديد في أي وقت.")
    return ConversationHandler.END
    
async def check_existing_appointment(user_id: str) -> bool:
    """Check if user already has an active appointment."""
    waiting_appointments = sheets_service.get_waiting_bookings()
    return any(appointment[0] == user_id for appointment in waiting_appointments)

async def get_barber_queue(barber_name: str):
    """Get waiting appointments for a specific barber."""
    waiting_appointments = sheets_service.get_waiting_bookings()
    return [appointment for appointment in waiting_appointments if appointment[3] == barber_name]

async def get_position_and_wait_time(user_id: str, barber_name: str = None):
    """Get user's position and estimated wait time for a specific barber or all barbers."""
    if barber_name:
        waiting_appointments = await get_barber_queue(barber_name)
    else:
        waiting_appointments = sheets_service.get_waiting_bookings()
    
    position = next((i for i, row in enumerate(waiting_appointments) if row[0] == user_id), -1)
    
    if position == -1:
        return None, None
    
    # Calculate wait time based on number of people ahead (each person = 10 mins)
    wait_time = (position) * 10
    return position + 1, wait_time

async def choose_barber(update: Update, context):
    """Handle the initial appointment booking request."""
    logger.info(f"Book appointment button clicked by user {update.message.chat_id}")
    user_id = str(update.message.chat_id)
    
    # Check if this is an admin adding an appointment
    is_admin = update.message.text == BTN_ADD
    
    # If not admin, check for existing appointments
    if not is_admin and await check_existing_appointment(user_id):
        position, wait_time = await get_position_and_wait_time(user_id)
        if position and wait_time:
            hours = wait_time // 60
            minutes = wait_time % 60
            time_msg = f"{wait_time} دقيقة" if wait_time < 60 else f"{hours} ساعة و {minutes} دقيقة"
            
            await update.message.reply_text(
                f"❌ عندك رنديفو فايت.\n"
                f"🔢 مرتبتك في لاشان: {position}\n"
                f"⏳ وقت الانتظار المقدر: {time_msg}\n"
                "ما تقدرش دير رنديفو جديد حتى يخلص لي فايت."
            )
        else:
            await update.message.reply_text(
                "❌ عندك رنديفو فايت.\n"
                "ما تقدرش دير رنديفو جديد حتى يخلص لي فايت."
            )
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(f"👨‍💇‍♂️ {BARBERS['barber_1']}", callback_data="barber_1")],
        [InlineKeyboardButton(f"👨‍💇‍♂️ {BARBERS['barber_2']}", callback_data="barber_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💈 شوف منين تحب تحلق:",
        reply_markup=reply_markup
    )
    return SELECTING_BARBER
        
async def barber_selection(update: Update, context):
    """Handle the barber selection."""
    query = update.callback_query
    try:
        await query.answer()
        context.user_data["barber"] = BARBERS[query.data]
        await query.edit_message_text("✏️ كتب سميتك من فضلك:")
        return ENTERING_NAME
    except Exception as e:
        logger.error(f"Error in barber_selection: {e}")
        await query.edit_message_text("❌ عندنا مشكل. حاول مرة أخرى.")
        return ConversationHandler.END

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
    
    # Get current bookings to generate next ticket number
    all_bookings = sheets_service.get_all_bookings()
    ticket_number = len(all_bookings)  # This will be 1 for the first booking

    booking_data = [user_id, name, phone, barber, datetime.now().strftime("%Y-%m-%d %H:%M"), "Waiting", str(ticket_number)]
    sheets_service.append_booking(booking_data)
    
    # Get position and estimated wait time
    position, wait_time = await get_position_and_wait_time(user_id, barber)
    hours = wait_time // 60 if wait_time else 0
    minutes = wait_time % 60 if wait_time else 0
    time_msg = f"{wait_time} دقيقة" if wait_time and wait_time < 60 else f"{hours} ساعة و {minutes} دقيقة"
                
    await update.message.reply_text(
        f"✅ تم حجز موعدك!\n"
        f"🎫 رقم تيكيتك: {ticket_number}\n"
        f"💇‍♂️ الحلاق: {barber}\n"
        f"🔢 مرتبتك في لاشان: {position}\n"
        f"⏳ وقت الانتظار المقدر: {time_msg}\n\n"
        f"يمكنك إدارة حجزك من القائمة الرئيسية باستخدام الأزرار:"
        f"\n❌ امسح الحجز - لحذف الحجز"
        f"\n✅ خلاص - لتحديث حالة الحجز"
    )
    return ConversationHandler.END

async def handle_delete_request(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    # Extract ticket number from callback data
    ticket_number = query.data.replace("delete_booking_", "")
    
    try:
        # Delete the booking
        await sheets_service.delete_booking(ticket_number)
        
        # Update the message to show it was deleted
        await query.edit_message_text(
            f"✅ تم حذف الرنديفو رقم {ticket_number} بنجاح",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 تحديث", callback_data="view_all_queues")
            ]])
        )
    except Exception as e:
        logger.error(f"Error deleting booking: {str(e)}")
        await query.edit_message_text(
            "❌ حدث خطأ أثناء حذف الرنديفو. حاول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 تحديث", callback_data="view_all_queues")
            ]])
        )

async def handle_done_request(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    # Extract ticket number from callback data
    ticket_number = query.data.replace("done_booking_", "")
    
    try:
        # Update the booking status to done
        await sheets_service.update_booking_status(ticket_number, "تم")
        
        # Update the message to show it was marked as done
        await query.edit_message_text(
            f"✅ تم تأكيد انتهاء الرنديفو رقم {ticket_number}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 تحديث", callback_data="view_all_queues")
            ]])
        )
    except Exception as e:
        logger.error(f"Error marking booking as done: {str(e)}")
        await query.edit_message_text(
            "❌ حدث خطأ أثناء تأكيد انتهاء الرنديفو. حاول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 تحديث", callback_data="view_all_queues")
            ]])
        )

async def is_admin(user_id: str, context) -> bool:
    """Check if user is an admin."""
    return context.user_data.get('is_admin', False)

async def admin_panel(update: Update, context):
    """Handle the admin panel request."""
    logger.info(f"Admin panel requested by user {update.message.chat_id}")
    
    # Check if user is already authenticated as admin
    if await is_admin(str(update.message.chat_id), context):
        keyboard = [
            [BTN_VIEW_WAITING, BTN_VIEW_DONE],
            [BTN_VIEW_BARBER1, BTN_VIEW_BARBER2],
            [BTN_ADD, BTN_REFRESH]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "👋 مرحبا بيك في لوحة التحكم:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    # If not authenticated, ask for password
    await update.message.reply_text("🔐 كتب كلمة السر:")
    return ADMIN_VERIFICATION

async def verify_admin_password(update: Update, context):
    """Verify the admin password and show admin panel if correct."""
    logger.info(f"Password verification attempt by user {update.message.chat_id}")
    
    if update.message.text == ADMIN_PASSWORD:
        # Set admin status in user_data
        context.user_data['is_admin'] = True
        logger.info(f"Successful admin login by user {update.message.chat_id}")
        
        keyboard = [
            [BTN_VIEW_WAITING, BTN_VIEW_DONE],
            [BTN_VIEW_BARBER1, BTN_VIEW_BARBER2],
            [BTN_ADD, BTN_REFRESH]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "👋 مرحبا بيك في لوحة التحكم:",
            reply_markup=reply_markup
        )
    else:
        logger.warning(f"Failed password attempt by user {update.message.chat_id}")
        await update.message.reply_text("❌ كلمة السر ماشي صحيحة.")
    
    return ConversationHandler.END

async def view_waiting_bookings(update: Update, context):
    """Show waiting appointments with management options."""
    # Check if user is admin
    if not await is_admin(str(update.message.chat_id), context):
        await update.message.reply_text("❌ ما عندكش الصلاحيات باش تشوف هاد الصفحة.")
        return
    
    waiting_appointments = sheets_service.get_waiting_bookings()
    if not waiting_appointments:
        await update.message.reply_text("ما كاين حتى واحد في لاشان")
        return
        
    # Send header message
    await update.message.reply_text("📋 لاشان الانتظار:")
    
    # Send each appointment as a separate message with its own buttons
    for i, appointment in enumerate(waiting_appointments, 1):
        # Format the appointment details
        message = f"📍 المرتبة: {i}\n"
        message += f"👤 الاسم: {appointment[1]}\n"
        message += f"💇‍♂️ الحلاق: {appointment[3]}\n"
        message += f"🎫 رقم التذكرة: {appointment[6]}"
        
        # Create keyboard for this appointment
        keyboard = [
            [
                InlineKeyboardButton(f"✅ خلاص", callback_data=f"status_{appointment[6]}"),
                InlineKeyboardButton(f"❌ امسح", callback_data=f"delete_{appointment[6]}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message with buttons
        await update.message.reply_text(message, reply_markup=reply_markup)
    
    # Add refresh button at the bottom
    refresh_keyboard = [[InlineKeyboardButton("🔄 شارجي", callback_data="refresh_waiting")]]
    refresh_markup = InlineKeyboardMarkup(refresh_keyboard)
    await update.message.reply_text("──────────────", reply_markup=refresh_markup)

async def view_done_bookings(update: Update, context):
    if not await is_admin(str(update.message.chat_id), context):
        await update.message.reply_text("❌ ما عندكش الصلاحيات باش تشوف هاد الصفحة.")
        return
    
    done_appointments = sheets_service.get_done_bookings()
    if not done_appointments:
        await update.message.reply_text("ما كاين حتى واحد خلص")
        return

    # Send header message
    await update.message.reply_text("✅ لي خلصو:")

    # Send each completed appointment with a delete button
    for i, appointment in enumerate(done_appointments, 1):
        message = f"{i}. {appointment[1]} - {appointment[3]} - رقم: {appointment[6]}"
        
        # Create keyboard with delete button
        keyboard = [[InlineKeyboardButton(f"❌ امسح", callback_data=f"delete_done_{appointment[6]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
            
        # Send message with delete button
        await update.message.reply_text(message, reply_markup=reply_markup)

async def view_barber_bookings(update: Update, context):
    if not await is_admin(str(update.message.chat_id), context):
        await update.message.reply_text("❌ ما عندكش الصلاحيات باش تشوف هاد الصفحة.")
        return
    
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
    
    # Check if user is admin
    if not await is_admin(str(query.from_user.id), context):
        await query.edit_message_text("❌ ما عندكش الصلاحيات باش تغير الحالة.")
        return
    
    try:
        # Extract ticket number from callback data
        ticket_number = int(query.data.split('_')[1])
        logger.info(f"Attempting to change status for ticket {ticket_number}")
        logger.info(f"Callback data: {query.data}")
        
        # Update the status in the sheet
        if sheets_service.update_booking_status(ticket_number, "Done"):
            logger.info("Status change successful")
            # Show success message
            await query.edit_message_text("✅ تم تغيير الحالة بنجاح")
            
            # Refresh the waiting list
            await view_waiting_bookings(update, context)
        else:
            logger.error("Failed to update status in sheet")
            await query.edit_message_text("❌ عندنا مشكل في تغيير الحالة. حاول مرة أخرى.")
        
    except Exception as e:
        logger.error(f"Error in handle_status_change: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        await query.edit_message_text("❌ عندنا مشكل. حاول مرة أخرى.")

async def handle_delete_booking(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    # Check if user is admin
    if not await is_admin(str(query.from_user.id), context):
        await query.edit_message_text("❌ ما عندكش الصلاحيات باش تمسح الحجز.")
        return
    
    try:
        # Extract ticket number from callback data
        callback_data = query.data
        logger.info(f"Received callback data: {callback_data}")
        
        if not callback_data.startswith("delete_"):
            logger.error(f"Invalid callback data format: {callback_data}")
            await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
            return
        
        try:
            ticket_number = int(callback_data.split("_")[1])
            logger.info(f"Attempting to delete ticket {ticket_number}")
            
            # Delete the booking from the sheet
            if sheets_service.delete_booking(ticket_number):
                logger.info("Booking deletion successful")
                # Show success message
                await query.edit_message_text("✅ تم حذف الحجز بنجاح")
                
                # Refresh the waiting list
                await view_waiting_bookings(update, context)
            else:
                logger.error("Failed to delete booking from sheet")
                await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
        except (IndexError, ValueError) as e:
            logger.error(f"Error extracting ticket number: {e}")
            await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
        
    except Exception as e:
        logger.error(f"Error in handle_delete_booking: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        await query.edit_message_text("❌ عندنا مشكل. حاول مرة أخرى.")

async def handle_refresh(update: Update, context):
    await update.message.reply_text("🔄 تم تحديث البيانات")

async def check_queue(update: Update, context):
    # Create keyboard with queue options
    keyboard = [
        [InlineKeyboardButton("📋 شوف لاشان كامل", callback_data="view_all_queues")],
        [InlineKeyboardButton(f"💇‍♂️ شوف لاشان {BARBERS['barber_1']}", callback_data=f"view_queue_{BARBERS['barber_1']}")],
        [InlineKeyboardButton(f"💇‍♂️ شوف لاشان {BARBERS['barber_2']}", callback_data=f"view_queue_{BARBERS['barber_2']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📋 شوف لاشان الحلاقين:",
        reply_markup=reply_markup
    )

async def handle_queue_view(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    
    if data == "view_all_queues":
        # Show both queues
        barber1_queue = await get_barber_queue(BARBERS['barber_1'])
        barber2_queue = await get_barber_queue(BARBERS['barber_2'])
        
        message = "📋 لاشان الحلاقين:\n\n"
        
        # Show queue for Barber 1
        message += f"💇‍♂️ {BARBERS['barber_1']}:\n"
        if not barber1_queue:
            message += "ما كاين حتى واحد في لاشان\n"
        else:
            for i, appointment in enumerate(barber1_queue, 1):
                status = "👤" if appointment[0] == user_id else "⏳"
                message += f"{i}. {status} {appointment[1]} - رقم: {appointment[6]}\n"
        
        message += "\n"
        
        # Show queue for Barber 2
        message += f"💇‍♂️ {BARBERS['barber_2']}:\n"
        if not barber2_queue:
            message += "ما كاين حتى واحد في لاشان\n"
        else:
            for i, appointment in enumerate(barber2_queue, 1):
                status = "👤" if appointment[0] == user_id else "⏳"
                message += f"{i}. {status} {appointment[1]} - رقم: {appointment[6]}\n"
        
        # Add user's position and wait time if they have an appointment
        position1, wait_time1 = await get_position_and_wait_time(user_id, BARBERS['barber_1'])
        position2, wait_time2 = await get_position_and_wait_time(user_id, BARBERS['barber_2'])
        
        if position1 is not None:
            hours1 = wait_time1 // 60
            minutes1 = wait_time1 % 60
            time_msg1 = f"{wait_time1} دقيقة" if wait_time1 < 60 else f"{hours1} ساعة و {minutes1} دقيقة"
            message += f"\n🔢 مرتبتك مع {BARBERS['barber_1']}: {position1}\n"
            message += f"⏳ وقت الانتظار: {time_msg1}\n"
        
        if position2 is not None:
            hours2 = wait_time2 // 60
            minutes2 = wait_time2 % 60
            time_msg2 = f"{wait_time2} دقيقة" if wait_time2 < 60 else f"{hours2} ساعة و {minutes2} دقيقة"
            message += f"\n🔢 مرتبتك مع {BARBERS['barber_2']}: {position2}\n"
            message += f"⏳ وقت الانتظار: {time_msg2}\n"
        
        if position1 is None and position2 is None:
            message += "\n❌ ما عندكش رنديفو."
    else:
        # Show specific barber's queue
        barber_name = data.replace("view_queue_", "")
        barber_queue = await get_barber_queue(barber_name)
        
        message = f"📋 لاشان {barber_name}:\n\n"
        if not barber_queue:
            message += "ما كاين حتى واحد في لاشان\n"
        else:
            for i, appointment in enumerate(barber_queue, 1):
                status = "👤" if appointment[0] == user_id else "⏳"
                message += f"{i}. {status} {appointment[1]} - رقم: {appointment[6]}\n"
        
        # Add user's position and wait time if they have an appointment
        position, wait_time = await get_position_and_wait_time(user_id, barber_name)
        if position is not None:
            hours = wait_time // 60
            minutes = wait_time % 60
            time_msg = f"{wait_time} دقيقة" if wait_time < 60 else f"{hours} ساعة و {minutes} دقيقة"
            message += f"\n🔢 مرتبتك: {position}\n"
            message += f"⏳ وقت الانتظار: {time_msg}\n"
        else:
            message += "\n❌ ما عندكش رنديفو مع هذا الحلاق."
    
    await query.edit_message_text(message)

async def estimated_wait_time(update: Update, context):
    user_id = str(update.message.chat_id)
    
    # Get queues for both barbers
    barber1_queue = await get_barber_queue(BARBERS['barber_1'])
    barber2_queue = await get_barber_queue(BARBERS['barber_2'])
    
    message = "⏳ وقت الانتظار:\n\n"
    
    # Show wait times for Barber 1
    message += f"💇‍♂️ {BARBERS['barber_1']}:\n"
    if not barber1_queue:
        message += "ما كاين حتى واحد في لاشان\n"
    else:
        for i, appointment in enumerate(barber1_queue, 1):
            wait_time = (i - 1) * 10
            hours = wait_time // 60
            minutes = wait_time % 60
            time_msg = f"{wait_time} دقيقة" if wait_time < 60 else f"{hours} ساعة و {minutes} دقيقة"
            status = "👤" if appointment[0] == user_id else "⏳"
            message += f"{i}. {status} {appointment[1]} - وقت الانتظار: {time_msg}\n"
    
    message += "\n"
    
    # Show wait times for Barber 2
    message += f"💇‍♂️ {BARBERS['barber_2']}:\n"
    if not barber2_queue:
        message += "ما كاين حتى واحد في لاشان\n"
    else:
        for i, appointment in enumerate(barber2_queue, 1):
            wait_time = (i - 1) * 10
            hours = wait_time // 60
            minutes = wait_time % 60
            time_msg = f"{wait_time} دقيقة" if wait_time < 60 else f"{hours} ساعة و {minutes} دقيقة"
            status = "👤" if appointment[0] == user_id else "⏳"
            message += f"{i}. {status} {appointment[1]} - وقت الانتظار: {time_msg}\n"
    
    await update.message.reply_text(message)

async def check_and_notify_users(context):
    try:
        waiting_appointments = sheets_service.get_waiting_bookings()
        await notification_service.send_notifications(context, waiting_appointments)
    except Exception as e:
        logging.error(f"Error in check_and_notify_users: {str(e)}")

# Add these functions to handle button callbacks properly
async def handle_booking_button(update: Update, context):
    """Handle the booking button click."""
    logger.info(f"Booking button clicked by user {update.message.chat_id}")
    try:
        return await choose_barber(update, context)
    except Exception as e:
        logger.error(f"Error handling booking button: {e}")
        await update.message.reply_text("❌ عندنا مشكل. حاول مرة أخرى.")
        return ConversationHandler.END

async def admin_callback(update: Update, context):
    await admin_panel(update, context)
    return ADMIN_VERIFICATION

async def add_callback(update: Update, context):
    await choose_barber(update, context)
    return SELECTING_BARBER

async def cancel_callback(update: Update, context):
    await cancel(update, context)
    return ConversationHandler.END

async def handle_delete_done_booking(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    # Check if user is admin
    if not await is_admin(str(query.from_user.id), context):
        await query.edit_message_text("❌ ما عندكش الصلاحيات باش تمسح الحجز.")
        return
    
    try:
        # Extract ticket number from callback data
        callback_data = query.data
        logger.info(f"Received callback data: {callback_data}")
        
        if not callback_data.startswith("delete_done_"):
            logger.error(f"Invalid callback data format: {callback_data}")
            await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
            return
        
        try:
            ticket_number = int(callback_data.split("_")[2])
            logger.info(f"Attempting to delete done ticket {ticket_number}")
            
            # Delete the booking from the sheet
            if sheets_service.delete_booking(ticket_number):
                logger.info("Done booking deletion successful")
                # Show success message
                await query.edit_message_text("✅ تم حذف الحجز بنجاح")
                
                # Refresh the done list
                await view_done_bookings(update, context)
            else:
                logger.error("Failed to delete done booking from sheet")
                await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
        except (IndexError, ValueError) as e:
            logger.error(f"Error extracting ticket number: {e}")
            await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
        
    except Exception as e:
        logger.error(f"Error in handle_delete_done_booking: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        await query.edit_message_text("❌ عندنا مشكل. حاول مرة أخرى.")

async def handle_delete_confirmation(update: Update, context):
    """Handle the confirmation of booking deletion."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract ticket number from callback data
        callback_data = query.data
        logger.info(f"Received callback data: {callback_data}")
        
        if not callback_data.startswith(("confirm_delete_", "cancel_delete_")):
            logger.error(f"Invalid callback data format: {callback_data}")
            await query.edit_message_text("❌ عندنا مشكل. حاول مرة أخرى.")
            return
            
        try:
            ticket_number = int(callback_data.split("_")[2])
            logger.info(f"Processing deletion for ticket {ticket_number}")
            
            if callback_data.startswith("confirm_delete_"):
                # Delete the booking from the sheet
                if sheets_service.delete_booking(ticket_number):
                    logger.info(f"Successfully deleted ticket {ticket_number}")
                    # Show success message
                    await query.edit_message_text("✅ تم حذف حجزك بنجاح")
                    # Refresh the menu to remove the buttons
                    await start(update, context)
                else:
                    logger.error(f"Failed to delete ticket {ticket_number}")
                    await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
            else:
                # User cancelled the deletion
                logger.info(f"User cancelled deletion for ticket {ticket_number}")
                await query.edit_message_text("تم إلغاء عملية الحذف")
                
        except (IndexError, ValueError) as e:
            logger.error(f"Error extracting ticket number: {e}")
            await query.edit_message_text("❌ عندنا مشكل في حذف الحجز. حاول مرة أخرى.")
            
    except Exception as e:
        logger.error(f"Error in handle_delete_confirmation: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        await query.edit_message_text("❌ عندنا مشكل. حاول مرة أخرى.")

# Modify the main function to fix the event loop issue
def main():
    """Set up and run the bot."""
    try:
        # Get bot token from environment variable
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            logger.error("No TELEGRAM_TOKEN found in environment variables")
            return None
        
        # Create the Application with proper error handling
        application = Application.builder().token(token).build()

        # Create admin conversation handler
        admin_handler = ConversationHandler(
            entry_points=[
                CommandHandler("admin", admin_panel),
                MessageHandler(filters.Text([BTN_ADMIN]), admin_panel)
            ],
            states={
                ADMIN_VERIFICATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, verify_admin_password)
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            name="admin_conversation",
            persistent=False
        )

        # Create booking conversation handler
        booking_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Text([BTN_BOOK_APPOINTMENT]), handle_booking_button)
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
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            name="booking_conversation",
            persistent=False
        )

        # Register handlers in the correct order
        application.add_handler(CommandHandler("start", start))
        
        # Add admin button handlers first (before the conversation handlers)
        application.add_handler(MessageHandler(filters.Text([BTN_VIEW_WAITING]), view_waiting_bookings))
        application.add_handler(MessageHandler(filters.Text([BTN_VIEW_DONE]), view_done_bookings))
        application.add_handler(MessageHandler(filters.Text([BTN_VIEW_BARBER1, BTN_VIEW_BARBER2]), view_barber_bookings))
        application.add_handler(MessageHandler(filters.Text([BTN_ADD]), choose_barber))
        application.add_handler(MessageHandler(filters.Text([BTN_REFRESH]), handle_refresh))
        
        # Add conversation handlers
        application.add_handler(admin_handler)
        application.add_handler(booking_handler)
        
        # Add regular command handlers
        application.add_handler(MessageHandler(filters.Text([BTN_VIEW_QUEUE]), check_queue))
        application.add_handler(MessageHandler(filters.Text([BTN_CHECK_WAIT]), estimated_wait_time))
        
        # Add callback query handlers
        application.add_handler(CallbackQueryHandler(handle_status_change, pattern="^status_"))
        application.add_handler(CallbackQueryHandler(handle_delete_booking, pattern="^delete_[0-9]+$"))
        application.add_handler(CallbackQueryHandler(handle_queue_view, pattern="^view_(all_queues|queue_)"))
        application.add_handler(CallbackQueryHandler(handle_delete_done_booking, pattern="^delete_done_[0-9]+$"))
        application.add_handler(CallbackQueryHandler(handle_delete_request, pattern="^delete_booking_"))
        application.add_handler(CallbackQueryHandler(handle_done_request, pattern="^done_booking_"))
        application.add_handler(CallbackQueryHandler(handle_queue_view, pattern="^view_queue_|^view_all_queues$"))

        # Initialize job queue for notifications with 1-minute interval
        if application.job_queue:
            application.job_queue.run_repeating(check_and_notify_users, interval=60, first=1)
            logger.info("Job queue initialized successfully")
        else:
            logger.error("Job queue not available")

        # Start the bot with proper error handling for Railway
        logger.info("Starting bot on Railway...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )
        
        return application
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return None

if __name__ == '__main__':
    # For Railway deployment, we want to keep the process running
    # and handle restarts gracefully
    while True:
        try:
            logger.info("Starting bot process...")
            app = main()
            if app is None:
                logger.error("Bot failed to start, waiting before retry...")
                time.sleep(30)  # Wait 30 seconds before retrying
                continue
        except KeyboardInterrupt:
            logger.info("Bot stopped by user!")
            break
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            time.sleep(30)  # Wait 30 seconds before retrying
            continue 