from datetime import datetime
import logging
from src.config.config import APPOINTMENT_DURATION_MINUTES

class NotificationService:
    def __init__(self):
        self.notification_cache = {}

    def save_notification_status(self, user_id: str, notification_type: str):
        """Save that a notification has been sent"""
        self.notification_cache[f"{user_id}_{notification_type}"] = datetime.now().timestamp()

    def was_recently_notified(self, user_id: str, notification_type: str) -> bool:
        """Check if user was recently notified (within last 5 minutes)"""
        key = f"{user_id}_{notification_type}"
        if key not in self.notification_cache:
            return False
        time_diff = datetime.now().timestamp() - self.notification_cache[key]
        return time_diff < 300  # 5 minutes

    def clear_notifications_for_user(self, user_id: str):
        """Clear all notifications for a specific user"""
        keys_to_remove = [key for key in self.notification_cache.keys() if key.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            del self.notification_cache[key]

    async def send_notifications(self, context, waiting_appointments):
        """Send notifications to users based on their position in queue"""
        try:
            # Clear old notifications for users no longer in queue
            current_user_ids = [appointment[0] for appointment in waiting_appointments]
            for key in list(self.notification_cache.keys()):
                user_id = key.split('_')[0]
                if user_id not in current_user_ids:
                    del self.notification_cache[key]

            for position, appointment in enumerate(waiting_appointments):
                user_id = appointment[0]
                user_name = appointment[1]
                barber = appointment[3]

                try:
                    # Send turn notification to first in line
                    if position == 0 and not self.was_recently_notified(user_id, "turn"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🎉 {user_name}، دورك توا!\n"
                                 f"روح لـ {barber}.\n"
                                 f"إذا ما جيتش في 5 دقايق، تقدر تخسر دورك."
                        )
                        self.save_notification_status(user_id, "turn")
                        logging.info(f"Sent turn notification to user {user_id}")

                    # Send 15-minute warning to next in line
                    elif position == 1 and not self.was_recently_notified(user_id, "warning"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔔 {user_name}! دورك قريب يجي مع {barber} في 15 دقيقة.\n"
                                 f"ابدا تقرب للصالون باش ما تخسرش دورك."
                        )
                        self.save_notification_status(user_id, "warning")
                        logging.info(f"Sent 15-min warning to user {user_id}")

                    # Send 30-minute warning to third in line
                    elif position == 2 and not self.was_recently_notified(user_id, "warning_30"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔔 {user_name}! دورك غادي يجي مع {barber} في 30 دقيقة.\n"
                                 f"ابدا تقرب للصالون باش ما تخسرش دورك."
                        )
                        self.save_notification_status(user_id, "warning_30")
                        logging.info(f"Sent 30-min warning to user {user_id}")

                    # Send 45-minute warning to fourth in line
                    elif position == 3 and not self.was_recently_notified(user_id, "warning_45"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔔 {user_name}! دورك غادي يجي مع {barber} في 45 دقيقة.\n"
                                 f"ابدا تقرب للصالون باش ما تخسرش دورك."
                        )
                        self.save_notification_status(user_id, "warning_45")
                        logging.info(f"Sent 45-min warning to user {user_id}")

                    # Send 1-hour warning to fifth in line
                    elif position == 4 and not self.was_recently_notified(user_id, "warning_60"):
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔔 {user_name}! دورك غادي يجي مع {barber} في ساعة.\n"
                                 f"ابدا تقرب للصالون باش ما تخسرش دورك."
                        )
                        self.save_notification_status(user_id, "warning_60")
                        logging.info(f"Sent 60-min warning to user {user_id}")

                except Exception as e:
                    logging.error(f"Failed to send notification to user {user_id}: {str(e)}")
                    continue

        except Exception as e:
            logging.error(f"Error in send_notifications: {str(e)}") 