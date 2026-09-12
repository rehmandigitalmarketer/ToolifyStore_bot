import uuid
import httpx
import config

class AsyncQamifyClient:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or config.QAMIFY_API_KEY
        self.base_url = (base_url or config.QAMIFY_BASE_URL).rstrip("/")

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def ping(self):
        """Check if API key is valid"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/v1/ping", headers=self.headers)
                return res.status_code == 200, res.json() if res.content else {}
        except Exception as e:
            return False, {"error": str(e)}

    async def get_balance(self):
        """Get prepaid reseller balance"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/v1/balance", headers=self.headers)
                if res.status_code == 200:
                    return True, res.json()
                return False, {"error": f"Status {res.status_code}: {res.text}"}
        except Exception as e:
            return False, {"error": str(e)}

    async def get_products(self):
        """Get all products and live stock asynchronously"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/v1/products", headers=self.headers)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list):
                        return True, data
                    elif isinstance(data, dict) and "products" in data:
                        return True, data["products"]
                    elif isinstance(data, dict) and "data" in data:
                        return True, data["data"]
                    return True, data
                return False, {"error": f"Status {res.status_code}: {res.text}"}
        except Exception as e:
            return False, {"error": str(e)}

    async def get_product(self, product_id):
        """Get single product details"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/v1/products/{product_id}", headers=self.headers)
                if res.status_code == 200:
                    return True, res.json()
                return False, {"error": f"Status {res.status_code}: {res.text}"}
        except Exception as e:
            return False, {"error": str(e)}

    async def place_order(self, product_id, qty=1, idempotency_key=None):
        """Buy keys with idempotency protection"""
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        payload = {
            "product_id": int(product_id),
            "qty": int(qty),
            "idempotency_key": idempotency_key
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(f"{self.base_url}/v1/orders", json=payload, headers=self.headers)
                data = res.json() if res.content else {}
                
                if res.status_code in [200, 201]:
                    return True, data
                elif res.status_code == 409:
                    return False, {"error": "Out of Stock or Insufficient Qamify Reseller Balance.", "code": 409, "raw": data}
                elif res.status_code == 429:
                    return False, {"error": "Rate limit exceeded. Please try again shortly.", "code": 429, "raw": data}
                else:
                    return False, {"error": data.get("error") or data.get("message") or res.text, "code": res.status_code}
        except Exception as e:
            return False, {"error": str(e)}

    async def get_order(self, order_code):
        """Re-fetch order details by order code"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/v1/orders/{order_code}", headers=self.headers)
                if res.status_code == 200:
                    return True, res.json()
                return False, {"error": res.text}
        except Exception as e:
            return False, {"error": str(e)}

qamify = AsyncQamifyClient()
