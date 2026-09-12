import requests
import os

# OxaPay / Cryptomus Gateway Configuration (Optional - for 100% automated crypto deposits)
OXAPAY_MERCHANT_KEY = os.getenv("OXAPAY_MERCHANT_KEY", "")

def create_crypto_invoice(user_id, amount_usd):
    """Creates automated crypto payment link via OxaPay"""
    if not OXAPAY_MERCHANT_KEY:
        return False, "OxaPay Merchant key configured nahi hai."

    url = "https://api.oxapay.com/merchants/request"
    payload = {
        "merchant": OXAPAY_MERCHANT_KEY,
        "amount": amount_usd,
        "currency": "USD",
        "lifeTime": 30,
        "orderId": f"DEP-{user_id}",
        "description": f"Wallet Deposit for User {user_id}"
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if data.get("result") == 100:
            return True, data.get("payLink")
        return False, data.get("message", "Error creating invoice")
    except Exception as e:
        return False, str(e)
