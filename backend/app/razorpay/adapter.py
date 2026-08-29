import os
import httpx
import time
from typing import Dict, Any, Tuple

from app.core.config import settings

class RazorpayAdapter:
    def __init__(self):
        self.key_id = settings.razorpay.KEY_ID
        self.key_secret = settings.razorpay.KEY_SECRET
        self.base_url = settings.razorpay.API_BASE_URL
        self.auth = (self.key_id, self.key_secret)
        self.timeouts = httpx.Timeout(
            connect=settings.razorpay.TIMEOUT_CONNECT,
            read=settings.razorpay.TIMEOUT_READ,
            write=settings.razorpay.TIMEOUT_WRITE,
            pool=5.0
        )
        
    def _post(self, path: str, json_data: dict) -> Tuple[bool, dict]:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.post(url, json=json_data, auth=self.auth, timeout=self.timeouts)
            data = response.json()
            if response.status_code == 400 and "error" in data and "description" in data["error"]:
                # If duplicate idempotency key (receipt/reference_id), razorpay throws 400 with specific text
                # We can handle that upstream.
                return False, data
            
            response.raise_for_status()
            return True, data
        except httpx.HTTPStatusError as e:
            return False, e.response.json()
        except Exception as e:
            return False, {"error": {"description": str(e)}}

    def create_payment_link(self, amount: int, currency: str, reference_id: str, description: str = "") -> Tuple[bool, dict]:
        """
        Create a Payment Link. reference_id acts as our idempotency key per the verification doc.
        expire_by is omitted to use default (or must be >= 15 min if provided).
        """
        payload = {
            "amount": amount,
            "currency": currency,
            "reference_id": reference_id,
            "description": description,
            "reminder_enable": True,
            "accept_partial": True,
            "first_min_partial_amount": 10000 # Minimum 100 INR
        }
        return self._post("/payment_links", payload)

    def create_order(self, amount: int, currency: str, receipt: str) -> Tuple[bool, dict]:
        """
        Create an Order. receipt acts as idempotency key.
        """
        payload = {
            "amount": amount,
            "currency": currency,
            "receipt": receipt
        }
        return self._post("/orders", payload)
