from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CallbackContext
from src.config.super_admin_config import (
    SUPER_ADMIN_PASSWORD, ADDING_BARBER_SHOP, ENTERING_SHOP_NAME,
    ENTERING_SHOP_ADMIN_PASSWORD, ENTERING_SHEET_ID, BTN_ADD_SHOP,
    BTN_VIEW_SHOPS, BTN_DELETE_SHOP, BTN_BACK_TO_SUPER_ADMIN
)
from src.services.barber_shop_service import BarberShopService

# Initialize services
barber_shop_service = BarberShopService()

async def super_admin_panel(update: Update, context: CallbackContext):
    """Handle the /superadmin command"""
    if not context.args or context.args[0] != SUPER_ADMIN_PASSWORD:
        await update.message.reply_text("كلمة المرور غير صحيحة.")
        return ConversationHandler.END

    keyboard = [
        [BTN_ADD_SHOP],
        [BTN_VIEW_SHOPS],
        [BTN_DELETE_SHOP]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "مرحباً بك في لوحة تحكم المشرف الرئيسي. اختر ما تريد القيام به:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def start_adding_shop(update: Update, context: CallbackContext):
    """Start the process of adding a new barber shop"""
    await update.message.reply_text("أدخل اسم محل الحلاقة الجديد:")
    return ENTERING_SHOP_NAME

async def handle_shop_name(update: Update, context: CallbackContext):
    """Handle the shop name input"""
    shop_name = update.message.text
    if shop_name in barber_shop_service.get_all_shops():
        await update.message.reply_text("هذا المحل موجود بالفعل. جرب اسماً آخر:")
        return ENTERING_SHOP_NAME
    
    context.user_data['shop_name'] = shop_name
    await update.message.reply_text("أدخل كلمة المرور لمشرف المحل:")
    return ENTERING_SHOP_ADMIN_PASSWORD

async def handle_shop_admin_password(update: Update, context: CallbackContext):
    """Handle the shop admin password input"""
    admin_password = update.message.text
    context.user_data['admin_password'] = admin_password
    await update.message.reply_text("أدخل معرف ملف Google Sheets الخاص بالمحل:")
    return ENTERING_SHEET_ID

async def handle_sheet_id(update: Update, context: CallbackContext):
    """Handle the Google Sheets ID input"""
    sheet_id = update.message.text
    shop_name = context.user_data['shop_name']
    admin_password = context.user_data['admin_password']
    
    if barber_shop_service.add_shop(shop_name, admin_password, sheet_id):
        await update.message.reply_text(f"تم إضافة محل {shop_name} بنجاح!")
    else:
        await update.message.reply_text("حدث خطأ أثناء إضافة المحل. حاول مرة أخرى.")
    
    return ConversationHandler.END

async def view_shops(update: Update, context: CallbackContext):
    """View all barber shops"""
    shops = barber_shop_service.get_all_shops()
    if not shops:
        await update.message.reply_text("لا توجد محلات حالياً.")
        return ConversationHandler.END
    
    message = "المحلات المتوفرة:\n\n"
    for shop in shops:
        message += f"• {shop}\n"
    
    await update.message.reply_text(message)
    return ConversationHandler.END

async def start_deleting_shop(update: Update, context: CallbackContext):
    """Start the process of deleting a barber shop"""
    shops = barber_shop_service.get_all_shops()
    if not shops:
        await update.message.reply_text("لا توجد محلات لحذفها.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(shop, callback_data=f"delete_shop_{shop}")] for shop in shops]
    keyboard.append([InlineKeyboardButton("إلغاء", callback_data="cancel_delete")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("اختر المحل الذي تريد حذفه:", reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_shop_deletion(update: Update, context: CallbackContext):
    """Handle the shop deletion callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_delete":
        await query.message.reply_text("تم إلغاء عملية الحذف.")
        return ConversationHandler.END
    
    shop_name = query.data.replace("delete_shop_", "")
    if barber_shop_service.delete_shop(shop_name):
        await query.message.reply_text(f"تم حذف محل {shop_name} بنجاح!")
    else:
        await query.message.reply_text("حدث خطأ أثناء حذف المحل. حاول مرة أخرى.")
    
    return ConversationHandler.END 