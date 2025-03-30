import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from src.config.config import (
    ADMIN_ID, ADMIN_PASSWORD, ADMIN_VERIFICATION,
    BTN_VIEW_WAITING, BTN_VIEW_DONE, BTN_VIEW_BARBER1,
    BTN_VIEW_BARBER2, BTN_CHANGE_STATUS, BTN_DELETE,
    BTN_ADD, BTN_REFRESH, BARBERS
)
from src.services.sheets_service import SheetsService
from src.services.notification_service import NotificationService

sheets_service = SheetsService()
notification_service = NotificationService()

async def admin_panel(update: Update, context: CallbackContext) -> None:
    """Handle admin panel access request"""
    user_id = str(update.message.chat_id)
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ممنوع. هذا الأمر للمسؤول فقط.")
        return
    
    # Ask for password
    await update.message.reply_text("من فضلك أدخل كلمة السر للدخول إلى لوحة التحكم:")
    return ADMIN_VERIFICATION

async def verify_admin_password(update: Update, context: CallbackContext) -> int:
    """Verify admin password and show admin panel"""
    entered_password = update.message.text.strip()
    
    if entered_password == ADMIN_PASSWORD:
        # Store admin state in user_data
        context.user_data['is_admin'] = True
        
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
        return ADMIN_VERIFICATION

async def view_waiting_bookings(update: Update, context: CallbackContext) -> None:
    """View all waiting bookings"""
    if str(update.message.chat_id) != ADMIN_ID or not context.user_data.get('is_admin'):
        await update.message.reply_text("⛔ ممنوع. هذا الأمر للمسؤول فقط.")
        return

    try:
        waiting_bookings = sheets_service.get_waiting_bookings()

        if not waiting_bookings:
            await update.message.reply_text("ما كاين حتى واحد يستنى 🤷‍♂️")
            return

        for i, booking in enumerate(waiting_bookings, 1):
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

async def view_done_bookings(update: Update, context: CallbackContext) -> None:
    """View all completed bookings"""
    if str(update.message.chat_id) != ADMIN_ID:
        return

    try:
        done_bookings = sheets_service.get_done_bookings()

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
        message_text = update.message.text
        if BTN_VIEW_BARBER1 in message_text:
            barber_name = BARBERS['barber_1']
        elif BTN_VIEW_BARBER2 in message_text:
            barber_name = BARBERS['barber_2']
        else:
            await update.message.reply_text("❌ لم يتم تحديد الحلاق")
            return

        barber_bookings = sheets_service.get_barber_bookings(barber_name)
        
        if not barber_bookings:
            await update.message.reply_text(f"ما كاين حتى حجز مع {barber_name} 🤷‍♂️")
            return

        for i, booking in enumerate(barber_bookings, 1):
            status_emoji = "⏳" if booking[5] == "Waiting" else "✅"
            message = (f"{i}. {status_emoji} {booking[1]}\n"
                      f"   التيليفون: {booking[2]}\n"
                      f"   الوقت: {booking[4]}\n"
                      f"   التذكرة: {booking[6]}\n"
                      f"{'─' * 20}\n")
            
            if booking[5] == "Waiting":
                keyboard = [
                    [
                        InlineKeyboardButton("✅ خلاص", callback_data=f"status_{booking[0]}"),
                        InlineKeyboardButton("❌ امسح", callback_data=f"delete_{booking[0]}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, reply_markup=reply_markup)
            else:
                await update.message.reply_text(message)

    except Exception as e:
        logging.error(f"Error in view_barber_bookings: {str(e)}")
        await update.message.reply_text("كاين مشكل. عاود حاول.")

async def handle_status_change(update: Update, context: CallbackContext):
    """Handle status change button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract booking ID and new status from callback data
        _, booking_id, new_status = query.data.split('_')
        booking_id = int(booking_id)
        
        # Get current booking status
        current_status = sheets_service.get_booking_status(booking_id)
        
        if current_status == "Deleted":
            await query.message.reply_text("❌ لا يمكن تغيير حالة موعد محذوف!")
            return
            
        if current_status == "Done" and new_status == "Done":
            await query.message.reply_text("✅ هذا الموعد مكمل بالفعل!")
            return
            
        # Update status in sheet
        success = sheets_service.update_booking_status(booking_id, new_status)
        
        if success:
            status_emoji = "✅" if new_status == "Done" else "⏳" if new_status == "Waiting" else "❌"
            await query.message.reply_text(f"{status_emoji} تم تحديث حالة الموعد بنجاح!")
            
            # Refresh the view
            await view_waiting_bookings(update, context)
        else:
            await query.message.reply_text("❌ حدث خطأ أثناء تحديث حالة الموعد. حاول مرة أخرى.")
            
    except Exception as e:
        logging.error(f"Error in handle_status_change: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ غير متوقع. حاول مرة أخرى.")

async def handle_delete_booking(update: Update, context: CallbackContext):
    """Handle delete booking button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract booking ID from callback data
        _, booking_id = query.data.split('_')
        booking_id = int(booking_id)
        
        # Get current booking status
        current_status = sheets_service.get_booking_status(booking_id)
        
        if current_status == "Deleted":
            await query.message.reply_text("❌ هذا الموعد محذوف بالفعل!")
            return
            
        # Delete booking from sheet
        success = sheets_service.delete_booking(booking_id)
        
        if success:
            await query.message.reply_text("🗑️ تم حذف الموعد بنجاح!")
            
            # Refresh the view
            await view_waiting_bookings(update, context)
        else:
            await query.message.reply_text("❌ حدث خطأ أثناء حذف الموعد. حاول مرة أخرى.")
            
    except Exception as e:
        logging.error(f"Error in handle_delete_booking: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ غير متوقع. حاول مرة أخرى.")

async def handle_refresh(update: Update, context: CallbackContext) -> None:
    """Handle refreshing the admin panel"""
    if str(update.message.chat_id) != ADMIN_ID:
        return
    
    try:
        sheets_service.refresh_connection()
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