import sys
import os
from barbershop_bot import main
import threading

# Start the bot in a separate thread
def run_bot():
    main()

bot_thread = threading.Thread(target=run_bot)
bot_thread.start()

# Required for PythonAnywhere
application = None 