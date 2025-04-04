import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes as CallbackContext, ConversationHandler
from src.config.config import (
    ADMIN_ID, ADMIN_PASSWORD, BTN_VIEW_WAITING, BTN_VIEW_DONE, BTN_VIEW_BARBER1, BTN_VIEW_BARBER2,
    BTN_ADD, BTN_REFRESH, ADMIN_VERIFICATION, BTN_CHANGE_STATUS, BTN_DELETE
)
from src.services.sheets_service import SheetsService
from src.services.notification_service import NotificationService
from src.services.barber_shop_service import BarberShopService

# Initialize services
sheets_service = SheetsService()
notification_service = NotificationService()
barber_shop_service = BarberShopService()

async def admin_panel(update: Update, context: CallbackContext) -> int:
    """Display admin panel and request password"""
    context.user_data['is_admin'] = False  # Reset admin status
    await update.message.reply_text("🔐 من فضلك أدخل كلمة المرور للدخول للوحة التحكم:")
    return 3  # ADMIN_VERIFICATION state

async def verify_admin_password(update: Update, context: CallbackContext) -> int:
    """Verify admin password"""
    if update.message.text == ADMIN_PASSWORD:
        context.user_data['is_admin'] = True
        keyboard = [
            ["📋 شوف اللايحة ديال الانتظار", "✅ شوف المكملين"],
            ["👨‍💼 الحلاق 1", "👨‍💼 الحلاق 2"],
            ["➕ زيد موعد", "🔄 تحديث"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("✅ تم تسجيل الدخول بنجاح! مرحبا بك في لوحة التحكم", reply_markup=reply_markup)
        # Set admin flag for use in other handlers
        context.user_data['is_admin'] = True
        return -1  # End conversation
    else:
        await update.message.reply_text("❌ كلمة المرور غير صحيحة. حاول مرة أخرى أو اكتب /cancel للإلغاء.")
        return 3  # Stay in ADMIN_VERIFICATION state

async def view_waiting_bookings(update: Update, context: CallbackContext) -> None:
    """Display waiting bookings"""
    # Refresh connection to ensure fresh data
    sheets_service.refresh_connection()
    
    try:
        waiting_bookings = sheets_service.get_waiting_bookings()
        
        if not waiting_bookings:
            await update.message.reply_text("📭 لا توجد حجوزات في الانتظار حاليا")
            return
        
        await update.message.reply_text("⌛️ الحجوزات قيد الانتظار:")
        
        for booking in waiting_bookings:
            booking_id = booking[0]
            name = booking[1]
            phone = booking[2]
            barber = booking[3]
            ticket = booking[4]
            
            # Create inline keyboard for actions
            keyboard = [
                [
                    InlineKeyboardButton("✅ تم", callback_data=f"status_{booking_id}_Done"),
                    InlineKeyboardButton("📞 اتصل", callback_data=f"call_{booking_id}_{phone}"),
                    InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_{booking_id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                f"🎫 رقم التذكرة: {ticket}\n"
                f"👤 الاسم: {name}\n"
                f"📱 الهاتف: {phone}\n"
                f"💇‍♂️ الحلاق: {barber}\n"
            )
            
            await update.message.reply_text(message, reply_markup=reply_markup)
            
    except Exception as e:
        logging.error(f"Error in view_waiting_bookings: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء عرض الحجوزات")

async def view_done_bookings(update: Update, context: CallbackContext) -> None:
    """Display completed bookings"""
    try:
        done_bookings = sheets_service.get_done_bookings()
        
        if not done_bookings:
            await update.message.reply_text("📭 لا توجد حجوزات مكتملة")
            return
        
        await update.message.reply_text("✅ الحجوزات المكتملة:")
        
        for booking in done_bookings[-10:]:  # Show last 10 done bookings
            booking_id = booking[0]
            name = booking[1]
            phone = booking[2]
            barber = booking[3]
            ticket = booking[4]
            
            message = (
                f"🎫 رقم التذكرة: {ticket}\n"
                f"👤 الاسم: {name}\n"
                f"📱 الهاتف: {phone}\n"
                f"💇‍♂️ الحلاق: {barber}\n"
                f"✅ الحالة: مكتمل\n"
            )
            
            await update.message.reply_text(message)
            
    except Exception as e:
        logging.error(f"Error in view_done_bookings: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء عرض الحجوزات المكتملة")

async def view_barber_bookings(update: Update, context: CallbackContext) -> None:
    """Display bookings for a specific barber"""
    try:
        barber_name = update.message.text.replace("👨‍💼 ", "")
        barber_bookings = sheets_service.get_barber_bookings(barber_name)
        
        if not barber_bookings:
            await update.message.reply_text(f"📭 لا توجد حجوزات لـ {barber_name}")
            return
        
        await update.message.reply_text(f"💇‍♂️ حجوزات {barber_name}:")
        
        for booking in barber_bookings:
            booking_id = booking[0]
            name = booking[1]
            phone = booking[2]
            ticket = booking[4]
            status = booking[5]
            
            # Create inline keyboard for waiting bookings
            reply_markup = None
            if status == "Waiting":
                keyboard = [
                    [
                        InlineKeyboardButton("✅ تم", callback_data=f"status_{booking_id}_Done"),
                        InlineKeyboardButton("📞 اتصل", callback_data=f"call_{booking_id}_{phone}"),
                        InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_{booking_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                f"🎫 رقم التذكرة: {ticket}\n"
                f"👤 الاسم: {name}\n"
                f"📱 الهاتف: {phone}\n"
                f"📊 الحالة: {status}\n"
            )
            
            await update.message.reply_text(message, reply_markup=reply_markup)
            
    except Exception as e:
        logging.error(f"Error in view_barber_bookings: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء عرض حجوزات الحلاق")

async def handle_call_customer(update: Update, context: CallbackContext):
    """Handle call customer button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract customer phone from callback data
        parts = query.data.split('_')
        booking_id = parts[1]
        phone = parts[2]
        
        # Generate a clickable telephone link
        await query.message.reply_text(
            f"📞 اتصل الآن بالرقم: +{phone}\n\n"
            f"[اضغط هنا للاتصال](tel:+{phone})",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logging.error(f"Error in handle_call_customer: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ أثناء محاولة الاتصال")

async def handle_status_change(update: Update, context: CallbackContext):
    """Handle status change button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract booking ID and new status from callback data
        parts = query.data.split('_')
        booking_id = parts[1]
        new_status = parts[2]
        
        # Find the row number for this booking
        all_bookings = sheets_service.get_all_bookings()
        row_num = None
        
        for i, row in enumerate(all_bookings[1:], start=2):  # Skip header row
            if row[0] == booking_id:
                row_num = i
                current_status = row[5]
                break
                
        if not row_num:
            await query.message.reply_text("❌ لم يتم العثور على الحجز")
            return
            
        if current_status == "Deleted":
            await query.message.reply_text("❌ لا يمكن تغيير حالة موعد محذوف!")
            return
            
        if current_status == "Done" and new_status == "Done":
            await query.message.reply_text("✅ هذا الموعد مكمل بالفعل!")
            return
            
        # Update the status
        sheets_service.update_cell(row_num, 6, new_status)  # Update status column (6)
        
        # Send confirmation
        status_emoji = "✅" if new_status == "Done" else "⏳" if new_status == "Waiting" else "❌"
        await query.message.reply_text(f"{status_emoji} تم تحديث حالة الموعد بنجاح!")
        
        # Refresh the view
        try:
            # Clear notification cache for this user if status changed to Done
            if new_status == "Done":
                notification_service.clear_notification_cache()
                
            # Try to refresh the view
            if "waiting" in query.message.text.lower():
                await view_waiting_bookings(update, context)
            elif "barber" in query.message.text.lower():
                await view_barber_bookings(update, context)
        except Exception as e:
            logging.error(f"Error refreshing view after status change: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error in handle_status_change: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ أثناء تحديث حالة الحجز")

async def handle_delete_booking(update: Update, context: CallbackContext):
    """Handle delete booking button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract booking ID from callback data
        booking_id = query.data.split('_')[1]
        
        # Find the row number for this booking
        all_bookings = sheets_service.get_all_bookings()
        row_num = None
        
        for i, row in enumerate(all_bookings[1:], start=2):  # Skip header row
            if row[0] == booking_id:
                row_num = i
                current_status = row[5]
                break
                
        if not row_num:
            await query.message.reply_text("❌ لم يتم العثور على الحجز")
            return
            
        if current_status == "Deleted":
            await query.message.reply_text("❌ هذا الموعد محذوف بالفعل!")
            return
            
        # Delete the booking (mark as deleted)
        sheets_service.update_cell(row_num, 6, "Deleted")  # Update status column (6)
        
        # Send confirmation
        await query.message.reply_text("🗑️ تم حذف الموعد بنجاح!")
        
        # Refresh the view
        try:
            # Clear notification cache for this user
            notification_service.clear_notification_cache()
            
            # Try to refresh the view
            if "waiting" in query.message.text.lower():
                await view_waiting_bookings(update, context)
            elif "barber" in query.message.text.lower():
                await view_barber_bookings(update, context)
        except Exception as e:
            logging.error(f"Error refreshing view after deletion: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error in handle_delete_booking: {str(e)}")
        await query.message.reply_text("❌ حدث خطأ أثناء حذف الحجز")

async def handle_refresh(update: Update, context: CallbackContext) -> None:
    """Handle refreshing the Google Sheets connection"""
    try:
        # Refresh connection and clear caches
        sheets_service.refresh_connection()
        notification_service.clear_notification_cache()
        
        await update.message.reply_text("🔄 تم تحديث الاتصال بنجاح!")
    except Exception as e:
        logging.error(f"Error in handle_refresh: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء تحديث الاتصال")

async def shop_admin_panel(update: Update, context: CallbackContext):
    """Handle the /shopadmin command"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("الرجاء استخدام الأمر بالشكل الصحيح:\n/shopadmin <اسم المحل> <كلمة المرور>")
        return ConversationHandler.END
    
    shop_name = context.args[0]
    password = context.args[1]
    
    if barber_shop_service.verify_shop_admin(shop_name, password):
        context.user_data['current_shop'] = shop_name
        context.user_data['is_shop_admin'] = True
        
        keyboard = [
            ["📋 شوف اللايحة ديال الانتظار", "✅ شوف المكملين"],
            ["🔄 تحديث", "➕ زيد موعد"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"مرحباً بك في لوحة تحكم محل {shop_name}!\nاختر ما تريد القيام به:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ كلمة المرور غير صحيحة أو المحل غير موجود.")
    
    return ConversationHandler.END

async def view_waiting_bookings(update: Update, context: CallbackContext):
    """View waiting bookings for the current shop"""
    if not context.user_data.get('is_shop_admin') or not context.user_data.get('current_shop'):
        await update.message.reply_text("الرجاء تسجيل الدخول إلى لوحة التحكم أولاً.")
        return ConversationHandler.END
    
    shop_name = context.user_data['current_shop']
    shop = barber_shop_service.get_shop(shop_name)
    if not shop:
        await update.message.reply_text("❌ حدث خطأ في الوصول إلى بيانات المحل.")
        return ConversationHandler.END
    
    # Get waiting bookings from the shop's Google Sheet
    waiting_bookings = sheets_service.get_waiting_bookings(shop['sheet_id'])
    
    if not waiting_bookings:
        await update.message.reply_text("لا يوجد مواعيد في الانتظار حالياً.")
        return ConversationHandler.END
    
    message = "📋 قائمة المواعيد في الانتظار:\n\n"
    for booking in waiting_bookings:
        message += (
            f"👤 الاسم: {booking[1]}\n"
            f"📱 الهاتف: {booking[2]}\n"
            f"💇‍♂️ الحلاق: {booking[3]}\n"
            f"🎫 رقم التذكرة: {booking[4]}\n"
            f"-------------------\n"
        )
    
    await update.message.reply_text(message)
    return ConversationHandler.END

async def view_done_bookings(update: Update, context: CallbackContext):
    """View completed bookings for the current shop"""
    if not context.user_data.get('is_shop_admin') or not context.user_data.get('current_shop'):
        await update.message.reply_text("الرجاء تسجيل الدخول إلى لوحة التحكم أولاً.")
        return ConversationHandler.END
    
    shop_name = context.user_data['current_shop']
    shop = barber_shop_service.get_shop(shop_name)
    if not shop:
        await update.message.reply_text("❌ حدث خطأ في الوصول إلى بيانات المحل.")
        return ConversationHandler.END
    
    # Get completed bookings from the shop's Google Sheet
    done_bookings = sheets_service.get_done_bookings(shop['sheet_id'])
    
    if not done_bookings:
        await update.message.reply_text("لا يوجد مواعيد مكتملة حالياً.")
        return ConversationHandler.END
    
    message = "✅ قائمة المواعيد المكتملة:\n\n"
    for booking in done_bookings:
        message += (
            f"👤 الاسم: {booking[1]}\n"
            f"📱 الهاتف: {booking[2]}\n"
            f"💇‍♂️ الحلاق: {booking[3]}\n"
            f"🎫 رقم التذكرة: {booking[4]}\n"
            f"-------------------\n"
        )
    
    await update.message.reply_text(message)
    return ConversationHandler.END

async def handle_status_change(update: Update, context: CallbackContext):
    """Handle changing the status of a booking"""
    if not context.user_data.get('is_shop_admin') or not context.user_data.get('current_shop'):
        await update.callback_query.message.reply_text("الرجاء تسجيل الدخول إلى لوحة التحكم أولاً.")
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    shop_name = context.user_data['current_shop']
    shop = barber_shop_service.get_shop(shop_name)
    if not shop:
        await query.message.reply_text("❌ حدث خطأ في الوصول إلى بيانات المحل.")
        return ConversationHandler.END
    
    # Extract booking ID from callback data
    booking_id = query.data.split('_')[1]
    
    # Update the booking status in the shop's Google Sheet
    if sheets_service.update_booking_status(shop['sheet_id'], booking_id, "Done"):
        await query.message.reply_text("✅ تم تحديث حالة الموعد بنجاح!")
    else:
        await query.message.reply_text("❌ حدث خطأ أثناء تحديث حالة الموعد.")
    
    return ConversationHandler.END

async def handle_delete_booking(update: Update, context: CallbackContext):
    """Handle deleting a booking"""
    if not context.user_data.get('is_shop_admin') or not context.user_data.get('current_shop'):
        await update.callback_query.message.reply_text("الرجاء تسجيل الدخول إلى لوحة التحكم أولاً.")
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    shop_name = context.user_data['current_shop']
    shop = barber_shop_service.get_shop(shop_name)
    if not shop:
        await query.message.reply_text("❌ حدث خطأ في الوصول إلى بيانات المحل.")
        return ConversationHandler.END
    
    # Extract booking ID from callback data
    booking_id = query.data.split('_')[1]
    
    # Delete the booking from the shop's Google Sheet
    if sheets_service.delete_booking(shop['sheet_id'], booking_id):
        await query.message.reply_text("✅ تم حذف الموعد بنجاح!")
    else:
        await query.message.reply_text("❌ حدث خطأ أثناء حذف الموعد.")
    
    return ConversationHandler.END

async def handle_refresh(update: Update, context: CallbackContext):
    """Handle refreshing the view"""
    if not context.user_data.get('is_shop_admin') or not context.user_data.get('current_shop'):
        await update.message.reply_text("الرجاء تسجيل الدخول إلى لوحة التحكم أولاً.")
        return ConversationHandler.END
    
    await update.message.reply_text("🔄 جاري تحديث البيانات...")
    return ConversationHandler.END 