import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8956196956:AAFKbV1orYjiuUW7JG9ruJvQIAUIYxo5q9c")

# Optional Proxy (Agar VPN na ho toh http://127.0.0.1:port ya socks5://... yahan daal sakte hain)
PROXY_URL = os.getenv("PROXY_URL", "")

# Qamify Reseller API Key
QAMIFY_API_KEY = os.getenv("QAMIFY_API_KEY", "qamify_0e1f456d3981d3c0124ba29713dac4749ff122fe758b49ea")

# Base URL for Qamify
QAMIFY_BASE_URL = os.getenv("QAMIFY_BASE_URL", "https://api.qamify.site")

# Admin Telegram Numeric IDs (comma separated if multiple in .env)
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]

# Profit margin in percent (e.g., 20 means you add 20% profit on top of Qamify price)
PROFIT_MARGIN_PERCENT = float(os.getenv("PROFIT_MARGIN_PERCENT", "20"))

# Currency display settings
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")  # e.g., '$' or 'Rs '
USD_TO_LOCAL_RATE = float(os.getenv("USD_TO_LOCAL_RATE", "1.0"))  # e.g., 280 for PKR, or 1.0 for USD

# Support Contact Username (e.g. your_telegram_username)
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "Support_Admin")

# Payment details text shown when user clicks Deposit
PAYMENT_INSTRUCTIONS = os.getenv("PAYMENT_INSTRUCTIONS", """💳 *Deposit Payment Details:*

• *Easypaisa / JazzCash:* `03001234567` (Account Name)
• *USDT (TRC-20):* `TYOUR_CRYPTO_WALLET_ADDRESS`
• *Bank Transfer:* `Bank Name - Account Number`

⚠️ *Important:* Payment send karne ke baad payment screenshot aur apna User ID support ko send karein taake aapka balance add ho sake.""")
