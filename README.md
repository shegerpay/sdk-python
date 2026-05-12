<p align="center"><img src="logo.png" alt="ShegerPay" width="200" /></p>

# ShegerPay Python SDK

Official Python SDK for ShegerPay — verify Ethiopian bank payments (CBE, Telebirr, BOA, Awash) in your app.

[![Version](https://img.shields.io/badge/version-2.2.0-blue)](https://pypi.org/project/shegerpay/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Install

```bash
pip install shegerpay
```

## Quick Start

```python
from shegerpay import ShegerPay

client = ShegerPay("sk_live_YOUR_API_KEY")

# Verify a payment
result = client.verify(transaction_id="FT26062K7WMY", amount=1000, provider="cbe")
print(result.verified)  # True/False

# Verify from screenshot (OCR)
import base64
with open("receipt.png", "rb") as f:
    img = base64.b64encode(f.read()).decode()
result = client.verify_image(screenshot=img, provider="cbe")

# Create payment link
link = client.create_payment_link(title="Order #1234", amount=1500, currency="ETB")
print(link["url"])
```

## Supported Providers
`cbe` · `telebirr` · `boa` · `awash` · `ebirr_kaafi` · `ebirr_coop`

## Docs
- Full docs: https://shegerpay.com/docs
- API reference: https://shegerpay.com/docs/api
- Support: support@shegerpay.com | https://t.me/shegerpay_0
