"""
Payment service providing Razorpay payment integration, order creation,
and cryptographic signature verification.
"""
from typing import Optional, Dict, Any, Tuple, List
import hmac
import hashlib
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)


class PaymentService:
    """Service handling Razorpay payment order initialization and verification."""

    BASE_URL = "https://api.razorpay.com/v1"

    @classmethod
    def get_credentials(cls) -> Tuple[str, str]:
        """Retrieve Razorpay Key ID and Secret from application configuration."""
        key_id = Config.RAZORPAY_KEY_ID
        key_secret = Config.RAZORPAY_KEY_SECRET
        return key_id, key_secret

    @classmethod
    def calculate_authoritative_total(cls, products: List[Dict[str, Any]]) -> Tuple[bool, str, float, float, float]:
        """
        Authoritatively calculates subtotal, delivery fee, and final payable amount
        to prevent client-side price tampering.

        Returns:
            Tuple of (success, message, subtotal, delivery_fee, final_total)
        """
        if not products or not isinstance(products, list):
            return False, "Cart cannot be empty", 0.0, 0.0, 0.0

        subtotal = 0.0
        for item in products:
            try:
                price = float(item.get('price', 0))
                quantity = int(item.get('quantity', 1))
                if price <= 0 or quantity <= 0:
                    return False, f"Invalid price or quantity for item: {item.get('name', 'product')}", 0.0, 0.0, 0.0
                subtotal += price * quantity
            except (ValueError, TypeError):
                return False, "Invalid product data format", 0.0, 0.0, 0.0

        # Business Rule: Free delivery for orders >= Rs. 500, else Rs. 30 delivery charge
        delivery_fee = 0.0 if subtotal >= 500.0 else 30.0
        final_total = round(subtotal + delivery_fee, 2)
        subtotal = round(subtotal, 2)

        return True, "", subtotal, delivery_fee, final_total

    @classmethod
    def create_order(
        cls,
        amount_in_paise: int,
        receipt: Optional[str] = None,
        currency: str = "INR",
        notes: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]], int]:
        """
        Create a new Razorpay Order on Razorpay servers.

        Args:
            amount_in_paise: Order amount in paise (1 INR = 100 paise). Minimum: 100 paise.
            receipt: Internal receipt or order identifier.
            currency: Currency code (default: 'INR').
            notes: Optional dictionary of metadata notes.

        Returns:
            Tuple of (success, message, razorpay_order_dict, http_status_code).
        """
        key_id, key_secret = cls.get_credentials()
        if not key_id or not key_secret:
            logger.error("Razorpay API credentials not configured.")
            return False, "Razorpay API credentials not configured", None, 500

        # Validate minimum amount (>= 100 paise per Razorpay specification)
        try:
            amount_val = int(amount_in_paise)
        except (ValueError, TypeError):
            return False, "Invalid amount format. Must be an integer representing paise.", None, 400

        if amount_val < 100:
            return False, "Amount must be at least 100 paise", None, 400

        payload = {
            "amount": amount_val,
            "currency": currency or "INR",
            "receipt": receipt or "rcpt_order",
            "payment_capture": 1,
            "notes": notes or {"app": "DailyDrop"}
        }

        try:
            response = requests.post(
                f"{cls.BASE_URL}/orders",
                auth=(key_id, key_secret),
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Created Razorpay order: {data.get('id')} for amount: {amount_val} paise")
                return True, "Razorpay order created successfully", data, 200
            elif response.status_code == 401:
                logger.error(f"Razorpay authentication failure (401): {response.text}")
                return False, "Razorpay authentication failed: Invalid Key or Secret", None, 401
            else:
                error_msg = f"Razorpay API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return False, f"Failed to create order with Razorpay: {response.status_code}", None, 500

        except requests.RequestException as e:
            logger.error(f"Network error communicating with Razorpay: {e}")
            return False, "Payment gateway connection error", None, 500

    @classmethod
    def create_razorpay_order(
        cls,
        amount: float,
        receipt: str,
        notes: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Backwards-compatible helper accepting amount in Rupees (INR).
        Converts Rupees to paise and delegates to create_order.
        """
        amount_in_paise = int(round(amount * 100))
        success, message, data, _ = cls.create_order(
            amount_in_paise=amount_in_paise,
            receipt=receipt,
            currency="INR",
            notes=notes
        )
        return success, message, data

    @classmethod
    def verify_payment_signature(cls, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Verify Razorpay cryptographic payment signature using HMAC SHA256.

        Algorithm:
            HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
            Compare generated signature with razorpay_signature

        Args:
            razorpay_order_id: The order ID returned during creation (order_xxx).
            razorpay_payment_id: The payment ID returned upon client checkout (pay_xxx).
            razorpay_signature: The hexadecimal signature returned from Razorpay Checkout.

        Returns:
            True if signature matches mathematically, False otherwise.
        """
        _, key_secret = cls.get_credentials()
        if not key_secret or not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            logger.warning("Missing required arguments for payment signature verification")
            return False

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        secret_bytes = key_secret.encode("utf-8")

        expected_signature = hmac.new(
            secret_bytes,
            message,
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected_signature, razorpay_signature)
        if not is_valid:
            logger.warning(
                f"Invalid Razorpay signature for order {razorpay_order_id}. "
                f"Received: {razorpay_signature}, Expected: {expected_signature}"
            )
        else:
            logger.info(f"Successfully verified payment signature for payment {razorpay_payment_id}")

        return is_valid

    @classmethod
    def verify_webhook_signature(cls, raw_body: bytes, signature: str) -> bool:
        """
        Verify Razorpay Webhook cryptographic signature using HMAC SHA256.

        Algorithm:
            HMAC-SHA256(request.data, WEBHOOK_SECRET)
            Compare generated signature with X-Razorpay-Signature header.

        Args:
            raw_body: The raw request bytes from request.get_data().
            signature: The hexadecimal signature from X-Razorpay-Signature header.

        Returns:
            True if signature matches mathematically, False otherwise.
        """
        webhook_secret = getattr(Config, 'RAZORPAY_WEBHOOK_SECRET', '') or Config.RAZORPAY_KEY_SECRET
        if not webhook_secret or not signature or not raw_body:
            logger.warning("Missing webhook secret, signature, or body for webhook signature verification")
            return False

        secret_bytes = webhook_secret.encode("utf-8")
        expected_signature = hmac.new(
            secret_bytes,
            raw_body,
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning(f"Invalid Razorpay webhook signature. Received: {signature}, Expected: {expected_signature}")
        else:
            logger.info("Successfully verified Razorpay webhook signature")
        return is_valid
