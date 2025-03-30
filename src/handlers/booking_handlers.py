import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes as CallbackContext, ConversationHandler
from src.config.config import (
    SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE,
    ADMIN_ID, BARBERS, BTN_BOOK_APPOINTMENT, APPOINTMENT_DURATION_MINUTES
)
from src.utils.validators import is_valid_name, is_valid_phone
from src.utils.formatters import format_wait_time, get_estimated_completion_time
from src.services.sheets_service import SheetsService
from src.services.notification_service import NotificationService

sheets_service = SheetsService()
notification_service = NotificationService()

async def choose_barber(update: Update, context: CallbackContext) -> int:
    """Handle the initial booking request and check if user already has an appointment"""
    user_id = str(update.message.chat_id)
    
    # Check if user already has an active appointment
    if sheets_service.has_active_appointment(user_id):
        # Check if the appointment is still waiting
        if sheets_service.get_appointment_status(user_id) == "Waiting":
            await update.message.reply_text("❌ عندك رنديفو موجود. لازم تكملو قبل ما دير واحد جديد.")
            return ConversationHandler.END

    # Create keyboard with barber options
    keyboard = [
        [InlineKeyboardButton(BARBERS['barber_1'], callback_data="barber_1")],
        [InlineKeyboardButton(BARBERS['barber_2'], callback_data="barber_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("💇‍♂️ اختر الحلاق:", reply_markup=reply_markup)
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