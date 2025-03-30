from datetime import datetime
import logging
from src.config.config import APPOINTMENT_DURATION_MINUTES

class NotificationService:
    def __init__(self):
        self.notification_cache = {}
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
        """Send notifications to users based on their position in queue"""
        if not waiting_appointments:
            logging.info("No waiting appointments to process")
            return

        try:
            logging.info(f"Processing notifications for {len(waiting_appointments)} appointments")
            # Clear old notifications for users no longer in queue
            current_user_ids = [str(appointment[0]) for appointment in waiting_appointments]
            self._clear_old_notifications(current_user_ids)

            for position, appointment in enumerate(waiting_appointments):
                try:
                    user_id = str(appointment[0])
                    user_name = appointment[1]
                    barber = appointment[3]
                    logging.info(f"Processing notification for position {position}, user {user_id}")

                    # Send notifications based on position
                    await self._send_position_notification(
                        context, position, user_id, user_name, barber
                    )

                except Exception as e:
                    logging.error(f"Failed to process notification for position {position}, user {user_id}: {str(e)}")
                    continue

        except Exception as e:
            logging.error(f"Error in send_notifications: {str(e)}")

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