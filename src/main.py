import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler
)
from src.config.config import (
    TELEGRAM_TOKEN, SELECTING_BARBER, ENTERING_NAME, ENTERING_PHONE,
    ADMIN_VERIFICATION, BTN_BOOK_APPOINTMENT, BTN_VIEW_QUEUE, BTN_CHECK_WAIT,
    BTN_VIEW_WAITING, BTN_VIEW_DONE, BTN_VIEW_BARBER1, BTN_VIEW_BARBER2,
    BTN_CHANGE_STATUS, BTN_DELETE, BTN_ADD, BTN_REFRESH
)
from src.handlers.booking_handlers import (
    choose_barber, barber_selection, handle_name, handle_phone
)
from src.handlers.admin_handlers import (
    admin_panel, verify_admin_password, view_waiting_bookings,
    view_done_bookings, view_barber_bookings, handle_status_change,
    handle_delete_booking, handle_refresh
)
from src.handlers.queue_handlers import check_queue, estimated_wait_time
from src.services.sheets_service import SheetsService
from src.services.notification_service import NotificationService

# Setup logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Initialize services
sheets_service = SheetsService()
notification_service = NotificationService()

async def start(update: Update, context):
    """Handle the /start command"""
    keyboard = [["📋 شوف لاشان", "📅 دير رنديفو"],
                ["⏳ شحال باقي"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("مرحبا بيك عند الحلاق! شنو تحب دير:", reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context):
    """Handle the /cancel command"""
    await update.message.reply_text("تم إلغاء الحجز. يمكنك حجز موعد جديد في أي وقت.")
    return ConversationHandler.END

async def check_and_notify_users(context) -> None:
    """Periodically check queue and notify users of their turn"""
    try:
        waiting_appointments = sheets_service.get_waiting_bookings()
        if waiting_appointments:
            await notification_service.send_notifications(context, waiting_appointments)
            logging.info(f"Successfully processed notifications for {len(waiting_appointments)} users")
    except Exception as e:
        logging.error(f"Error in check_and_notify_users: {str(e)}")

def main():
    """Main function to run the bot"""
    try:
        # Initialize the application with persistence
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add conversation handler for booking process
        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex(f"^{BTN_BOOK_APPOINTMENT}$"), choose_barber),
                CommandHandler("admin", admin_panel),
                MessageHandler(filters.Regex(f"^{BTN_ADD}$"), choose_barber)
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
                ],
                ADMIN_VERIFICATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, verify_admin_password)
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True,
            name="booking_conversation"
        )

        # Add all handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        
        # Add admin panel handlers
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_QUEUE}$"), check_queue))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_CHECK_WAIT}$"), estimated_wait_time))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_WAITING}$"), view_waiting_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_DONE}$"), view_done_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_BARBER1}$"), view_barber_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIEW_BARBER2}$"), view_barber_bookings))
        app.add_handler(MessageHandler(filters.Regex(f"^{BTN_REFRESH}$"), handle_refresh))
        app.add_handler(CallbackQueryHandler(handle_status_change, pattern="^status_"))
        app.add_handler(CallbackQueryHandler(handle_delete_booking, pattern="^delete_"))

        # Initialize job queue for notifications
        try:
            job_queue = app.job_queue
            if job_queue:
                # Add notification job to run every 1 minute
                job_queue.run_repeating(check_and_notify_users, interval=60, first=10)
                logging.info("Notification job queue initialized successfully")
            else:
                raise ValueError("Job queue is not available")
        except Exception as e:
            logging.error(f"Failed to initialize job queue: {str(e)}")
            raise

        logging.info("Bot is starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logging.error(f"Error starting bot: {str(e)}")
        raise

if __name__ == "__main__":
    main() 