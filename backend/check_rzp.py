import os
from app.core.config import settings
import httpx
from httpx import BasicAuth
import json

def check():
    url = "https://api.razorpay.com/v1/payment_links/plink_TVgk6ndc5ydzMg"
    res = httpx.get(url, auth=BasicAuth(settings.razorpay.KEY_ID, settings.razorpay.KEY_SECRET))
    print(json.dumps(res.json(), indent=2))
    
if __name__ == "__main__":
    check()
