import logging
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, ConversationHandler
from src.config.config import (
    SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE,
    BARBERS, BTN_BOOK_APPOINTMENT, APPOINTMENT_DURATION_MINUTES
)
from src.utils.validators import is_valid_name, is_valid_phone
from src.utils.formatters import format_wait_time, get_estimated_completion_time
from src.services.sheets_service import SheetsService
from src.services.notification_service import NotificationService

sheets_service = SheetsService()
notification_service = NotificationService()

async def choose_barber(update: Update, context: CallbackContext) -> int:
    """Handle the initial booking request"""
    logging.info(f"Booking button clicked. Message text: {update.message.text}")
    user_id = update.message.chat_id
    
    if sheets_service.has_active_appointment(user_id):
        await update.message.reply_text("❌ عندك رندي فو مازال ما كملش. لازم تستنى حتى يكمل قبل ما دير واحد اخر.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(name, callback_data=id)] for id, name in BARBERS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("شكون من حلاق تحب:", reply_markup=reply_markup)
    return SELECTING_BARBER

async def barber_selection(update: Update, context: CallbackContext) -> int:
    """Handle barber selection"""
    query = update.callback_query
    await query.answer()
    selected_barber = query.data.replace("barber_", "الحلاق ")
    context.user_data['barber'] = selected_barber
    await query.message.reply_text(
        f"اخترت {selected_barber}. من فضلك دخل اسمك الكامل:\n"
        "(الاسم لازم يكون بين 3 و 30 حرف)"
    )
    return ENTERING_NAME

async def handle_name(update: Update, context: CallbackContext) -> int:
    """Handle name input"""
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
    """Handle phone number input and complete booking"""
    user_id = update.message.chat_id
    phone = update.message.text.strip().replace(' ', '').replace('-', '')
    
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
        waiting_appointments = sheets_service.get_waiting_bookings()
        position = len(waiting_appointments)  # New position will be at the end
        ticket_number = sheets_service.generate_ticket_number()

        # Add the new booking to Google Sheets
        booking_data = [user_id, user_name, phone, selected_barber, 
                       time.strftime("%Y-%m-%d %H:%M:%S"), "Waiting", ticket_number]
        sheets_service.append_booking(booking_data)
        
        # Send confirmation message with position info
        if position == 0:
            await update.message.reply_text(
                f"✅ {user_name}، تسجل رونديفو مع {selected_barber}!\n"
                f"📱 رقم التيليفون: {phone}\n"
                f"🎟️ رقم التذكرة: {ticket_number}\n"
                "🎉 مبروك! راك الأول - دورك توا!"
            )
            notification_service.save_notification_status(str(user_id), "turn")
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