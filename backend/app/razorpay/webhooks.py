import hmac
import hashlib
import os

class WebhookVerifier:
    def __init__(self):
        self.secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret").encode('utf-8')

    def verify_signature(self, raw_body: bytes, signature: str) -> bool:
        """
        Verify Razorpay webhook signature.
        """
        if not signature:
            return False
            
        expected_mac = hmac.new(self.secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_mac, signature)
