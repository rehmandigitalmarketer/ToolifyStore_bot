import sqlite3
import string
import random
from database import get_connection, add_user_balance

def create_voucher(amount_cents, created_by=0):
    """Admin creates a redeemable voucher code (e.g. VOUCH-XXXX-XXXX)"""
    code = "KEY-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        amount_cents INTEGER,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("INSERT INTO vouchers (code, amount_cents) VALUES (?, ?)", (code, amount_cents))
    conn.commit()
    conn.close()
    return code

def redeem_voucher(user_id, code):
    """User redeems voucher code to get instant balance"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vouchers WHERE code = ? AND is_used = 0", (code.strip().upper(),))
    v = cursor.fetchone()
    if not v:
        conn.close()
        return False, "❌ Invalid ya already used voucher code."

    amount_cents = v["amount_cents"]
    cursor.execute("UPDATE vouchers SET is_used = 1, used_by = ? WHERE code = ?", (user_id, code.strip().upper()))
    conn.commit()
    conn.close()

    new_bal = add_user_balance(user_id, amount_cents, note=f"Redeemed Voucher {code}")
    return True, {"amount_cents": amount_cents, "new_balance": new_bal}
