import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes as CallbackContext, ConversationHandler
from src.config.config import (
    SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE,
    ADMIN_ID, BARBERS, BTN_BOOK_APPOINTMENT, APPOINTMENT_DURATION_MINUTES,
    SUPER_ADMIN_PASSWORD, ADMIN_VERIFICATION, BTN_VIEW_QUEUE,
    BTN_CHECK_WAIT, BTN_VIEW_WAITING, BTN_VIEW_DONE,
    BTN_VIEW_BARBER1, BTN_VIEW_BARBER2, BTN_CHANGE_STATUS,
    BTN_DELETE, BTN_ADD, BTN_REFRESH
)
from src.utils.validators import is_valid_name, is_valid_phone
from src.utils.formatters import format_wait_time, get_estimated_completion_time
from src.services.sheets_service import SheetsService
from src.services.notification_service import NotificationService
import time
from telegram.warnings import PTBUserWarning
from warnings import filterwarnings
import json
import os
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from typing import Dict
from src.services.barber_shop_service import BarberShopService

sheets_service = SheetsService()
notification_service = NotificationService()
barber_shop_service = BarberShopService()

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext):
    """Handle the /start command"""
    # Check if this is a shop-specific start
    if context.args and context.args[0].startswith('shop_'):
        shop_name = context.args[0].replace('shop_', '')
        shop = barber_shop_service.get_shop(shop_name)
        if shop:
            context.user_data['current_shop'] = shop_name
            keyboard = [
                ["📅 دير رنديفو", "📋 شوف لاشان"],
                ["⏳ شحال باقي"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                f"مرحباً بيك عند {shop_name}! اختر ما تريد القيام به:",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
    
    # Show list of available shops
    shops = barber_shop_service.get_all_shops()
    if not shops:
        await update.message.reply_text("عذراً، لا توجد محلات متاحة حالياً.")
        return ConversationHandler.END
    
    message = "👋 مرحباً بك! اختر المحل الذي تريد الحجز فيه:\n\n"
    keyboard = []
    for shop in shops:
        keyboard.append([InlineKeyboardButton(shop, callback_data=f"select_shop_{shop}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_shop_selection(update: Update, context: CallbackContext):
    """Handle shop selection from the list"""
    query = update.callback_query
    await query.answer()
    
    shop_name = query.data.replace("select_shop_", "")
    shop = barber_shop_service.get_shop(shop_name)
    
    if shop:
        context.user_data['current_shop'] = shop_name
        keyboard = [
            ["📅 دير رنديفو", "📋 شوف لاشان"],
            ["⏳ شحال باقي"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.message.reply_text(
            f"تم اختيار محل {shop_name}. اختر ما تريد القيام به:",
            reply_markup=reply_markup
        )
    else:
        await query.message.reply_text("عذراً، حدث خطأ في اختيار المحل. حاول مرة أخرى.")
    
    return ConversationHandler.END

async def choose_barber(update: Update, context: CallbackContext) -> int:
    """Handle the booking appointment button"""
    if 'current_shop' not in context.user_data:
        await update.message.reply_text("الرجاء اختيار محل أولاً.")
        return ConversationHandler.END
    
    shop_name = context.user_data['current_shop']
    shop = barber_shop_service.get_shop(shop_name)
    if not shop:
        await update.message.reply_text("عذراً، حدث خطأ في اختيار المحل. حاول مرة أخرى.")
        return ConversationHandler.END
    
    barbers = shop.get('barbers', {})
    if not barbers:
        await update.message.reply_text("عذراً، لا يوجد حلاقين متاحين حالياً.")
        return ConversationHandler.END
    
    keyboard = []
    for barber_id, barber_name in barbers.items():
        keyboard.append([InlineKeyboardButton(barber_name, callback_data=f"barber_{barber_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر الحلاق:", reply_markup=reply_markup)
    return SELECTING_BARBER

async def barber_selection(update: Update, context: CallbackContext) -> int:
    """Handle barber selection"""
    query = update.callback_query
    await query.answer()
    
    # Extract the selected barber
    barber_choice = query.data.split('_')[1]
    barber_name = BARBERS[f'barber_{barber_choice}']
    
    # Save the selected barber in user_data
    context.user_data['barber'] = barber_name
    
    await query.message.reply_text(f"✅ اخترت {barber_name}. الآن، من فضلك أدخل اسمك الكامل:")
    return ENTERING_NAME

async def handle_name(update: Update, context: CallbackContext) -> int:
    """Handle name input"""
    name = update.message.text.strip()
    
    # Basic name validation
    if len(name) < 3 or len(name) > 50:
        await update.message.reply_text("❌ من فضلك أدخل اسمًا صالحًا (بين 3 و 50 حرفًا).")
        return ENTERING_NAME
    
    # Save the name in user_data
    context.user_data['name'] = name
    
    await update.message.reply_text(f"👤 شكرًا {name}. الآن، من فضلك أدخل رقم هاتفك:")
    return ENTERING_PHONE

async def handle_phone(update: Update, context: CallbackContext) -> int:
    """Handle phone number input"""
    phone = update.message.text.strip()
    
    # Basic phone validation
    if not re.match(r'^\d{8,15}$', phone):
        await update.message.reply_text("❌ من فضلك أدخل رقم هاتف صالح (8-15 رقمًا).")
        return ENTERING_PHONE
    
    try:
        # Get data from context
        name = context.user_data.get('name')
        barber = context.user_data.get('barber')
        user_id = str(update.message.chat_id)
        
        # Generate a ticket number
        ticket_number = sheets_service.generate_ticket_number()
        
        # Prepare data for the sheet
        booking_data = [
            user_id,       # User ID
            name,          # Name
            phone,         # Phone
            barber,        # Barber
            ticket_number, # Ticket
            "Waiting"      # Status
        ]
        
        # Append to Google Sheet
        sheets_service.append_booking(booking_data)
        
        # Calculate position in queue
        queue_position = 1  # Default position
        waiting_bookings = sheets_service.get_waiting_bookings()
        for i, booking in enumerate(waiting_bookings):
            if booking[0] == user_id and booking[3] == barber:
                queue_position = i + 1
                break
        
        # Send confirmation message with ticket details
        confirmation_message = (
            f"✅ *تم الحجز بنجاح!*\n\n"
            f"📋 *معلومات الرنديفو:*\n"
            f"👤 الاسم: {name}\n"
            f"📱 الهاتف: {phone}\n"
            f"💇‍♂️ الحلاق: {barber}\n"
            f"🎫 رقم التذكرة: {ticket_number}\n"
            f"🔢 ترتيبك في الصف: {queue_position}\n\n"
            f"⏰ سنرسل لك إشعارًا عندما يقترب دورك.\n"
            f"شكرًا لاختيارك خدماتنا! 🙏"
        )
        
        await update.message.reply_text(confirmation_message, parse_mode='Markdown')
        
        # Clean up context data
        context.user_data.pop('name', None)
        context.user_data.pop('barber', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"Error in handle_phone: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء حفظ الحجز. يرجى المحاولة مرة أخرى لاحقًا.")
        return ConversationHandler.END 

async def check_and_notify_users(context) -> None:
    """Periodically check queue and notify users of their turn"""
    start_time = time.time()
    try:
        logger.info("Starting notification check...")
        waiting_appointments = sheets_service.get_waiting_bookings()
        
        if waiting_appointments:
            logger.info(f"Found {len(waiting_appointments)} waiting appointments")
            await notification_service.send_notifications(context, waiting_appointments)
            logger.info(f"Successfully processed notifications")
        else:
            logger.info("No waiting appointments found")
    except Exception as e:
        logger.error(f"Error in check_and_notify_users: {str(e)}")
        # Clear cache to ensure fresh data on next check
        sheets_service.cache = {}
    finally:
        end_time = time.time()
        logger.info(f"Notification check completed in {end_time - start_time:.2f} seconds") 

class BarberShopService:
    def __init__(self):
        self.shops_file = "data/barber_shops.json"
        self._ensure_data_directory()
        self._load_shops()
        self.creds = Credentials.from_service_account_file('path/to/your/service_account.json')
        self.sheets_service = build('sheets', 'v4', credentials=self.creds)

    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        os.makedirs(os.path.dirname(self.shops_file), exist_ok=True)
        if not os.path.exists(self.shops_file):
            self._save_shops({})

    def _load_shops(self):
        """Load barber shops from file"""
        try:
            with open(self.shops_file, 'r', encoding='utf-8') as f:
                self.shops = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.shops = {}
            self._save_shops(self.shops)

    def _save_shops(self, shops: Dict):
        """Save barber shops to file"""
        with open(self.shops_file, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=4)

    def create_google_sheet(self, shop_name: str) -> str:
        """Create a new Google Sheet for the barber shop"""
        spreadsheet = {
            'properties': {
                'title': f"{shop_name} - Appointments"
            }
        }
        sheet = self.sheets_service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        return sheet.get('spreadsheetId')

    def add_shop(self, shop_name: str, admin_password: str) -> bool:
        """Add a new barber shop and create a Google Sheet"""
        if shop_name in self.shops:
            return False
        
        sheet_id = self.create_google_sheet(shop_name)
        self.shops[shop_name] = {
            "admin_password": admin_password,
            "sheet_id": sheet_id,
            "barbers": {}
        }
        self._save_shops(self.shops)
        return True

    # ... (rest of the class remains unchanged) 

async def handle_sheet_id(update: Update, context: CallbackContext):
    """Handle the Google Sheets ID input"""
    shop_name = context.user_data['shop_name']
    admin_password = SUPER_ADMIN_PASSWORD  # Use the super admin password
    sheet_id = barber_shop_service.create_google_sheet(shop_name)  # Create the sheet automatically

    if barber_shop_service.add_shop(shop_name, admin_password):
        await update.message.reply_text(f"تم إضافة محل {shop_name} بنجاح!")
    else:
        await update.message.reply_text("حدث خطأ أثناء إضافة المحل. حاول مرة أخرى.")
    
    return ConversationHandler.END 