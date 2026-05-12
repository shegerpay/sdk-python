"""
=== ShegerPay Python SDK Examples ===
Verify Ethiopian bank payments with just a few lines of code
"""

import base64
from shegerpay import ShegerPay, ShegerPayError, AuthenticationError

# Initialize client with your API key
# Use sk_test_ for development, sk_live_ for production
client = ShegerPay(api_key="sk_test_your_api_key_here")

# =====================================================
# Example 1: Quick Verify — amount is now optional
# =====================================================

print("=== Quick Verify (lookup only, no amount) ===")
try:
    result = client.quick_verify(transaction_id="FT26062K7WMY")

    if result.valid:
        print(f"Payment verified!")
        print(f"   Provider: {result.provider}")
        print(f"   Amount: {result.amount} ETB")
        print(f"   Mode: {result.mode}")
    else:
        print(f"Verification failed: {result.reason}")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 2: Quick Verify with amount (stricter check)
# =====================================================

print("\n=== Quick Verify with amount ===")
try:
    result = client.quick_verify(
        transaction_id="FT24352648751234",  # CBE format
        amount=100
    )
    print(f"Valid: {result.valid}, Status: {result.status}")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 3: Full Verify with Merchant Name
# =====================================================

print("\n=== Full Verify ===")
try:
    result = client.verify(
        provider="cbe",
        transaction_id="FT24352648751234",
        amount=100,
        merchant_name="My Shop ETB Account"
    )

    print(f"Status: {result.status}")
    print(f"Valid: {result.valid}")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 4: Image Verification (receipt screenshot)
# =====================================================

print("\n=== Image Verification ===")
try:
    with open("receipt.jpg", "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    image_result = client.verify_image(image_base64, provider="cbe")
    print(f"Image verify valid: {image_result.valid}, confidence: {image_result.confidence}")

except FileNotFoundError:
    print("(receipt.jpg not found — skipping image verify example)")
except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 5: Create Payment Link
# =====================================================

print("\n=== Create Payment Link ===")
try:
    link = client.create_payment_link(
        title="Order #1234",
        amount=1500,
        currency="ETB",
        enable_cbe=True,
        enable_telebirr=True,
    )
    print(f"Payment link: {link.url}")

    links = client.list_payment_links(limit=10)
    for l in links:
        print(f"  - {l.id}: {l.url} ({l.status})")

    client.delete_payment_link(link.id)

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 6: Webhook Management
# =====================================================

print("\n=== Webhook Management ===")
try:
    webhook = client.create_webhook(
        url="https://your-site.com/webhooks/shegerpay",
        events=["payment.verified", "payment.failed"],
    )
    print(f"Webhook created: {webhook.id}")

    webhooks = client.list_webhooks()
    print(f"Total webhooks: {len(webhooks)}")

    client.test_webhook(webhook.id)
    client.delete_webhook(webhook.id)

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 7: Webhook signature verification
# =====================================================

print("\n=== Webhook Signature Verification ===")
# In your Flask/FastAPI webhook handler:
#
# raw_payload = request.get_data(as_text=True)
# signature   = request.headers.get("x-shegerpay-signature", "")
# is_valid    = ShegerPay.verify_webhook_signature(raw_payload, signature, "YOUR_WEBHOOK_SECRET")
# if not is_valid:
#     return jsonify({"error": "Invalid signature"}), 401
# event = request.get_json()
print("(See inline comments for Flask usage)")

# =====================================================
# Example 8: List supported providers
# =====================================================

print("\n=== Supported Providers ===")
try:
    providers = client.get_providers()
    for p in providers:
        print(f"  {p.name}: {p.status}")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 9: Telebirr Verification
# =====================================================

print("\n=== Telebirr Verify ===")
try:
    result = client.verify(
        provider="telebirr",
        transaction_id="ABC123XYZ",
        amount=500
    )
    print(f"Result: {result.status}")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 10: Test Mode - Simulating Failures
# =====================================================

print("\n=== Test Mode: Simulated Failure ===")
try:
    # Include "FAIL" in transaction ID to simulate failure
    result = client.quick_verify(
        transaction_id="FAIL_TEST_123",
        amount=100
    )
    if not result.valid:
        print(f"Expected failure: {result.reason}")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 11: Get Transaction History
# =====================================================

print("\n=== Transaction History ===")
try:
    transactions = client.get_history(limit=10)
    for tx in transactions[:5]:
        print(f"  - {tx.external_id}: {tx.amount} ETB ({tx.status})")

except ShegerPayError as e:
    print(f"Error: {e.message}")

# =====================================================
# Example 12: Error Handling
# =====================================================

print("\n=== Error Handling ===")
try:
    bad_client = ShegerPay(api_key="invalid_key")
except AuthenticationError as e:
    print(f"Authentication error: {e.message}")

# =====================================================
# Example 13: Flask Integration
# =====================================================

print("\n=== Flask Integration Example ===")
print("""
from flask import Flask, request, jsonify
from shegerpay import ShegerPay

app = Flask(__name__)
shegerpay = ShegerPay(api_key="sk_live_xxx")

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    data = request.json

    # amount is optional — omit for lookup-only check
    result = shegerpay.verify(
        transaction_id=data['transaction_id'],
        amount=data.get('amount'),
        provider=data.get('provider')
    )

    if result.valid:
        return jsonify({'success': True, 'message': 'Payment verified'})
    else:
        return jsonify({'success': False, 'reason': result.reason}), 400

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_payload = request.get_data(as_text=True)
    signature   = request.headers.get('x-shegerpay-signature', '')
    is_valid    = ShegerPay.verify_webhook_signature(raw_payload, signature, 'YOUR_WEBHOOK_SECRET')
    if not is_valid:
        return jsonify({'error': 'Invalid signature'}), 401
    event = request.get_json()
    print('Event type:', event.get('type'))
    return jsonify({'received': True})
""")

print("\nAll examples completed!")
