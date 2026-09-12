# 🤖 Qamify Reseller Telegram Bot

A complete, automated Telegram Bot to resell digital license keys and products via Qamify API.

---

### 📁 Project Structure

```
qamify-telegram-bot/
├── .env                <-- Apni Qamify API Key aur Settings yahan dalein
├── config.py           <-- Configurations & currency settings
├── database.py         <-- SQLite Database (Users, Orders, Balances)
├── qamify_api.py       <-- Qamify API connector
├── bot.py              <-- Main Telegram Bot runner
└── run_bot.bat         <-- Windows One-Click Start Script
```

---

### ⚙️ Setup Instructions:

1. **Step 1: Open `.env` file**
   - Apni poori **Qamify API Key** paste karein:
     ```env
     QAMIFY_API_KEY=qamify_cea39f... (poori key dalein)
     ```
   - Apne **Support Username** ka naam dalein (e.g. `SUPPORT_USERNAME=YourTelegramUsername`)

2. **Step 2: Bot Start Karein**
   - Sirf `run_bot.bat` par double click karein ya terminal mein chalayein:
     ```bash
     python bot.py
     ```

3. **Step 3: Admin Banein**
   - Telegram par apne bot ko kholein aur command bhejein:
     `/setadmin`
   - Aap bot ke admin ban jayenge.

---

### 👑 Admin Commands:

| Command | Description | Example |
|---|---|---|
| `/setadmin` | Bot ka admin claim karne ke liye | `/setadmin` |
| `/addbalance <user_id> <amount>` | Kisi user ke wallet me balance add karne ke liye | `/addbalance 12345678 10.0` |
| `/qbalance` | Apna live Qamify prepaid balance check karne ke liye | `/qbalance` |
| `/broadcast <message>` | Bot ke tamaam users ko announcement bhejne ke liye | `/broadcast New stock arrived!` |

---

### 💡 Features Included:
- 🛍️ Live products and stock from Qamify API
- 📈 Automated profit margin (default: +25% profit)
- 💳 User wallet system with manual deposit instructions
- ⚡ Instant license key delivery upon order
- 🔄 Automatic refund to wallet if API or stock fails
- 📜 Order history with delivered keys saved in local database
- 📊 Admin Dashboard with user count, profit analytics, and sales stats
