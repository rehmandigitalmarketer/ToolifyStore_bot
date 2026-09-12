import logging
import asyncio
import os
import html
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import config
from qamify_api import qamify
import database as db
from vouchers import create_voucher, redeem_voucher
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ----------------- LOGGING ----------------- #
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------- 24/7 CLOUD HEALTH SERVER (RENDER / RAILWAY) ----------------- #
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Toolify Bot is Live 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server error: {e}")

threading.Thread(target=run_health_server, daemon=True).start()

# ----------------- HELPERS ----------------- #
def format_price(cents):
    """Convert cents to configured currency string"""
    usd = cents / 100.0
    local_val = usd * config.USD_TO_LOCAL_RATE
    if config.CURRENCY_SYMBOL == "$":
        return f"${local_val:.2f}"
    return f"{config.CURRENCY_SYMBOL}{local_val:,.0f}"

def get_custom_prices():
    """Load custom prices from custom_prices.json if exists"""
    custom_path = os.path.join(os.path.dirname(__file__), "custom_prices.json")
    if os.path.exists(custom_path):
        try:
            with open(custom_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {str(k): float(v) for k, v in data.items() if str(k).isdigit()}
        except Exception:
            pass
    return {}

def calculate_selling_cents(cost_cents, product_id=None):
    """Calculates selling price in cents: Checks custom price first, otherwise uses profit margin"""
    if product_id is not None:
        custom_prices = get_custom_prices()
        p_id_str = str(product_id)
        if p_id_str in custom_prices:
            return int(round(custom_prices[p_id_str] * 100))

    margin = (100.0 + config.PROFIT_MARGIN_PERCENT) / 100.0
    return int(round(cost_cents * margin))

def escape(text):
    """Escape HTML characters"""
    return html.escape(str(text)) if text else ""

async def safe_edit_message(query, text, reply_markup=None, parse_mode="HTML"):
    """Safely edit message without crashing on 'Message is not modified' error"""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            try:
                await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception as e2:
                logger.error(f"Error sending message: {e2}")

# ----------------- UI / KEYBOARDS ----------------- #
def get_main_menu_keyboard(user_id):
    bal_cents = db.get_user_balance(user_id)
    bal_text = format_price(bal_cents)
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Browse Products & Keys", callback_data="products_page_0")],
        [
            InlineKeyboardButton(f"💰 Balance: {bal_text}", callback_data="my_balance"),
            InlineKeyboardButton("💳 Add Balance", callback_data="deposit")
        ],
        [
            InlineKeyboardButton("📜 My Orders", callback_data="my_orders"),
            InlineKeyboardButton("📞 Support", callback_data="support")
        ]
    ]

    if user_id in config.ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Dashboard", callback_data="admin_panel")])

    return InlineKeyboardMarkup(keyboard)

# ----------------- COMMAND HANDLERS ----------------- #

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    db.get_or_create_user(user.id, user.username or "", user.first_name or "")
    bal_cents = db.get_user_balance(user.id)
    bal_str = format_price(bal_cents)
    safe_name = escape(user.first_name)

    text = (
        f"⚡ <b>Welcome to Toolify Store, {safe_name}!</b> 🚀\n\n"
        f"🛒 <i>Your Premium Digital Marketplace for Licenses, Keys & Subscriptions.</i>\n\n"
        f"💵 <b>Your Wallet Balance:</b> <code>{bal_str}</code>\n"
        f"🆔 <b>Your User ID:</b> <code>{user.id}</code>\n\n"
        "Neeche diye gaye buttons se products browse karein ya balance deposit karein:"
    )
    
    reply_markup = get_main_menu_keyboard(user.id)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
        await safe_edit_message(update.callback_query, text, reply_markup=reply_markup)

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct /shop command"""
    PAGE_SIZE = 6
    success, products = qamify.get_products()
    if not success or not isinstance(products, list) or not products:
        await update.message.reply_text("📦 Filhal store mein koi products available nahi hain.", parse_mode="HTML")
        return

    total_products = len(products)
    current_page_products = products[0:PAGE_SIZE]
    keyboard = []
    for p in current_page_products:
        p_id = p.get("id")
        p_name = escape(p.get("name", f"Product #{p_id}"))
        stock = p.get("stock", 0)
        cost_cents = p.get("unit_price_cents", 0)
        sell_cents = calculate_selling_cents(cost_cents, p_id)
        price_text = format_price(sell_cents)
        stock_badge = f"🟢 ({stock})" if stock > 0 else "🔴 Out"
        keyboard.append([InlineKeyboardButton(f"{p_name} | {price_text} {stock_badge}", callback_data=f"pview_{p_id}")])

    if total_products > PAGE_SIZE:
        keyboard.append([InlineKeyboardButton("Next ➡️", callback_data="products_page_1")])
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

    total_pages = max(1, (total_products + PAGE_SIZE - 1) // PAGE_SIZE)
    await update.message.reply_text(
        f"🛍️ <b>Available Products Catalog</b> (Page 1/{total_pages}):\n"
        "<i>Product select karein details aur buy karne ke liye:</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct /wallet command"""
    user = update.effective_user
    bal_cents = db.get_user_balance(user.id)
    text = (
        f"💰 <b>Wallet Overview</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"💵 <b>Current Balance:</b> <code>{format_price(bal_cents)}</code>\n\n"
        "Aap balance add karke koi bhi product instantly khareed sakte hain."
    )
    keyboard = [
        [InlineKeyboardButton("💳 Add Balance Now", callback_data="deposit")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct /orders command"""
    user = update.effective_user
    orders = db.get_user_orders(user.id, limit=8)
    if not orders:
        await update.message.reply_text(
            "📜 Aapne abhi tak koi order place nahi kiya.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ Shop Now", callback_data="products_page_0")]]),
            parse_mode="HTML"
        )
        return

    text = "📜 <b>Your Recent Orders:</b>\n\n"
    for o in orders:
        text += (
            f"📦 <b>{escape(o['product_name'])}</b>\n"
            f"🔖 Code: <code>{escape(o['order_code'])}</code> | Price: <code>{format_price(o['sold_price_cents'])}</code>\n"
            f"🔑 Key: {o['keys_delivered']}\n"
            f"🕒 Date: <code>{escape(o['created_at'])}</code>\n"
            "─────────────────\n"
        )
    keyboard = [
        [InlineKeyboardButton("🛍️ Shop More", callback_data="products_page_0")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct /profile command"""
    user = update.effective_user
    u_data = db.get_or_create_user(user.id, user.username or "", user.first_name or "")
    bal_cents = u_data["balance_cents"]
    orders = db.get_user_orders(user.id, limit=100)
    
    text = (
        "👤 <b>Your Account Profile:</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"👤 <b>Name:</b> {escape(user.first_name)}\n"
        f"🔗 <b>Username:</b> @{escape(user.username or 'None')}\n"
        f"💰 <b>Wallet Balance:</b> <code>{format_price(bal_cents)}</code>\n"
        f"📦 <b>Total Orders:</b> <code>{len(orders)}</code>\n"
        f"📅 <b>Member Since:</b> <code>{u_data.get('created_at', 'Active')}</code>"
    )
    keyboard = [
        [InlineKeyboardButton("💳 Add Balance", callback_data="deposit")],
        [InlineKeyboardButton("📜 View Orders", callback_data="my_orders")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct /support command"""
    user = update.effective_user
    supp_user = config.SUPPORT_USERNAME.replace("@", "")
    supp_id = getattr(config, "SUPPORT_USER_ID", "8978230804")
    text = (
        "📞 <b>Customer Support & Assistance</b>\n\n"
        "Agar aapko kisi bhi order ya payment mein madad chahiye to contact karein:\n\n"
        f"👤 <b>Admin / Support:</b> @{escape(supp_user)}\n"
        f"🆔 <b>Support User ID:</b> <code>{supp_id}</code>\n"
        f"📌 <b>Your User ID:</b> <code>{user.id}</code>\n\n"
        "<i>Payment screenshots aur order queries ke liye direct Telegram par rabta karein.</i>"
    )
    keyboard = [
        [InlineKeyboardButton("💬 Open Support Chat", url=f"https://t.me/{supp_user}")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif update.callback_query:
        await safe_edit_message(update.callback_query, text, reply_markup=InlineKeyboardMarkup(keyboard))

async def set_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows claiming admin role if ADMIN_IDS is empty"""
    user_id = update.effective_user.id
    if not config.ADMIN_IDS:
        config.ADMIN_IDS.append(user_id)
        await update.message.reply_text(f"👑 Congratulations! You are now set as the Admin of this bot (ID: <code>{user_id}</code>).", parse_mode="HTML")
    else:
        if user_id in config.ADMIN_IDS:
            await update.message.reply_text("Aap pehle se Admin hain.")
        else:
            await update.message.reply_text("❌ Admin rights already claimed.")

async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        await update.message.reply_text("⛔ Sirf Admins balance add kar sakte hain.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/addbalance &lt;user_id&gt; &lt;amount_in_dollars&gt;</code>\nExample: <code>/addbalance 123456789 10.0</code>", parse_mode="HTML")
        return

    try:
        target_user = int(context.args[0])
        amount_val = float(context.args[1])
        amount_cents = int(round(amount_val * 100))

        new_bal = db.add_user_balance(target_user, amount_cents, note=f"Admin added by {user_id}")
        await update.message.reply_text(
            f"✅ <b>Balance Added Successfully!</b>\n\n"
            f"👤 User: <code>{target_user}</code>\n"
            f"➕ Added: <code>{format_price(amount_cents)}</code>\n"
            f"💰 New Balance: <code>{format_price(new_bal)}</code>",
            parse_mode="HTML"
        )
        
        try:
            await context.bot.send_message(
                chat_id=target_user,
                text=f"💳 <b>Deposit Confirmed!</b>\n\nAapke wallet mein <code>{format_price(amount_cents)}</code> add kardiye gaye hain.\nNew Balance: <code>{format_price(new_bal)}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/redeem &lt;VOUCHER_CODE&gt;</code>\nExample: <code>/redeem KEY-A1B2C3D4</code>", parse_mode="HTML")
        return

    code = context.args[0]
    success, res = redeem_voucher(user_id, code)
    if success:
        amt_str = format_price(res["amount_cents"])
        bal_str = format_price(res["new_balance"])
        await update.message.reply_text(
            f"🎉 <b>Voucher Redeemed Successfully!</b>\n\n"
            f"➕ Added: <code>{amt_str}</code>\n"
            f"💰 New Balance: <code>{bal_str}</code>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"❌ {res}", parse_mode="HTML")

async def genvoucher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/genvoucher &lt;amount_in_usd&gt;</code>\nExample: <code>/genvoucher 10.0</code>", parse_mode="HTML")
        return

    try:
        amt_usd = float(context.args[0])
        cents = int(round(amt_usd * 100))
        code = create_voucher(cents, created_by=user_id)
        await update.message.reply_text(
            f"🎟️ <b>Voucher Created!</b>\n\n"
            f"Code: <code>{code}</code>\n"
            f"Value: <code>{format_price(cents)}</code>\n\n"
            "Yeh code user ko send karein, wo <code>/redeem CODE</code> likh kar balance claim kar sakega.",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def check_qamify_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        return

    is_ok, res = qamify.get_balance()
    if is_ok:
        bal_cents = res.get("balance_cents", 0)
        await update.message.reply_text(f"🌐 <b>Qamify Reseller Balance:</b> <code>${bal_cents/100:.2f}</code> ({bal_cents} cents)", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Failed to fetch balance: <code>{escape(res.get('error'))}</code>", parse_mode="HTML")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ Usage: <code>/broadcast &lt;message to all users&gt;</code>", parse_mode="HTML")
        return

    all_users = db.get_all_users()
    count = 0
    await update.message.reply_text(f"📢 Sending broadcast to {len(all_users)} users...")

    for u in all_users:
        try:
            await context.bot.send_message(chat_id=u, text=f"📢 <b>Announcement:</b>\n\n{escape(msg)}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ Broadcast complete! Delivered to {count}/{len(all_users)} users.")

# ----------------- CALLBACK QUERY ROUTER ----------------- #

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    user = update.effective_user
    user_id = user.id

    try:
        # 1. Main Menu
        if data == "main_menu":
            await start_command(update, context)

        # 2. Support
        elif data == "support":
            await support_command(update, context)

        # 3. Balance Info
        elif data == "my_balance":
            bal_cents = db.get_user_balance(user_id)
            text = (
                f"💰 <b>Wallet Overview</b>\n\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"💵 <b>Current Balance:</b> <code>{format_price(bal_cents)}</code>\n\n"
                "Aap balance add karke koi bhi product instantly khareed sakte hain."
            )
            keyboard = [
                [InlineKeyboardButton("💳 Add Balance Now", callback_data="deposit")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

        # 4. Deposit Instructions
        elif data == "deposit":
            supp_user = config.SUPPORT_USERNAME.replace("@", "")
            text = f"{config.PAYMENT_INSTRUCTIONS}\n\n🆔 <b>Your User ID:</b> <code>{user_id}</code>"
            keyboard = [
                [InlineKeyboardButton("💬 Contact Support to Add Balance", url=f"https://t.me/{supp_user}")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

        # 5. Products List with Pagination
        elif data.startswith("products_page_"):
            page = int(data.split("_")[-1])
            PAGE_SIZE = 6

            success, products = qamify.get_products()
            if not success or not isinstance(products, list) or not products:
                err_msg = products.get("error", "API Connection Error") if isinstance(products, dict) else "No Products Found"
                await safe_edit_message(
                    query,
                    f"⚠️ <b>Products fetch nahi ho sake:</b>\n<code>{escape(err_msg)}</code>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return

            total_products = len(products)
            start_idx = page * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            current_page_products = products[start_idx:end_idx]

            keyboard = []
            for p in current_page_products:
                p_id = p.get("id")
                p_name = escape(p.get("name", f"Product #{p_id}"))
                stock = p.get("stock", 0)
                cost_cents = p.get("unit_price_cents", 0)
                sell_cents = calculate_selling_cents(cost_cents, p_id)
                price_text = format_price(sell_cents)
                
                stock_badge = f"🟢 ({stock})" if stock > 0 else "🔴 Out"
                btn_text = f"{p_name} | {price_text} {stock_badge}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pview_{p_id}")])

            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"products_page_{page-1}"))
            if end_idx < total_products:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"products_page_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)

            keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

            total_pages = max(1, (total_products + PAGE_SIZE - 1) // PAGE_SIZE)
            await safe_edit_message(
                query,
                f"🛍️ <b>Available Products Catalog</b> (Page {page+1}/{total_pages}):\n"
                "<i>Product select karein details aur buy karne ke liye:</i>",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # 6. View Single Product
        elif data.startswith("pview_"):
            product_id = int(data.split("_")[1])
            _, all_p = qamify.get_products()
            p = next((item for item in all_p if item.get("id") == product_id), None) if isinstance(all_p, list) else None

            if not p:
                await safe_edit_message(query, "❌ Product information nahi mil saki.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="products_page_0")]]))
                return

            p_name = escape(p.get("name", f"Product #{product_id}"))
            stock = p.get("stock", 0)
            cost_cents = p.get("unit_price_cents", 0)
            sell_cents = calculate_selling_cents(cost_cents, product_id)
            desc = escape((p.get("description") or "Instant delivery digital product key upon purchase.")[:800])

            text = (
                f"📦 <b>{p_name}</b>\n\n"
                f"📝 <b>Description:</b>\n{desc}\n\n"
                f"💵 <b>Price:</b> <code>{format_price(sell_cents)}</code>\n"
                f"📊 <b>Live Stock:</b> <code>{'In Stock (' + str(stock) + ')' if stock > 0 else '❌ Out of Stock'}</code>\n"
            )

            keyboard = []
            if stock > 0:
                keyboard.append([InlineKeyboardButton(f"⚡ Buy Now ({format_price(sell_cents)})", callback_data=f"pbuy_{product_id}")])
            else:
                keyboard.append([InlineKeyboardButton("❌ Out of Stock", callback_data="no_stock")])

            keyboard.append([InlineKeyboardButton("🔙 Back to Products", callback_data="products_page_0")])
            await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "no_stock":
            await query.answer("Yeh product filhal out of stock hai.", show_alert=True)

        # 7. Buy Product Confirmation & Execution
        elif data.startswith("pbuy_"):
            product_id = int(data.split("_")[1])
            _, all_p = qamify.get_products()
            p = next((item for item in all_p if item.get("id") == product_id), None) if isinstance(all_p, list) else None

            if not p:
                await safe_edit_message(query, "❌ Product not found.")
                return

            p_name = escape(p.get("name", f"Product #{product_id}"))
            cost_cents = p.get("unit_price_cents", 0)
            sell_cents = calculate_selling_cents(cost_cents, product_id)
            user_bal = db.get_user_balance(user_id)

            if user_bal < sell_cents:
                shortfall = sell_cents - user_bal
                await safe_edit_message(
                    query,
                    f"❌ <b>Insufficient Balance!</b>\n\n"
                    f"Product: <b>{p_name}</b>\n"
                    f"Price: <code>{format_price(sell_cents)}</code>\n"
                    f"Your Balance: <code>{format_price(user_bal)}</code>\n"
                    f"Need: <code>{format_price(shortfall)}</code> more.\n\n"
                    "Please add balance to your wallet to continue.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💳 Add Balance", callback_data="deposit")],
                        [InlineKeyboardButton("🔙 Back", callback_data=f"pview_{product_id}")]
                    ])
                )
                return

            deducted, remaining_bal = db.deduct_user_balance(user_id, sell_cents, note=f"Buy: {p_name}")
            if not deducted:
                await safe_edit_message(query, "❌ Balance deduction failed. Please try again.")
                return

            await safe_edit_message(query, "⏳ <b>Purchasing license key from server, please wait...</b>")

            order_success, order_res = qamify.place_order(product_id=product_id, qty=1)

            if order_success:
                keys = order_res.get("keys", [])
                order_code = order_res.get("code", order_res.get("order_code", "N/A"))
                keys_text = "\n".join([f"<code>{escape(k)}</code>" for k in keys]) if keys else f"<code>{escape(order_res.get('data', 'Delivered'))}</code>"

                db.record_order(
                    user_id=user_id,
                    product_id=product_id,
                    product_name=p_name,
                    qty=1,
                    cost_cents=cost_cents,
                    sold_price_cents=sell_cents,
                    order_code=str(order_code),
                    keys_delivered=keys_text
                )

                success_text = (
                    f"🎉 <b>Order Successful!</b>\n\n"
                    f"📦 <b>Product:</b> {p_name}\n"
                    f"🔖 <b>Order Code:</b> <code>{escape(order_code)}</code>\n\n"
                    f"🔑 <b>Your Key / License:</b>\n{keys_text}\n\n"
                    f"💰 <b>Remaining Balance:</b> <code>{format_price(remaining_bal)}</code>\n\n"
                    "Thank you for your purchase! ❤️"
                )
                keyboard = [
                    [InlineKeyboardButton("📜 View Order History", callback_data="my_orders")],
                    [InlineKeyboardButton("🛍️ Continue Shopping", callback_data="products_page_0")]
                ]
                await safe_edit_message(query, success_text, reply_markup=InlineKeyboardMarkup(keyboard))

            else:
                db.add_user_balance(user_id, sell_cents, note=f"Refund: Failed order for {p_name}")
                new_bal = db.get_user_balance(user_id)
                err_msg = order_res.get("error", "Stock unavailable or server error.")

                fail_text = (
                    f"⚠️ <b>Order Failed & Refunded!</b>\n\n"
                    f"Reason: <code>{escape(err_msg)}</code>\n\n"
                    f"💵 Aapke <code>{format_price(sell_cents)}</code> wallet mein wapis refund kardiye gaye hain.\n"
                    f"Current Balance: <code>{format_price(new_bal)}</code>"
                )
                keyboard = [[InlineKeyboardButton("🔙 Back to Store", callback_data="products_page_0")]]
                await safe_edit_message(query, fail_text, reply_markup=InlineKeyboardMarkup(keyboard))

        # 8. User Order History
        elif data == "my_orders":
            orders = db.get_user_orders(user_id, limit=8)
            if not orders:
                await safe_edit_message(
                    query,
                    "📜 Aapne abhi tak koi order place nahi kiya.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ Buy Now", callback_data="products_page_0")]])
                )
                return

            text = "📜 <b>Your Recent Orders:</b>\n\n"
            for o in orders:
                text += (
                    f"📦 <b>{escape(o['product_name'])}</b>\n"
                    f"🔖 Code: <code>{escape(o['order_code'])}</code> | Price: <code>{format_price(o['sold_price_cents'])}</code>\n"
                    f"🔑 Key: {o['keys_delivered']}\n"
                    f"🕒 Date: <code>{escape(o['created_at'])}</code>\n"
                    "─────────────────\n"
                )

            keyboard = [
                [InlineKeyboardButton("🛍️ Shop More", callback_data="products_page_0")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]
            await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

        # 9. Admin Dashboard
        elif data == "admin_panel":
            if user_id not in config.ADMIN_IDS:
                await query.answer("Access Denied.", show_alert=True)
                return

            stats = db.get_stats()
            is_ok, qbal = qamify.get_balance()
            qbal_str = f"${(qbal.get('balance_cents', 0)/100):.2f}" if is_ok else "Error fetching"

            text = (
                "⚙️ <b>Admin Dashboard</b>\n\n"
                f"👥 <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
                f"📦 <b>Total Orders Sold:</b> <code>{stats['total_orders']}</code>\n"
                f"💵 <b>Total Revenue:</b> <code>{format_price(stats['total_revenue_cents'])}</code>\n"
                f"📈 <b>Total Profit Made:</b> <code>{format_price(stats['total_profit_cents'])}</code>\n"
                f"🌐 <b>Qamify Supplier Balance:</b> <code>{qbal_str}</code>\n\n"
                "<b>Admin Commands:</b>\n"
                "• <code>/addbalance &lt;user_id&gt; &lt;amount_in_usd&gt;</code> - Add balance to user\n"
                "• <code>/genvoucher &lt;amount_in_usd&gt;</code> - Create a balance voucher\n"
                "• <code>/broadcast &lt;message&gt;</code> - Send message to all bot users\n"
                "• <code>/qbalance</code> - Check live Qamify API balance"
            )
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_panel")],
                [InlineKeyboardButton("🔙 Back to Store", callback_data="main_menu")]
            ]
            await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Error in callback_router: {e}", exc_info=True)

# ----------------- GLOBAL ERROR HANDLER ----------------- #
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# ----------------- MAIN RUNNER ----------------- #
def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("❌ Error: Telegram Bot Token configure nahi hai!")
        return

    print("🚀 Initializing Toolify Reseller Telegram Bot...")
    
    builder = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN)
    
    if config.PROXY_URL:
        print(f"🌐 Using proxy: {config.PROXY_URL}")
        builder = builder.proxy(config.PROXY_URL).get_updates_proxy(config.PROXY_URL)
        
    app = builder.build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(CommandHandler("wallet", wallet_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CommandHandler("setadmin", set_admin_command))
    app.add_handler(CommandHandler("addbalance", add_balance_command))
    app.add_handler(CommandHandler("genvoucher", genvoucher_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("qbalance", check_qamify_balance_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    # Callback Query Router
    app.add_handler(CallbackQueryHandler(callback_router))
    
    # Global error handler
    app.add_error_handler(error_handler)

    print("🤖 Bot started successfully! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
