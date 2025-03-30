import json
import os
from typing import Dict, List, Optional

class BarberShopService:
    def __init__(self):
        self.shops_file = "data/barber_shops.json"
        self._ensure_data_directory()
        self._load_shops()

    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        os.makedirs(os.path.dirname(self.shops_file), exist_ok=True)
        if not os.path.exists(self.shops_file):
            self._save_shops({})

    def _load_shops(self):
        """Load barber shops from file"""
        try:
            with open(self.shops_file, 'r', encoding='utf-8') as f:
                self.shops = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.shops = {}
            self._save_shops(self.shops)

    def _save_shops(self, shops: Dict):
        """Save barber shops to file"""
        with open(self.shops_file, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=4)

    def add_shop(self, shop_name: str, admin_password: str, sheet_id: str) -> bool:
        """Add a new barber shop"""
        if shop_name in self.shops:
            return False
        
        self.shops[shop_name] = {
            "admin_password": admin_password,
            "sheet_id": sheet_id,
            "barbers": {}
        }
        self._save_shops(self.shops)
        return True

    def delete_shop(self, shop_name: str) -> bool:
        """Delete a barber shop"""
        if shop_name not in self.shops:
            return False
        
        del self.shops[shop_name]
        self._save_shops(self.shops)
        return True

    def get_shop(self, shop_name: str) -> Optional[Dict]:
        """Get barber shop details"""
        return self.shops.get(shop_name)

    def get_all_shops(self) -> List[str]:
        """Get all barber shop names"""
        return list(self.shops.keys())

    def verify_shop_admin(self, shop_name: str, password: str) -> bool:
        """Verify shop admin password"""
        shop = self.get_shop(shop_name)
        return shop and shop["admin_password"] == password

    def add_barber(self, shop_name: str, barber_id: str, barber_name: str) -> bool:
        """Add a barber to a shop"""
        shop = self.get_shop(shop_name)
        if not shop:
            return False
        
        shop["barbers"][barber_id] = barber_name
        self._save_shops(self.shops)
        return True

    def get_shop_barbers(self, shop_name: str) -> Dict[str, str]:
        """Get all barbers for a shop"""
        shop = self.get_shop(shop_name)
        return shop["barbers"] if shop else {} 