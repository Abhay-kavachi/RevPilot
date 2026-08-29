from dotenv import load_dotenv
load_dotenv()
import asyncio
from app.razorpay.adapter import RazorpayAdapter

async def run_test():
    adapter = RazorpayAdapter()
    print("Testing Razorpay Payment Link Creation...")
    try:
        # Create a tiny 1-rupee payment link
        success, result = adapter.create_payment_link(
            amount=100, # 100 paise = 1 INR
            currency="INR",
            reference_id="test_plink_real_124",
            description="RevPilot Real Credentials Test"
        )
        if success:
            print("SUCCESS! Created Payment Link:")
            print(f"ID: {result.get('id')}")
            print(f"URL: {result.get('short_url')}")
            print("Full response:", result)
        else:
            print(f"RAZORPAY ERROR: {result}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
