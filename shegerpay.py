"""
ShegerPay Python SDK
Official Python SDK for ShegerPay Payment Verification Gateway
"""

import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class Provider(Enum):
    """Supported payment providers"""
    CBE = "cbe"
    TELEBIRR = "telebirr"
    BANK_TRANSFER = "bank_transfer"


@dataclass
class VerificationResult:
    """Result of a payment verification"""
    valid: bool
    status: str
    verified: bool = False
    provider: Optional[str] = None
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    reason: Optional[str] = None
    mode: Optional[str] = None
    payer: Optional[str] = None
    
    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> 'VerificationResult':
        return cls(
            valid=data.get('valid', False),
            status=data.get('status', 'unknown'),
            verified=data.get('verified', data.get('valid', False)),
            provider=data.get('provider'),
            transaction_id=data.get('transaction_id'),
            amount=data.get('amount'),
            reason=data.get('reason'),
            mode=data.get('mode'),
            payer=data.get('payer')
        )


@dataclass 
class Transaction:
    """A verified transaction record"""
    id: str
    provider: str
    external_id: str
    amount: float
    status: str
    created_at: str
    mode: str


class ShegerPayError(Exception):
    """Base exception for ShegerPay SDK"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(ShegerPayError):
    """Raised when API key is invalid"""
    pass


class ValidationError(ShegerPayError):
    """Raised when request validation fails"""
    pass


class ShegerPay:
    """
    ShegerPay Payment Verification Client
    
    Usage:
        client = ShegerPay(api_key="sk_test_xxx")
        result = client.verify(provider="cbe", transaction_id="FT123", amount=100)
    """
    
    DEFAULT_BASE_URL = "https://api.shegerpay.com"
    
    def __init__(
        self, 
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize ShegerPay client.
        
        Args:
            api_key: Your secret API key (sk_test_xxx or sk_live_xxx)
            base_url: Optional custom API base URL
            timeout: Request timeout in seconds
        """
        if not api_key:
            raise AuthenticationError("API key is required")
        
        if not api_key.startswith(("sk_test_", "sk_live_")):
            raise AuthenticationError("Invalid API key format. Must start with sk_test_ or sk_live_")
        
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.timeout = timeout
        self.mode = "test" if api_key.startswith("sk_test_") else "live"
        
        self._session = requests.Session()
        self._session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'ShegerPay-Python-SDK/2.2.0'
        })
    
    def verify(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        provider: str = None,
        merchant_name: str = None,
        sub_provider: str = None,
        sender_account: str = None
    ) -> VerificationResult:
        """
        Verify a payment transaction.
        
        Args:
            transaction_id: Bank transaction reference (e.g., FT123456789)
            amount: Expected amount in ETB
            provider: Payment provider (cbe, telebirr, boa, bank_transfer). Required unless using a BOA receipt URL.
            merchant_name: Your registered bank account name
            sub_provider: Sub-provider for bank transfers (e.g., Payoneer)
            sender_account: Required for BOA verification
            
        Returns:
            VerificationResult with valid=True if payment is verified
            
        Example:
            result = client.verify(
                provider="cbe",
                transaction_id="FT24352648751234",
                amount=100,
                merchant_name="My Shop"
            )
        """
        if not provider:
            if "cs.bankofabyssinia.com/slip/?trx=" in transaction_id.lower():
                provider = "boa"
            else:
                raise ValidationError("provider is required for ambiguous transaction references. Pass provider explicitly or use quick_verify().")
        
        data = {
            'provider': provider,
            'transaction_id': transaction_id,
            'amount': amount,
        }
        
        if merchant_name:
            data['merchant_name'] = merchant_name
        else:
            data['merchant_name'] = 'ShegerPay Verification'
            
        if sub_provider:
            data['sub_provider'] = sub_provider
        if sender_account:
            data['sender_account'] = sender_account
        
        response = self._request('POST', '/api/v1/verify', data=data)
        return VerificationResult.from_response(response)
    
    def quick_verify(
        self,
        transaction_id: str,
        amount: float,
        expected_provider: str = None,
        sender_account: str = None
    ) -> VerificationResult:
        """
        Quick verification with auto-detected provider.
        
        Args:
            transaction_id: Bank transaction reference
            amount: Expected amount
            expected_provider: Optional provider hint
            sender_account: Required when quick-verifying BOA receipts
            
        Returns:
            VerificationResult
        """
        data = {
            'transaction_id': transaction_id,
            'amount': amount
        }
        if expected_provider:
            data['expected_provider'] = expected_provider
        if sender_account:
            data['sender_account'] = sender_account
        
        response = self._request('POST', '/api/v1/quick-verify', data=data)
        return VerificationResult.from_response(response)

    def verify_image(
        self,
        image: str,  # base64 encoded or URL
        provider: Optional[str] = None,
        amount: Optional[float] = None,
        merchant_name: str = "ShegerPay Verification",
    ) -> Dict[str, Any]:
        """Verify payment from receipt screenshot. image can be base64 or URL."""
        payload = {"image": image, "merchant_name": merchant_name}
        if provider:
            payload["provider"] = provider
        if amount is not None:
            payload["amount"] = amount
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request("POST", "/api/v1/verify/image", data=payload)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def get_history(self, limit: int = 50) -> List[Transaction]:
        """
        Get transaction history.
        
        Args:
            limit: Maximum number of transactions to return
            
        Returns:
            List of Transaction objects
        """
        response = self._request('GET', '/api/v1/history')
        
        transactions = []
        for tx in response:
            transactions.append(Transaction(
                id=tx.get('id'),
                provider=tx.get('provider'),
                external_id=tx.get('external_id'),
                amount=tx.get('amount'),
                status=tx.get('status'),
                created_at=tx.get('created_at'),
                mode=tx.get('mode')
            ))
        
        return transactions
    
    # ============================================
    # 🪙 CRYPTO METHODS
    # ============================================
    
    def get_crypto_prices(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get live crypto prices.
        
        Args:
            symbol: Optional specific crypto (BTC, ETH, USDT, etc.)
            
        Returns:
            Price data dictionary
            
        Example:
            prices = client.get_crypto_prices()
            btc = client.get_crypto_prices('BTC')
        """
        if symbol:
            return self._request('GET', f'/api/v1/crypto/rate/{symbol.upper()}')
        return self._request('GET', '/api/v1/crypto/rates')
    
    def create_crypto_payment(
        self,
        amount_usd: float,
        currency: str,
        wallet_address: str,
        chain: str = "TRON"
    ) -> Dict[str, Any]:
        """
        Create a crypto payment intent.
        
        Args:
            amount_usd: Amount in USD
            currency: Crypto currency (USDT, BTC, ETH, etc.)
            wallet_address: Your receiving wallet address
            chain: Blockchain (TRON, ETH, BSC, BTC, LTC)
            
        Returns:
            Payment intent with reference_id, payment_amount, qr_code
            
        Example:
            payment = client.create_crypto_payment(
                amount_usd=50,
                currency='USDT',
                wallet_address='TJCnKsPa7y5okkXvQAidZBzqx3QyQ6sxMW',
                chain='TRON'
            )
            print(payment['reference_id'])    # SHGR-TRO-ABC123-XYZ789
            print(payment['payment_amount'])  # 50.00003456 (unique)
        """
        self._session.headers['Content-Type'] = 'application/json'
        
        response = self._request('POST', '/api/v1/crypto/generate-intent', data={
            'amount_usd': amount_usd,
            'currency': currency.upper(),
            'wallet_address': wallet_address,
            'chain': chain
        })
        
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def verify_crypto_payment(
        self,
        reference_id: str,
        transaction_hash: str = None
    ) -> Dict[str, Any]:
        """
        Verify a crypto payment by reference ID.
        
        Args:
            reference_id: The reference ID from create_crypto_payment
            transaction_hash: Optional blockchain transaction hash
            
        Returns:
            Verification result with verified=True/False
            
        Example:
            result = client.verify_crypto_payment('SHGR-TRO-ABC123-XYZ789')
            
            if result['verified']:
                print('Payment confirmed!')
            elif result['status'] == 'pending':
                print('Waiting for blockchain...')
        """
        self._session.headers['Content-Type'] = 'application/json'
        
        data = {'reference_id': reference_id}
        if transaction_hash:
            data['transaction_hash'] = transaction_hash
        
        response = self._request('POST', '/api/v1/crypto/verify-reference', data=data)
        
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def get_crypto_status(self) -> Dict[str, Any]:
        """
        Get crypto service status.
        
        Returns:
            Service status, supported chains, and tokens
        """
        return self._request('GET', '/api/v1/crypto/status')
    
    # ============================================
    # 💳 PAYPAL / CREDIT CARD METHODS
    # ============================================
    
    def paypal_create_order(
        self,
        amount: float,
        currency: str = "USD",
        description: str = None,
        vault_on_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Create a PayPal order for credit card or PayPal payment.
        
        Args:
            amount: Payment amount
            currency: Currency code (USD, EUR, GBP, etc.)
            description: Order description
            vault_on_approval: Save card for future use
            
        Returns:
            Order with ID and approval links
            
        Example:
            order = client.paypal_create_order(100, 'USD', 'Order #123')
            print(order['id'])  # Use this to capture payment
        """
        self._session.headers['Content-Type'] = 'application/json'
        
        data = {
            'amount': amount,
            'currency': currency,
        }
        if description:
            data['description'] = description
        if vault_on_approval:
            data['vault_on_approval'] = vault_on_approval
        
        response = self._request('POST', '/api/v1/paypal/create-order', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_capture_order(self, order_id: str) -> Dict[str, Any]:
        """
        Capture payment for an approved order.
        
        Args:
            order_id: PayPal order ID from create_order
            
        Returns:
            Capture result with status and payment details
            
        Example:
            result = client.paypal_capture_order('ORDER_ID')
            if result['status'] == 'COMPLETED':
                print('Payment successful!')
        """
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/paypal/capture-order', data={'order_id': order_id})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order details by ID.
        
        Args:
            order_id: PayPal order ID
            
        Returns:
            Order details
        """
        return self._request('GET', f'/api/v1/paypal/order/{order_id}')
    
    def paypal_create_setup_token(self) -> Dict[str, Any]:
        """
        Create a setup token to vault (save) a card without charging.
        
        Returns:
            Setup token for card vaulting
        """
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/paypal/vault/setup-token', data={})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_list_saved_cards(self) -> Dict[str, Any]:
        """
        List all saved payment methods.
        
        Returns:
            List of saved cards/payment tokens
        """
        return self._request('GET', '/api/v1/paypal/vault/payment-tokens')
    
    def paypal_charge_saved_card(
        self,
        payment_token_id: str,
        amount: float,
        currency: str = "USD",
        description: str = None
    ) -> Dict[str, Any]:
        """
        Charge a saved card (one-click payment).
        
        Args:
            payment_token_id: Vaulted card token ID
            amount: Payment amount
            currency: Currency code
            description: Payment description
            
        Returns:
            Capture result
            
        Example:
            result = client.paypal_charge_saved_card('TOKEN_ID', 50.00)
        """
        self._session.headers['Content-Type'] = 'application/json'
        
        data = {
            'payment_token_id': payment_token_id,
            'amount': amount,
            'currency': currency
        }
        if description:
            data['description'] = description
        
        response = self._request('POST', '/api/v1/paypal/vault/charge', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_delete_saved_card(self, token_id: str) -> Dict[str, Any]:
        """
        Delete a saved payment method.
        
        Args:
            token_id: Payment token ID to delete
            
        Returns:
            Deletion confirmation
        """
        return self._request('DELETE', f'/api/v1/paypal/vault/payment-token/{token_id}')
    
    def paypal_create_subscription(
        self,
        plan_id: str,
        subscriber_email: str = None,
        subscriber_name: str = None,
        custom_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a subscription.
        
        Args:
            plan_id: PayPal billing plan ID
            subscriber_email: Customer email
            subscriber_name: Customer name
            custom_id: Your internal subscription ID
            
        Returns:
            Subscription with ID and approval link
            
        Example:
            sub = client.paypal_create_subscription('P-PLAN123', 'user@example.com')
        """
        self._session.headers['Content-Type'] = 'application/json'
        
        data = {'plan_id': plan_id}
        if subscriber_email:
            data['subscriber_email'] = subscriber_email
        if subscriber_name:
            data['subscriber_name'] = subscriber_name
        if custom_id:
            data['custom_id'] = custom_id
        
        response = self._request('POST', '/api/v1/paypal/subscriptions', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details.
        
        Args:
            subscription_id: PayPal subscription ID
            
        Returns:
            Subscription details
        """
        return self._request('GET', f'/api/v1/paypal/subscriptions/{subscription_id}')
    
    def paypal_cancel_subscription(self, subscription_id: str, reason: str = "Customer requested") -> Dict[str, Any]:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: PayPal subscription ID
            reason: Cancellation reason
            
        Returns:
            Cancellation confirmation
        """
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', f'/api/v1/paypal/subscriptions/{subscription_id}/cancel', data={'reason': reason})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_refund(
        self,
        capture_id: str,
        amount: float = None,
        currency: str = "USD",
        note: str = None
    ) -> Dict[str, Any]:
        """
        Refund a captured payment.
        
        Args:
            capture_id: Capture ID from order capture
            amount: Refund amount (None = full refund)
            currency: Currency code
            note: Note to payer
            
        Returns:
            Refund details
            
        Example:
            # Full refund
            refund = client.paypal_refund('CAPTURE_ID')
            
            # Partial refund
            refund = client.paypal_refund('CAPTURE_ID', amount=25.00)
        """
        self._session.headers['Content-Type'] = 'application/json'
        
        data = {'capture_id': capture_id, 'currency': currency}
        if amount:
            data['amount'] = amount
        if note:
            data['note'] = note
        
        response = self._request('POST', '/api/v1/paypal/refund', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def paypal_status(self) -> Dict[str, Any]:
        """
        Get PayPal service status.
        
        Returns:
            Service status, mode (sandbox/live), and feature availability
        """
        return self._request('GET', '/api/v1/paypal/status')

    def paypal_get_wallet_balance(self) -> Dict[str, Any]:
        """Get PayPal wallet balance."""
        return self._request('GET', '/api/v1/paypal/wallet/balance')

    def paypal_list_wallet_transactions(self, limit: int = 50) -> Dict[str, Any]:
        """List PayPal wallet transactions."""
        return self._request('GET', '/api/v1/paypal/wallet/transactions', params={'limit': limit})

    def paypal_request_payout(
        self,
        amount: float,
        recipient_email: str,
        currency: str = "USD",
        note: str = None
    ) -> Dict[str, Any]:
        """Request a PayPal payout."""
        self._session.headers['Content-Type'] = 'application/json'
        data = {'amount': amount, 'currency': currency, 'recipient_email': recipient_email}
        if note:
            data['note'] = note
        response = self._request('POST', '/api/v1/paypal/payouts/request', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def paypal_list_payouts(self) -> Dict[str, Any]:
        """List PayPal payout requests."""
        return self._request('GET', '/api/v1/paypal/payouts')
    
    def get_providers(self) -> Dict[str, Any]:
        """Get list of supported payment providers and their status."""
        return self._request("GET", "/api/v1/providers")

    @staticmethod
    def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature using HMAC-SHA256."""
        import hmac, hashlib
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.replace("sha256=", ""))

    @staticmethod
    def verify_redirect_signature(params: Dict[str, Any], signature: str, secret: str) -> bool:
        """Verify signed payment-link redirect parameters."""
        import hmac, hashlib
        amount = f"{float(params.get('amount') or 0):.2f}"
        payload = "|".join([
            str(params.get("checkout_session_id") or params.get("checkoutSessionId") or ""),
            str(params.get("order_id") or params.get("orderId") or ""),
            str(params.get("short_code") or params.get("shortCode") or ""),
            amount,
            str(params.get("currency") or "ETB"),
            str(params.get("status") or "paid"),
        ])
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.replace("sha256=", ""))

    def _request(
        self,
        method: str,
        path: str,
        data: Dict = None,
        params: Dict = None
    ) -> Dict[str, Any]:
        """Make API request"""
        url = f"{self.base_url}{path}"
        
        # Use JSON for POST if Content-Type is JSON
        use_json = self._session.headers.get('Content-Type') == 'application/json'
        
        try:
            if use_json and data:
                response = self._session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.timeout
                )
            else:
                response = self._session.request(
                    method=method,
                    url=url,
                    data=data,
                    params=params,
                    timeout=self.timeout
                )
            
            return self._handle_response(response)
            
        except requests.exceptions.Timeout:
            raise ShegerPayError("Request timed out")
        except requests.exceptions.ConnectionError:
            raise ShegerPayError("Connection error")

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse API response and raise SDK-specific errors."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key", status_code=401)
        if response.status_code == 400:
            error = response.json()
            raise ValidationError(error.get('detail') or error.get('message') or 'Validation error', status_code=400)
        if response.status_code in (402, 403, 429, 503) or response.status_code >= 500:
            try:
                error = response.json()
                message = error.get('detail') or error.get('message') or 'Request failed'
            except Exception:
                message = 'Server error' if response.status_code >= 500 else 'Request failed'
            raise ShegerPayError(message, status_code=response.status_code)
        if response.status_code == 204:
            return {}
        return response.json()

    # =========================================================================
    # PAYMENT LINKS
    # =========================================================================
    
    def create_payment_link(
        self,
        title: str,
        amount: float,
        currency: str = "ETB",
        description: str = None,
        enable_cbe: bool = True,
        enable_telebirr: bool = True,
        enable_crypto: bool = False,
        expires_in_hours: int = 24,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a shareable payment link with QR code.
        
        Args:
            title: Payment title
            amount: Amount to collect
            currency: ETB, USD, etc.
            enable_cbe: Enable CBE payment
            enable_telebirr: Enable Telebirr payment
            enable_crypto: Enable crypto payment
            expires_in_hours: Link expiry time
            
        Returns:
            Payment link with URL, QR code, and short code
        """
        self._session.headers['Content-Type'] = 'application/json'
        data = {
            'title': title,
            'amount': amount,
            'currency': currency,
            'enable_cbe': enable_cbe,
            'enable_telebirr': enable_telebirr,
            'enable_crypto': enable_crypto,
            'expires_in_hours': expires_in_hours,
            'amount_mode': kwargs.get('amount_mode'),
            'amount_options': kwargs.get('amount_options'),
            'min_amount': kwargs.get('min_amount'),
            'max_amount': kwargs.get('max_amount'),
            'promo_code_ids': kwargs.get('promo_code_ids'),
            'payment_method_layout': kwargs.get('payment_method_layout'),
            'allow_quantity': kwargs.get('allow_quantity'),
            'max_quantity': kwargs.get('max_quantity'),
            'redirect_url': kwargs.get('redirect_url'),
            'webhook_url': kwargs.get('webhook_url'),
            'business_name': kwargs.get('business_name'),
            'merchant_logo_url': kwargs.get('merchant_logo_url'),
            'theme_color': kwargs.get('theme_color'),
            'hide_branding': kwargs.get('hide_branding')
        }
        if description:
            data['description'] = description
        response = self._request('POST', '/api/v1/payment-links/', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def get_payment_link_order_status(self, short_code: str, order_id: str) -> Dict[str, Any]:
        """Get source-of-truth status for one payment-link checkout order."""
        return self._request('GET', f'/api/v1/payment-links/{short_code}/orders/{order_id}/status')

    def create_promo_code(self, code: str, discount_value: float = None, discount_percent: int = None, discount_type: str = "percent", **kwargs) -> Dict[str, Any]:
        """Create a reusable promo code. Requires a secret API key and discount_codes entitlement."""
        payload = self._promo_payload(code=code, discount_value=discount_value, discount_percent=discount_percent, discount_type=discount_type, **kwargs)
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/promo-codes/', data=payload)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def list_promo_codes(self) -> List[Dict[str, Any]]:
        """List reusable promo codes for the merchant."""
        return self._request('GET', '/api/v1/promo-codes/')

    def update_promo_code(self, code_id: str, **kwargs) -> Dict[str, Any]:
        """Update a reusable promo code."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('PATCH', f'/api/v1/promo-codes/{code_id}', data=self._promo_payload(**kwargs))
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def delete_promo_code(self, code_id: str) -> Dict[str, Any]:
        """Delete a promo code."""
        return self._request('DELETE', f'/api/v1/promo-codes/{code_id}')

    def validate_promo_code(self, code: str, amount: float, link_id: str = None, provider: str = None, customer_identifier: str = None) -> Dict[str, Any]:
        """Preview a promo code before payment. Does not consume usage."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/promo-codes/validate', data={
            'code': code,
            'amount': amount,
            'link_id': link_id,
            'provider': provider,
            'customer_identifier': customer_identifier,
        })
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def redeem_promo_code(self, code: str, amount: float, transaction_id: str, link_id: str = None, provider: str = None, customer_identifier: str = None, order_id: str = None, idempotency_key: str = None) -> Dict[str, Any]:
        """Redeem after ShegerPay verification succeeds. Idempotent for the transaction/order."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/promo-codes/redeem', data={
            'code': code,
            'amount': amount,
            'link_id': link_id,
            'provider': provider,
            'customer_identifier': customer_identifier,
            'transaction_id': transaction_id,
            'order_id': order_id,
            'idempotency_key': idempotency_key,
        })
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def apply_payment_link_coupon(self, short_code: str, code: str, amount: float = None, quantity: int = 1, provider: str = None, customer_identifier: str = None) -> Dict[str, Any]:
        """Preview a promo code against a ShegerPay payment link."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', f'/api/v1/payment-links/{short_code}/apply-coupon', data={
            'code': code,
            'amount': amount,
            'quantity': quantity,
            'provider': provider,
            'customer_identifier': customer_identifier,
        })
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def _promo_payload(self, **kwargs) -> Dict[str, Any]:
        mapping = {
            'discount_type': kwargs.get('discount_type'),
            'discount_value': kwargs.get('discount_value', kwargs.get('discount_percent')),
            'discount_percent': kwargs.get('discount_percent'),
            'max_discount_amount': kwargs.get('max_discount_amount'),
            'min_order_amount': kwargs.get('min_order_amount'),
            'max_uses': kwargs.get('max_uses'),
            'max_uses_per_customer': kwargs.get('max_uses_per_customer'),
            'starts_at': kwargs.get('starts_at'),
            'expires_at': kwargs.get('expires_at'),
            'active': kwargs.get('active'),
            'applies_to_link_ids': kwargs.get('applies_to_link_ids'),
            'allowed_providers': kwargs.get('allowed_providers'),
            'metadata': kwargs.get('metadata'),
        }
        if kwargs.get('code') is not None:
            mapping['code'] = kwargs.get('code')
        return {k: v for k, v in mapping.items() if v is not None}
    
    def list_payment_links(self) -> List[Dict[str, Any]]:
        """List all payment links."""
        response = self._request('GET', '/api/v1/payment-links/')
        return response.get('links', []) if isinstance(response, dict) else response
    
    def delete_payment_link(self, link_id: str) -> Dict[str, Any]:
        """Delete a payment link."""
        return self._request('DELETE', f'/api/v1/payment-links/{link_id}')

    # =========================================================================
    # WEBHOOKS
    # =========================================================================
    
    def create_webhook(self, url: str, events: List[str] = None) -> Dict[str, Any]:
        """Create a webhook endpoint."""
        self._session.headers['Content-Type'] = 'application/json'
        data = {'url': url, 'events': events or ['*']}
        response = self._request('POST', '/api/v1/webhooks/', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all webhooks."""
        return self._request('GET', '/api/v1/webhooks/')
    
    def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Send a test webhook."""
        return self._request('POST', f'/api/v1/webhooks/test?webhook_id={webhook_id}')
    
    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook."""
        return self._request('DELETE', f'/api/v1/webhooks/{webhook_id}')

    # =========================================================================
    # MULTI-CURRENCY WALLETS
    # =========================================================================
    
    def get_wallet_balance(self) -> Dict[str, Any]:
        """Get PayPal wallet balance. Non-PayPal wallet rails are private/assisted."""
        return self.paypal_get_wallet_balance()

    def convert_currency(self, from_currency: str, to_currency: str, amount: float) -> Dict[str, Any]:
        """Currency conversion is not part of the public SDK."""
        raise ShegerPayError("Currency conversion is private/assisted and is intentionally not exposed in the public SDK.", status_code=400)

    # =========================================================================
    # REFUNDS
    # =========================================================================

    def create_refund(self, transaction_id: str, amount: float = None, reason: str = None) -> Dict[str, Any]:
        """Request a refund."""
        self._session.headers['Content-Type'] = 'application/json'
        payload = {"transaction_id": transaction_id}
        if amount: payload["amount"] = amount
        if reason: payload["reason"] = reason
        response = self._request("POST", "/api/v1/refunds", data=payload)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    def list_refunds(self, status: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List refunds."""
        params = {"limit": limit}
        if status: params["status"] = status
        return self._request("GET", "/api/v1/refunds", params=params)

    # =========================================================================
    # DISPUTES
    # =========================================================================

    def list_disputes(self, status: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List disputes."""
        params = {"limit": limit}
        if status: params["status"] = status
        return self._request("GET", "/api/v1/disputes", params=params)

    def respond_to_dispute(self, dispute_id: str, message: str, evidence: List[str] = None) -> Dict[str, Any]:
        """Respond to a dispute."""
        self._session.headers['Content-Type'] = 'application/json'
        payload = {"message": message}
        if evidence: payload["evidence_urls"] = evidence
        response = self._request("POST", f"/api/v1/disputes/{dispute_id}/respond", data=payload)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    # =========================================================================
    # PAYOUTS
    # =========================================================================
    
    def request_payout(self, amount: float, currency: str, method: str = 'bank_transfer', **kwargs) -> Dict[str, Any]:
        """Request a PayPal payout."""
        recipient_email = kwargs.get('recipient_email') or kwargs.get('recipientEmail')
        if not recipient_email:
            raise ValidationError("recipient_email is required for PayPal payouts")
        return self.paypal_request_payout(amount=amount, recipient_email=recipient_email, currency=currency, note=kwargs.get('note'))
    
    def list_payouts(self, status: str = None) -> List[Dict[str, Any]]:
        """List PayPal payout requests."""
        return self.paypal_list_payouts()

    # =========================================================================
    # TRANSACTIONS
    # =========================================================================
    
    def list_transactions(self, status: str = None, provider: str = None, limit: int = 50) -> Dict[str, Any]:
        """List transactions with filtering."""
        params = {'limit': limit}
        if status: params['status'] = status
        if provider: params['provider'] = provider
        return self._request('GET', '/api/v1/transactions/history', params=params)

    # =========================================================================
    # SUBSCRIPTIONS
    # =========================================================================
    
    def get_subscription(self) -> Dict[str, Any]:
        """Get your current ShegerPay subscription."""
        return self._request('GET', '/api/v1/subscriptions/status')
    
    def get_usage(self) -> Dict[str, Any]:
        """Get your API usage for current billing period."""
        return self._request('GET', '/api/v1/analytics/api-usage')

    # =========================================================================
    # TWO-FACTOR AUTHENTICATION
    # =========================================================================
    
    def setup_2fa(self) -> Dict[str, Any]:
        """Setup 2FA. Returns QR code and secret."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/two-factor/setup', data={})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def verify_2fa(self, code: str) -> Dict[str, Any]:
        """Verify 2FA code."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/two-factor/verify', data={'code': code})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def get_2fa_status(self) -> Dict[str, Any]:
        """Get 2FA status."""
        return self._request('GET', '/api/v1/two-factor/status')
    
    def disable_2fa(self, code: str) -> Dict[str, Any]:
        """Disable 2FA."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/two-factor/disable', data={'code': code})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response

    # =========================================================================
    # PASSKEYS (WebAuthn)
    # =========================================================================
    
    def list_passkeys(self) -> List[Dict[str, Any]]:
        """List registered passkeys."""
        return self._request('GET', '/api/v1/passkeys')
    
    def delete_passkey(self, passkey_id: str) -> Dict[str, Any]:
        """Delete a passkey."""
        return self._request('DELETE', f'/api/v1/passkeys/{passkey_id}')

    # =========================================================================
    # INTERNATIONAL PAYMENTS
    # =========================================================================
    
    def add_wise_account(self, email: str, label: str = None) -> Dict[str, Any]:
        """Wise account setup is private/assisted and not exposed in the public SDK."""
        raise ShegerPayError("Wise account setup is private/assisted and is intentionally not exposed in the public SDK.", status_code=400)
    
    def add_payoneer_account(self, email: str, label: str = None) -> Dict[str, Any]:
        """Payoneer account setup is private/assisted and not exposed in the public SDK."""
        raise ShegerPayError("Payoneer account setup is private/assisted and is intentionally not exposed in the public SDK.", status_code=400)
    
    def get_gmail_status(self) -> Dict[str, Any]:
        """Check Gmail forwarding bot status."""
        return self._request('GET', '/api/v1/international/gmail/status')

    # =========================================================================
    # MONITORING & HEALTH
    # =========================================================================
    
    def get_health(self) -> Dict[str, Any]:
        """Get detailed health check including database, providers, encryption status."""
        return self._request('GET', '/api/v1/monitoring/health')
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status and uptime of all payment providers (CBE, Telebirr, etc.)."""
        return self._request('GET', '/api/v1/monitoring/providers')
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get API usage metrics - verification counts, rate limits, feature access."""
        return self._request('GET', '/api/v1/monitoring/metrics')
    
    def get_uptime(self) -> Dict[str, Any]:
        """Get historical uptime data and last incident information."""
        return self._request('GET', '/api/v1/monitoring/uptime')

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================
    
    def get_notification_settings(self) -> Dict[str, Any]:
        """Get email and Telegram notification preferences."""
        return self._request('GET', '/api/v1/notifications/settings')
    
    def configure_telegram(
        self,
        bot_token: str,
        chat_id: str,
        notify_on_payment: bool = True,
        notify_on_security: bool = True
    ) -> Dict[str, Any]:
        """
        Configure Telegram notifications.
        
        Args:
            bot_token: Your Telegram bot token from @BotFather
            chat_id: Chat ID to send notifications to
            notify_on_payment: Notify on payment verification
            notify_on_security: Notify on security events (2FA, login, etc.)
        
        Returns:
            Configuration result
        
        Example:
            client.configure_telegram(
                bot_token='123456:ABC...',
                chat_id='-1001234567890'
            )
        """
        self._session.headers['Content-Type'] = 'application/json'
        data = {
            'bot_token': bot_token,
            'chat_id': chat_id,
            'notify_on_payment': notify_on_payment,
            'notify_on_security': notify_on_security
        }
        response = self._request('POST', '/api/v1/notifications/telegram/configure', data=data)
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def test_telegram(self) -> Dict[str, Any]:
        """Send a test Telegram notification."""
        self._session.headers['Content-Type'] = 'application/json'
        response = self._request('POST', '/api/v1/notifications/telegram/test', data={})
        self._session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    def disable_telegram(self) -> Dict[str, Any]:
        """Disable Telegram notifications."""
        return self._request('DELETE', '/api/v1/notifications/telegram')


# Convenience function
def verify(api_key: str, transaction_id: str, amount: float, **kwargs) -> VerificationResult:
    """
    Quick verification without creating a client.
    
    Usage:
        import shegerpay
        result = shegerpay.verify("sk_test_xxx", "FT123456", 100)
    """
    client = ShegerPay(api_key)
    return client.verify(transaction_id=transaction_id, amount=amount, **kwargs)


__version__ = "2.2.0"
__all__ = ['ShegerPay', 'VerificationResult', 'Transaction', 'Provider', 'ShegerPayError', 'verify']
