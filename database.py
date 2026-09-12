import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_database.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance_cents INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        qty INTEGER DEFAULT 1,
        cost_cents INTEGER,
        sold_price_cents INTEGER,
        order_code TEXT,
        keys_delivered TEXT,
        status TEXT DEFAULT 'completed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Balance transaction logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount_cents INTEGER,
        type TEXT, -- 'deposit', 'purchase', 'refund', 'admin_adjust'
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

def get_or_create_user(user_id, username="", first_name=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, balance_cents) VALUES (?, ?, ?, 0)",
            (user_id, username or "", first_name or "")
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    else:
        # Update username/first_name if changed
        cursor.execute(
            "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
            (username or user["username"], first_name or user["first_name"], user_id)
        )
        conn.commit()
    conn.close()
    return dict(user)

def get_user_balance(user_id):
    user = get_or_create_user(user_id)
    return user["balance_cents"]

def add_user_balance(user_id, amount_cents, note="Admin Deposit"):
    conn = get_connection()
    cursor = conn.cursor()
    get_or_create_user(user_id)
    cursor.execute("UPDATE users SET balance_cents = balance_cents + ? WHERE user_id = ?", (amount_cents, user_id))
    cursor.execute(
        "INSERT INTO transactions (user_id, amount_cents, type, note) VALUES (?, ?, 'deposit', ?)",
        (user_id, amount_cents, note)
    )
    conn.commit()
    cursor.execute("SELECT balance_cents FROM users WHERE user_id = ?", (user_id,))
    new_bal = cursor.fetchone()["balance_cents"]
    conn.close()
    return new_bal

def deduct_user_balance(user_id, amount_cents, note="Product Purchase"):
    conn = get_connection()
    cursor = conn.cursor()
    user = get_or_create_user(user_id)
    if user["balance_cents"] < amount_cents:
        conn.close()
        return False, user["balance_cents"]

    cursor.execute("UPDATE users SET balance_cents = balance_cents - ? WHERE user_id = ?", (amount_cents, user_id))
    cursor.execute(
        "INSERT INTO transactions (user_id, amount_cents, type, note) VALUES (?, ?, 'purchase', ?)",
        (user_id, amount_cents, note)
    )
    conn.commit()
    cursor.execute("SELECT balance_cents FROM users WHERE user_id = ?", (user_id,))
    new_bal = cursor.fetchone()["balance_cents"]
    conn.close()
    return True, new_bal

def record_order(user_id, product_id, product_name, qty, cost_cents, sold_price_cents, order_code, keys_delivered):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO orders (user_id, product_id, product_name, qty, cost_cents, sold_price_cents, order_code, keys_delivered)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, product_id, product_name, qty, cost_cents, sold_price_cents, order_code, keys_delivered))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

def get_user_orders(user_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(*) as total_orders, SUM(sold_price_cents) as total_revenue, SUM(cost_cents) as total_cost FROM orders")
    order_stats = cursor.fetchone()
    total_orders = order_stats["total_orders"] or 0
    total_revenue = order_stats["total_revenue"] or 0
    total_cost = order_stats["total_cost"] or 0
    total_profit = total_revenue - total_cost

    conn.close()
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue_cents": total_revenue,
        "total_cost_cents": total_cost,
        "total_profit_cents": total_profit
    }

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r["user_id"] for r in rows]

# Auto initialize database on module load
init_db()
