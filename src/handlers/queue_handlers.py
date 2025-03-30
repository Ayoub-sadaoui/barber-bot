import logging
from telegram import Update
from telegram.ext import CallbackContext
from src.config.config import (
    BTN_VIEW_QUEUE, BTN_CHECK_WAIT, APPOINTMENT_DURATION_MINUTES
)
from src.utils.formatters import format_wait_time, get_estimated_completion_time
from src.services.sheets_service import SheetsService

sheets_service = SheetsService()

async def check_queue(update: Update, context: CallbackContext) -> None:
    """Handle queue check request"""
    try:
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
    """Handle wait time estimation request"""
    try:
        user_id = str(update.message.chat_id)
        waiting_appointments = sheets_service.get_waiting_bookings()
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