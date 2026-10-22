"""
Cart and checkout blueprint managing shopping cart, payment, order placement, and history.
"""
import time
from typing import Tuple, Dict, Any
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from config import Config
from services.order_service import OrderService
from blueprints.helpers import require_login
from extensions import csrf

logger = logging.getLogger(__name__)

cart_bp = Blueprint('cart', __name__)


@cart_bp.route('/cart', endpoint='cart')
def cart() -> str:
    """Display shopping cart page."""
    if 'user_id' not in session:
        flash('Please log in to access your cart!', 'error')
        return redirect(url_for('auth.login', next=url_for('cart.cart')))
    return render_template('cart.html')


@cart_bp.route('/payment', endpoint='payment')
@require_login
def payment() -> str:
    """Display payment page."""
    return render_template('payment.html', razorpay_key_id=Config.RAZORPAY_KEY_ID)


@cart_bp.route('/api/create-order', methods=['POST'], endpoint='api_create_order')
@cart_bp.route('/api/v1/payment/create-order', methods=['POST'], endpoint='api_create_razorpay_order')
def api_create_order() -> Tuple[Any, int]:
    """
    Initialize a Razorpay order.
    Complies with Razorpay Standard Checkout specification:
    - Calls Razorpay API: POST https://api.razorpay.com/v1/orders
    - Request: { amount (paise), currency, receipt }
    - Return: { order_id, amount, currency }
    - Minimum amount: 100 paise
    - Error handling: amount < 100 (400), auth failures (401), API errors (500)
    """
    from services.payment_service import PaymentService
    from services.idempotency_service import IdempotencyService

    idempotency_key = IdempotencyService.get_idempotency_key_from_request()
    if idempotency_key:
        can_proceed, cached_resp, status_code = IdempotencyService.acquire(idempotency_key, user_id=session.get('user_id'))
        if not can_proceed:
            return jsonify(cached_resp), (status_code or 200)

    data = request.get_json(silent=True) or {}

    # Check unauthenticated access when no order data or products
    if 'user_id' not in session and 'amount' not in data and 'products' not in data:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'error': 'Unauthorized', 'message': 'Authentication required. Please log in.'}), 401

    products = data.get('products')
    currency = data.get('currency', 'INR')
    notes = data.get('notes', {})

    if 'amount' in data:
        # Direct amount provided in paise
        try:
            amount_in_paise = int(data['amount'])
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid amount', 'message': 'Amount must be an integer representing paise'}), 400

        if amount_in_paise < 100:
            return jsonify({'success': False, 'error': 'Amount too small', 'message': 'Amount must be at least 100 paise'}), 400

        receipt = data.get('receipt', f"rcpt_{int(time.time())}")
        subtotal = round(amount_in_paise / 100.0, 2)
        fee = 0.0
        final_total = subtotal

    elif products:
        # DailyDrop cart products calculation
        valid, err_msg, subtotal, fee, final_total = PaymentService.calculate_authoritative_total(products)
        if not valid:
            return jsonify({'success': False, 'error': err_msg, 'message': err_msg}), 400

        amount_in_paise = int(round(final_total * 100))
        if amount_in_paise < 100:
            return jsonify({'success': False, 'error': 'Amount too small', 'message': 'Amount must be at least 100 paise'}), 400

        user_prefix = session.get('user_id', 'anon')
        receipt = data.get('receipt', f"rcpt_u{user_prefix}_{int(time.time())}")
        notes.update({'user_id': str(user_prefix), 'phone': data.get('phone_number', '')})

    else:
        return jsonify({'success': False, 'error': 'Missing parameters', 'message': 'Either amount (in paise) or products list must be provided'}), 400

    # Call PaymentService to create the order with Razorpay
    success, message, rzp_order, status_code = PaymentService.create_order(
        amount_in_paise=amount_in_paise,
        receipt=receipt,
        currency=currency,
        notes=notes
    )

    if not success or not rzp_order:
        return jsonify({
            'success': False,
            'error': message,
            'message': message
        }), status_code

    # Persist pending checkout in database to safeguard against customer disconnects
    if rzp_order and rzp_order.get('id'):
        try:
            from database import save_pending_order
            save_pending_order(
                razorpay_order_id=rzp_order.get('id'),
                user_id=session.get('user_id'),
                full_name=data.get('full_name', '') or session.get('name', 'Customer'),
                phone_number=data.get('phone_number', ''),
                address=data.get('address', ''),
                products=products if products else [],
                total_amount=final_total
            )
        except Exception as pe:
            logger.warning(f"Could not persist pending order details for {rzp_order.get('id')}: {pe}")

    response_payload = {
        'success': True,
        'order_id': rzp_order.get('id'),
        'id': rzp_order.get('id'),
        'amount': rzp_order.get('amount'),
        'currency': rzp_order.get('currency', 'INR'),
        'key_id': Config.RAZORPAY_KEY_ID,
        'receipt': rzp_order.get('receipt'),
        'subtotal': subtotal,
        'delivery_fee': fee,
        'final_total': final_total
    }
    if idempotency_key:
        IdempotencyService.complete(idempotency_key, response_payload, status_code=200)

    return jsonify(response_payload), 200


@cart_bp.route('/api/verify-payment', methods=['POST'], endpoint='api_verify_payment')
@cart_bp.route('/api/v1/payment/verify', methods=['POST'], endpoint='api_verify_razorpay_payment')
def api_verify_payment() -> Tuple[Any, int]:
    """
    Cryptographically verify Razorpay payment signature and persist order.
    Algorithm: HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
    Compare generated signature with razorpay_signature.
    Return success only if signatures match.
    """
    from services.payment_service import PaymentService
    from services.idempotency_service import IdempotencyService
    data = request.get_json(silent=True) or {}
    razorpay_order_id = data.get('razorpay_order_id') or data.get('order_id')

    razorpay_payment_id = data.get('razorpay_payment_id') or data.get('payment_id')
    razorpay_signature = data.get('razorpay_signature') or data.get('signature')

    # Idempotency check: prevent duplicate verification requests
    idempotency_key = IdempotencyService.get_idempotency_key_from_request()
    if not idempotency_key and razorpay_payment_id:
        idempotency_key = f"rzp_pay_{razorpay_payment_id}"

    if idempotency_key:
        can_proceed, cached_resp, status_code = IdempotencyService.acquire(idempotency_key, user_id=session.get('user_id'))
        if not can_proceed:
            return jsonify(cached_resp), (status_code or 200)

    # 1. Require authenticated session
    user_id = session.get('user_id')
    if not user_id:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'error': 'Unauthorized', 'message': 'Authentication required. Please log in.'}), 401

    # 2. Missing fields check
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({
            'success': False,
            'status': 'failure',
            'error': 'Missing fields',
            'message': 'Missing required fields: razorpay_order_id, razorpay_payment_id, razorpay_signature'
        }), 400


    # 3. Cryptographic signature validation using HMAC-SHA256
    is_valid = PaymentService.verify_payment_signature(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature
    )
    if not is_valid:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({
            'success': False,
            'status': 'failure',
            'error': 'Signature mismatch',
            'message': 'Invalid payment signature. Transaction rejected.'
        }), 400

    # 4. Check if order was already recorded (idempotent retry from client or webhook)
    from database import get_db_connection, get_pending_order, delete_pending_order
    from psycopg2.extras import RealDictCursor

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    'SELECT order_id, user_id FROM orders WHERE payment_id = %s OR payment_id = %s',
                    (razorpay_payment_id, razorpay_order_id)
                )
                existing = cursor.fetchone()
                if existing:
                    existing_uid = existing['user_id'] if isinstance(existing, dict) else existing[1]
                    if str(existing_uid) != str(user_id):
                        if idempotency_key:
                            IdempotencyService.release(idempotency_key)
                        return jsonify({
                            'success': False,
                            'error': 'Forbidden',
                            'message': 'Unauthorized: Payment order does not belong to this user'
                        }), 403

                    ord_id = existing['order_id'] if isinstance(existing, dict) else existing[0]
                    res_payload = {
                        'success': True,
                        'status': 'success',
                        'order_id': ord_id,
                        'payment_id': razorpay_payment_id,
                        'razorpay_order_id': razorpay_order_id,
                        'message': 'Payment already verified and order recorded.'
                    }
                    if idempotency_key:
                        IdempotencyService.complete(idempotency_key, res_payload, status_code=200)
                    return jsonify(res_payload), 200
    except Exception as db_err:
        logger.warning(f"Error checking existing order: {db_err}")

    # 5. Require a valid pending order owned by current user
    pending = None
    try:
        pending = get_pending_order(razorpay_order_id)
    except Exception as pe:
        logger.warning(f"Could not load pending order {razorpay_order_id}: {pe}")

    if not pending:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({
            'success': False,
            'error': 'Missing pending order',
            'message': 'No pending order found for this payment transaction. Please restart checkout.'
        }), 400

    pending_user_id = pending.get('user_id')
    if not pending_user_id or str(pending_user_id) != str(user_id):
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({
            'success': False,
            'error': 'Forbidden',
            'message': 'Unauthorized: Payment order does not belong to this user'
        }), 403

    # Extract cart products from pending order
    products = pending.get('products_data', [])
    if isinstance(products, str):
        import json
        try:
            products = json.loads(products)
        except Exception:
            products = []

    if not products:
        products = data.get('products', [])

    if not products:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'error': 'Empty cart', 'message': 'Cart cannot be empty'}), 400

    # 6. Authoritative price & total recalculation from database
    valid, err_msg, subtotal, fee, final_total = PaymentService.calculate_authoritative_total(products, require_catalog=True)
    if not valid:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'error': err_msg, 'message': err_msg}), 400

    full_name = pending.get('full_name') or data.get('full_name', '') or session.get('name', 'Customer')
    phone_number = pending.get('phone_number') or data.get('phone_number', '')
    address = pending.get('address') or data.get('address', '')

    success, message, order_id = OrderService.create_order(
        user_id=user_id,
        full_name=full_name,
        phone_number=phone_number,
        address=address,
        products=products,
        total_amount=final_total,
        payment_method='Razorpay',
        payment_id=razorpay_payment_id,
        status='Paid'
    )

    if not success:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'error': message, 'message': message}), 500

    try:
        delete_pending_order(razorpay_order_id)
    except Exception:
        pass

    user_orders = OrderService.get_user_orders(user_id)
    user_order_number = len(user_orders)

    res_payload = {
        'success': True,
        'status': 'success',
        'order_id': order_id,
        'user_order_number': user_order_number,
        'payment_id': razorpay_payment_id,
        'razorpay_order_id': razorpay_order_id,
        'message': 'Payment verified and order placed successfully!'
    }
    if idempotency_key:
        IdempotencyService.complete(idempotency_key, res_payload, status_code=200)

    return jsonify(res_payload), 200


@cart_bp.route('/api/v1/payment/webhook', methods=['POST'], endpoint='api_razorpay_webhook')
@cart_bp.route('/api/payment/webhook', methods=['POST'], endpoint='api_razorpay_webhook_alt')
@csrf.exempt
def api_razorpay_webhook() -> Tuple[Any, int]:
    """
    Razorpay Server Webhook Endpoint.
    Prevents lost orders if client disconnects, crashes, or drops network after payment.

    - Cryptographically verifies X-Razorpay-Signature header (HMAC SHA-256).
    - Checks for existing order to guarantee idempotency.
    - Prevents fulfillment state regression on out-of-order events.
    - Automatically recovers and places orders from pending_orders table if client disconnected.
    """
    import json
    from services.payment_service import PaymentService
    from database import get_db_connection, get_pending_order, delete_pending_order
    from psycopg2.extras import RealDictCursor

    signature = request.headers.get('X-Razorpay-Signature', '')
    raw_body = request.get_data()

    if not signature or not raw_body:
        return jsonify({'status': 'failure', 'error': 'Missing webhook signature or payload'}), 400

    if not PaymentService.verify_webhook_signature(raw_body, signature):
        return jsonify({'status': 'failure', 'error': 'Invalid webhook signature'}), 400

    event_payload = request.get_json(silent=True) or {}
    event_type = event_payload.get('event')
    logger.info(f"Verified Razorpay webhook event received: {event_type}")

    if event_type in ['payment.captured', 'order.paid']:
        payment_entity = event_payload.get('payload', {}).get('payment', {}).get('entity', {})
        rzp_payment_id = payment_entity.get('id')
        rzp_order_id = payment_entity.get('order_id') or event_payload.get('payload', {}).get('order', {}).get('entity', {}).get('id')

        if not rzp_order_id and not rzp_payment_id:
            return jsonify({'status': 'ignored', 'message': 'No payment or order ID present in webhook event'}), 200

        # 1. Idempotency Check: check if order already recorded
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        'SELECT order_id, status FROM orders WHERE payment_id = %s OR payment_id = %s',
                        (rzp_payment_id, rzp_order_id)
                    )
                    existing_order = cursor.fetchone()
                    if existing_order:
                        ord_id = existing_order['order_id'] if isinstance(existing_order, dict) else existing_order[0]
                        # Safe transition: only mark Paid if not already past in lifecycle
                        cursor.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s AND status IN ('Processing', 'Created')", (ord_id,))
                        try:
                            from services.outbox_service import OutboxService
                            OutboxService.record_event(
                                cursor=cursor,
                                event_type='PAYMENT_CONFIRMED',
                                aggregate_type='order',
                                aggregate_id=ord_id,
                                payload={'order_id': ord_id, 'payment_id': rzp_payment_id, 'event': event_type}
                            )
                        except Exception:
                            pass
                        if rzp_order_id:
                            delete_pending_order(rzp_order_id)
                        logger.info(f"Webhook: Order #{ord_id} already exists. Idempotently acknowledged.")
                        try:
                            from services.outbox_service import OutboxService
                            OutboxService.relay_events(limit=5)
                        except Exception:
                            pass
                        return jsonify({'status': 'already_processed', 'order_id': ord_id}), 200
        except Exception as q_err:
            logger.error(f"Webhook error querying existing orders: {q_err}")

        # 2. Client Disconnect Recovery: order was not yet placed by client browser
        if rzp_order_id:
            pending = get_pending_order(rzp_order_id)
            if pending:
                u_id = pending.get('user_id')
                f_name = pending.get('full_name', 'Customer')
                p_phone = pending.get('phone_number', '')
                p_addr = pending.get('address', '')
                p_raw = pending.get('products_data', '[]')
                p_tot = float(pending.get('total_amount', 0.0))

                try:
                    p_items = json.loads(p_raw) if isinstance(p_raw, str) else p_raw
                except Exception:
                    p_items = []

                if u_id and p_items and p_tot > 0:
                    rec_success, rec_msg, rec_order_id = OrderService.create_order(
                        user_id=u_id,
                        full_name=f_name,
                        phone_number=p_phone,
                        address=p_addr,
                        products=p_items,
                        total_amount=p_tot,
                        payment_method='Razorpay',
                        payment_id=rzp_payment_id or rzp_order_id,
                        status='Paid'
                    )
                    if rec_success:
                        delete_pending_order(rzp_order_id)
                        logger.info(f"Webhook: Successfully recovered disconnected customer order #{rec_order_id} for user #{u_id}")
                        return jsonify({'status': 'order_recovered', 'order_id': rec_order_id}), 200
                    else:
                        logger.error(f"Webhook: Failed to recover order from pending: {rec_msg}")
                        return jsonify({'status': 'recovery_failed', 'error': rec_msg}), 500

    elif event_type == 'payment.failed':
        # Safely log payment failure without regressing completed orders
        payment_entity = event_payload.get('payload', {}).get('payment', {}).get('entity', {})
        rzp_order_id = payment_entity.get('order_id')
        error_desc = payment_entity.get('error_description', 'Payment failed at gateway')
        logger.warning(f"Razorpay webhook payment.failed for order {rzp_order_id}: {error_desc}")
        return jsonify({'status': 'acknowledged', 'event': event_type, 'message': 'Payment failure noted'}), 200

    return jsonify({'status': 'acknowledged', 'event': event_type}), 200



@cart_bp.route('/place_order', methods=['POST'], endpoint='place_order')
@require_login
def place_order() -> Tuple[Any, int]:
    """Process Cash on Delivery (COD) order placement with Idempotency protection."""
    from services.payment_service import PaymentService
    from services.idempotency_service import IdempotencyService

    # 1. Idempotency Key check: prevents duplicate order placement
    idempotency_key = IdempotencyService.get_idempotency_key_from_request()
    if idempotency_key:
        can_proceed, cached_resp, status_code = IdempotencyService.acquire(idempotency_key, user_id=session.get('user_id'))
        if not can_proceed:
            return jsonify(cached_resp), (status_code or 200)

    data = request.get_json(silent=True) or {}
    if not data:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'message': 'No data received'}), 400

    full_name = data.get('full_name', '')
    phone_number = data.get('phone_number', '')
    address = data.get('address', '')
    products = data.get('products', [])

    valid, err_msg, subtotal, fee, final_total = PaymentService.calculate_authoritative_total(products)
    if not valid:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'message': err_msg}), 400

    success, message, order_id = OrderService.create_order(
        user_id=session['user_id'],
        full_name=full_name,
        phone_number=phone_number,
        address=address,
        products=products,
        total_amount=final_total,
        payment_method=data.get('payment_method', 'COD'),
        status='Processing'
    )

    if not success:
        if idempotency_key:
            IdempotencyService.release(idempotency_key)
        return jsonify({'success': False, 'message': message}), 400

    user_orders = OrderService.get_user_orders(session['user_id'])
    user_order_number = len(user_orders)

    res_payload = {
        'success': True,
        'order_id': order_id,
        'user_order_number': user_order_number,
        'message': message
    }

    if idempotency_key:
        IdempotencyService.complete(idempotency_key, res_payload, status_code=200)

    return jsonify(res_payload), 200


@cart_bp.route('/orders', endpoint='orders')
@require_login
def orders() -> str:
    """Display user's order history."""
    user_orders = OrderService.get_user_orders(session['user_id'])
    return render_template('orders.html', orders=user_orders)


# ==================== Wishlist Routes ====================

@cart_bp.route('/wishlist', endpoint='wishlist')
@require_login
def wishlist() -> str:
    """Display user's saved wishlist products."""
    from services.wishlist_service import WishlistService
    items = WishlistService.get_user_wishlist(session['user_id'])
    return render_template('wishlist.html', wishlist_items=items)


@cart_bp.route('/api/v1/wishlist/toggle', methods=['POST'], endpoint='api_toggle_wishlist')
@require_login
def api_toggle_wishlist() -> Tuple[Any, int]:
    """Toggle item in wishlist via AJAX."""
    from services.wishlist_service import WishlistService
    data = request.get_json(silent=True) or request.form
    product_id = data.get('product_id')
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid product ID'}), 400

    success, message, in_wishlist, count = WishlistService.toggle_item(session['user_id'], product_id)
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'in_wishlist': in_wishlist,
            'count': count,
            'product_id': product_id
        }), 200
    return jsonify({'success': False, 'message': message}), 400


@cart_bp.route('/api/v1/wishlist/remove', methods=['POST'], endpoint='api_remove_wishlist')
@require_login
def api_remove_wishlist() -> Tuple[Any, int]:
    """Remove item from wishlist via AJAX."""
    from services.wishlist_service import WishlistService
    data = request.get_json(silent=True) or request.form
    product_id = data.get('product_id')
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid product ID'}), 400

    success, message, count = WishlistService.remove_item(session['user_id'], product_id)
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'count': count,
            'product_id': product_id
        }), 200
    return jsonify({'success': False, 'message': message}), 400


@cart_bp.route('/api/v1/wishlist/ids', methods=['GET'], endpoint='api_wishlist_ids')
def api_wishlist_ids() -> Tuple[Any, int]:
    """Retrieve list of product IDs currently in user's wishlist."""
    from services.wishlist_service import WishlistService
    if 'user_id' not in session:
        return jsonify({'success': True, 'ids': [], 'count': 0, 'logged_in': False}), 200

    ids = WishlistService.get_user_wishlist_ids(session['user_id'])
    return jsonify({
        'success': True,
        'ids': ids,
        'count': len(ids),
        'logged_in': True
    }), 200

