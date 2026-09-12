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

# Admin Telegram Numeric IDs
ADMIN_IDS = [8978230804]

# Profit margin in percent (10% profit)
PROFIT_MARGIN_PERCENT = float(os.getenv("PROFIT_MARGIN_PERCENT", "10"))

# Currency display settings
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")
USD_TO_LOCAL_RATE = float(os.getenv("USD_TO_LOCAL_RATE", "1.0"))

# Support Contact
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "rehman_balochi")
SUPPORT_USER_ID = "8978230804"

# Payment details text shown when user clicks Deposit
PAYMENT_INSTRUCTIONS = os.getenv("PAYMENT_INSTRUCTIONS", """💳 <b>Deposit & Add Balance Options:</b>

🟡 <b>Binance Pay (Instant):</b>
• <b>Binance Pay ID:</b> <code>8978230804</code> (Rehman)
• <b>USDT (TRC-20):</b> <code>TYOUR_TRC20_WALLET_ADDRESS_HERE</code>
• <b>USDT (BEP-20):</b> <code>0xYOUR_BEP20_WALLET_ADDRESS_HERE</code>

🇵🇰 <b>Local Payment Methods:</b>
• <b>Easypaisa / JazzCash:</b> Contact Support
• <b>Bank Transfer:</b> Contact Support

⚠️ <b>Important Note:</b>
Payment send karne ke baad payment transaction screenshot aur apna <b>User ID</b> support (@rehman_balochi) ko bhejein taake aapka wallet balance foran credit ho sake.""")
