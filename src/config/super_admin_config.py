import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Super Admin Configuration
SUPER_ADMIN_PASSWORD = os.getenv('SUPER_ADMIN_PASSWORD', 'superadmin2024')

# Conversation States for Super Admin
ADDING_BARBER_SHOP, ENTERING_SHOP_NAME, ENTERING_SHOP_ADMIN_PASSWORD, ENTERING_SHEET_ID = range(4)

# Button texts for Super Admin Panel
BTN_ADD_SHOP = "➕ زيد محل حلاقة"
BTN_VIEW_SHOPS = "📋 شوف المحلات"
BTN_DELETE_SHOP = "❌ امسح محل"
BTN_BACK_TO_SUPER_ADMIN = "�� ارجع للوحة التحكم" 