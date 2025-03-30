from datetime import datetime
import logging
from telegram import Bot
from src.config.config import APPOINTMENT_DURATION_MINUTES

class NotificationService:
    def __init__(self):
        self.notification_cache = {}
        self.notified_users = set()
        self.logger = logging.getLogger(__name__)
        logging.info("NotificationService initialized")

    def save_notification_status(self, user_id: str, notification_type: str):
        """Save that a notification has been sent"""
        try:
            key = f"{user_id}_{notification_type}"
            self.notification_cache[key] = datetime.now().timestamp()
            logging.info(f"Saved notification status for {key}")
        except Exception as e:
            logging.error(f"Error saving notification status: {str(e)}")

    def was_recently_notified(self, user_id: str, notification_type: str) -> bool:
        """Check if user was recently notified (within last 5 minutes)"""
        try:
            key = f"{user_id}_{notification_type}"
            if key not in self.notification_cache:
                logging.info(f"No recent notification found for {key}")
                return False
            time_diff = datetime.now().timestamp() - self.notification_cache[key]
            result = time_diff < 300  # 5 minutes
            logging.info(f"Checking recent notification for {key}: {result} (time_diff: {time_diff}s)")
            return result
        except Exception as e:
            logging.error(f"Error checking recent notifications: {str(e)}")
            return False  # Changed to False to ensure notifications are sent if there's an error

    def clear_notifications_for_user(self, user_id: str):
        """Clear all notifications for a specific user"""
        try:
            keys_to_remove = [key for key in self.notification_cache.keys() if key.startswith(f"{user_id}_")]
            for key in keys_to_remove:
                del self.notification_cache[key]
        except Exception as e:
            logging.error(f"Error clearing notifications: {str(e)}")

    async def send_notifications(self, context, waiting_appointments):
        """Send notifications to users whose turn is coming up"""
        try:
            for appointment in waiting_appointments:
                user_id = appointment['user_id']
                name = appointment['name']
                ticket_number = appointment['ticket_number']
                barber = appointment['barber']
                position = appointment['position']
                estimated_wait = appointment['estimated_wait']

                # Skip if user was already notified
                if user_id in self.notified_users:
                    continue

                # Calculate time until appointment
                if estimated_wait <= 5:  # 5 minutes or less
                    message = (
                        f"🔔 *تنبيه!*\n\n"
                        f"مرحبا {name} 👋\n"
                        f"دورك قريب! 🎯\n\n"
                        f"📋 معلومات رنديفوك:\n"
                        f"• التذكرة: {ticket_number}\n"
                        f"• الحلاق: {barber}\n"
                        f"• موقعك ف اللاشان: {position}\n"
                        f"• الوقت لي باقي: {estimated_wait} دقائق ⏰\n\n"
                        f"من فضلك كون جاهز! 🙏"
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        self.notified_users.add(user_id)
                        self.logger.info(f"Sent notification to user {user_id} for ticket {ticket_number}")
                    except Exception as e:
                        self.logger.error(f"Failed to send notification to user {user_id}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error in send_notifications: {str(e)}")

    def clear_notifications(self):
        """Clear the list of notified users"""
        self.notified_users.clear()
        self.logger.info("Cleared notification history")

    def _clear_old_notifications(self, current_user_ids):
        """Clear notifications for users no longer in queue"""
        try:
            before_count = len(self.notification_cache)
            for key in list(self.notification_cache.keys()):
                user_id = key.split('_')[0]
                if user_id not in current_user_ids:
                    del self.notification_cache[key]
            after_count = len(self.notification_cache)
            logging.info(f"Cleared {before_count - after_count} old notifications")
        except Exception as e:
            logging.error(f"Error clearing old notifications: {str(e)}")

    async def _send_position_notification(self, context, position, user_id, user_name, barber):
        """Send notification based on queue position"""
        try:
            notification_config = {
                0: ("turn", "🎉 {name}، دورك توا!\nروح لـ {barber}.\nإذا ما جيتش في 5 دقايق، تقدر تخسر دورك."),
                1: ("warning_15", "🔔 {name}! دورك قريب يجي مع {barber} في 15 دقيقة.\nابدا تقرب للصالون باش ما تخسرش دورك."),
                2: ("warning_30", "🔔 {name}! دورك غادي يجي مع {barber} في 30 دقيقة.\nابدا تقرب للصالون باش ما تخسرش دورك."),
                3: ("warning_45", "🔔 {name}! دورك غادي يجي مع {barber} في 45 دقيقة.\nابدا تقرب للصالون باش ما تخسرش دورك."),
                4: ("warning_60", "🔔 {name}! دورك غادي يجي مع {barber} في ساعة.\nابدا تقرب للصالون باش ما تخسرش دورك.")
            }

            if position in notification_config:
                notification_type, message_template = notification_config[position]
                
                if not self.was_recently_notified(user_id, notification_type):
                    message = message_template.format(name=user_name, barber=barber)
                    logging.info(f"Sending {notification_type} notification to user {user_id}")
                    
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=message
                        )
                        self.save_notification_status(user_id, notification_type)
                        logging.info(f"Successfully sent {notification_type} notification to user {user_id}")
                    except Exception as e:
                        logging.error(f"Failed to send Telegram message to user {user_id}: {str(e)}")
                else:
                    logging.info(f"Skipping {notification_type} notification for user {user_id} (recently notified)")

        except Exception as e:
            logging.error(f"Error sending position notification: {str(e)}") 