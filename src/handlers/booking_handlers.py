import logging
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, ConversationHandler
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
    """Handle the initial booking request"""
    user_id = str(update.message.chat_id)

    # Check if user already has an active appointment
    if sheets_service.has_active_appointment(user_id):
        await update.message.reply_text("❌ عندك رنديفو موجود. لازم تكملو قبل ما دير واحد جديد.")
        return ConversationHandler.END

    # Create inline keyboard with barber options
    keyboard = [[
        InlineKeyboardButton(BARBERS["barber_1"], callback_data="barber_1"),
        InlineKeyboardButton(BARBERS["barber_2"], callback_data="barber_2")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("اختار الحلاق لي تحب:", reply_markup=reply_markup)
    return SELECTING_BARBER

async def barber_selection(update: Update, context: CallbackContext) -> int:
    """Handle barber selection"""
    query = update.callback_query
    await query.answer()
    
    selected_barber = BARBERS[query.data]
    context.user_data['barber'] = selected_barber
    
    await query.message.reply_text("من فضلك دخل سميتك:")
    return ENTERING_NAME

async def handle_name(update: Update, context: CallbackContext) -> int:
    """Handle name input"""
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("من فضلك دخل سمية صحيحة (على الأقل حرفين).")
        return ENTERING_NAME
    
    context.user_data['name'] = name
    await update.message.reply_text("من فضلك دخل نمرة تيليفونك:")
    return ENTERING_PHONE

async def handle_phone(update: Update, context: CallbackContext) -> int:
    """Handle phone number input"""
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) < 8:
        await update.message.reply_text("من فضلك دخل نمرة تيليفون صحيحة.")
        return ENTERING_PHONE
    
    try:
        user_id = str(update.message.chat_id)
        name = context.user_data['name']
        barber = context.user_data['barber']
        current_time = update.message.date.strftime("%Y-%m-%d %H:%M:%S")
        ticket_number = sheets_service.generate_ticket_number()
        
        # Add booking to sheet
        booking_data = [user_id, name, phone, barber, current_time, "Waiting", ticket_number]
        sheets_service.append_booking(booking_data)
        
        # Send confirmation message
        await update.message.reply_text(
            f"✅ تم تسجيل رنديفو جديد:\n"
            f"الاسم: {name}\n"
            f"التيليفون: {phone}\n"
            f"الحلاق: {barber}\n"
            f"التذكرة: {ticket_number}\n\n"
            f"غادي نعيطو ليك مني يقرب دورك."
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"Error in handle_phone: {str(e)}")
        await update.message.reply_text("❌ كاين مشكل. عاود حاول.")
        return ConversationHandler.END 