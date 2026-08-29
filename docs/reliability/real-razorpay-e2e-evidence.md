# Real Razorpay E2E Evidence

This document serves as proof that RevPilot has successfully executed genuine end-to-end recovery lifecycles via the real Razorpay Test API, routed securely back to our application via Ngrok webhooks.

## Full Payment Test (August 29, 2026)
- **Test Timestamp**: `2026-08-29 15:50:31 IST`
- **Case ID**: `0904a3b9-bc76-4962-9bd1-23a2ab4396ee`
- **Payment Link ID**: `plink_TVXn8CY7vMnLjG`
- **Payment ID**: `pay_TVXzmVLzSbIEhA`
- **Webhook Event ID**: `TVXzww2rNvHe9N` (`payment_link.paid`)
- **Amount at Risk**: ₹500.00 (50000 paise)
- **Recovered Amount**: ₹500.00 (50000 paise)
- **Final Case Status**: `CaseStatus.RECOVERED`
- **Signature Verification**: Validated successfully via strict HMAC-SHA256 (`200 OK`)
- **Webhook Arrival Evidence**:
  Received `payment_link.paid` containing exact payout metadata, confirmed on `ngrok` request trace, deduplicated by Postgres `WebhookEvent` table, and audited in `AuditEvent`.

---

## Partial Payment Test (August 29, 2026)
- **Test Timestamp**: `2026-08-29 16:07:40 IST`
- **Case ID**: `8beee88e-eee3-4a70-abb6-2064199b8c9e`
- **Payment Link ID**: `plink_TVYSFtz9yPjMUd`
- **Payment ID**: `pay_TVYTQoZGJSkJTb`
- **Webhook Event ID**: `TVYTRwFplYpp1I` (`payment_link.partially_paid`)
- **Amount at Risk**: ₹500.00 (50000 paise)
- **Recovered Amount**: ₹200.00 (20000 paise)
- **Final Case Status**: `CaseStatus.RECOVERED`
- **Signature Verification**: Validated successfully via strict HMAC-SHA256 (`200 OK`)
- **Webhook Arrival Evidence**:
  Received `payment_link.partially_paid` with `amount_paid = 20000`. This independently updated the case `amount_recovered` to accurately reflect only the partial amount paid, preventing financial misalignment.
