import os
import sys
from app.core.config import settings
import httpx
from httpx import BasicAuth
import json

def check(payment_link_id):
    url = f"https://api.razorpay.com/v1/payment_links/{payment_link_id}"
    res = httpx.get(url, auth=BasicAuth(settings.razorpay.KEY_ID, settings.razorpay.KEY_SECRET))
    if res.status_code == 200:
        print(json.dumps(res.json(), indent=2))
    else:
        print(f"Error {res.status_code}: {res.text}")
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_rzp.py <payment_link_id>")
        sys.exit(1)
    check(sys.argv[1])
