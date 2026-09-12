import uuid
import time
import httpx
import logging
import config

logger = logging.getLogger(__name__)

class AsyncQamifyClient:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or config.QAMIFY_API_KEY
        self.base_url = (base_url or config.QAMIFY_BASE_URL).rstrip("/")
        self._products_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 60  # Cache products for 60 seconds for instant response

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ToolifyBot/1.0"
        }

    async def ping(self):
        """Check if API key is valid"""
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                res = await client.get(f"{self.base_url}/v1/ping", headers=self.headers)
                return res.status_code == 200, res.json() if res.content else {}
        except Exception as e:
            logger.error(f"Qamify ping error: {e}")
            return False, {"error": str(e)}

    async def get_balance(self):
        """Get prepaid reseller balance"""
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                res = await client.get(f"{self.base_url}/v1/balance", headers=self.headers)
                if res.status_code == 200:
                    return True, res.json()
                return False, {"error": f"Status {res.status_code}: {res.text}"}
        except Exception as e:
            logger.error(f"Qamify balance error: {e}")
            return False, {"error": str(e)}

    async def get_products(self, force_refresh=False):
        """Get all products with in-memory caching for lightning fast instant response"""
        now = time.time()
        if not force_refresh and self._products_cache and (now - self._cache_timestamp < self._cache_ttl):
            return True, self._products_cache

        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                res = await client.get(f"{self.base_url}/v1/products", headers=self.headers)
                if res.status_code == 200:
                    data = res.json()
                    products = []
                    if isinstance(data, list):
                        products = data
                    elif isinstance(data, dict) and "products" in data:
                        products = data["products"]
                    elif isinstance(data, dict) and "data" in data:
                        products = data["data"]
                    else:
                        products = data

                    self._products_cache = products
                    self._cache_timestamp = now
                    return True, products
                elif self._products_cache:
                    # Return cached products as fallback
                    return True, self._products_cache
                return False, {"error": f"Status {res.status_code}: {res.text}"}
        except Exception as e:
            logger.error(f"Qamify get_products error: {e}")
            if self._products_cache:
                return True, self._products_cache
            return False, {"error": str(e)}

    async def get_product(self, product_id):
        """Get single product details"""
        # Check cache first
        if self._products_cache:
            p = next((item for item in self._products_cache if item.get("id") == int(product_id)), None)
            if p:
                return True, p

        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
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
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.post(f"{self.base_url}/v1/orders", json=payload, headers=self.headers)
                data = res.json() if res.content else {}
                
                # Invalidate cache so stock refreshes
                self._products_cache = None

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

qamify = AsyncQamifyClient()
