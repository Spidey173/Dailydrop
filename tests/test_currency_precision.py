"""
Unit and integration tests for exact Decimal financial precision.
Verifies rounding behavior (ROUND_HALF_UP), floating-point boundary cases,
subtotal aggregation, paise conversions, and boundary threshold delivery fees.
"""
from decimal import Decimal
import pytest
from services.currency_service import CurrencyService
from services.payment_service import PaymentService
from services.catalog_validation_service import CatalogValidationService


def test_currency_service_to_decimal():
    """Verify robust conversion to Decimal without float representation noise."""
    assert CurrencyService.to_decimal(19.99) == Decimal('19.99')
    assert CurrencyService.to_decimal('19.99') == Decimal('19.99')
    assert CurrencyService.to_decimal(100) == Decimal('100.00')
    assert CurrencyService.to_decimal(None) == Decimal('0.00')
    assert CurrencyService.to_decimal('') == Decimal('0.00')

    with pytest.raises(ValueError):
        CurrencyService.to_decimal("invalid-money")


def test_floating_point_imprecision_prevention():
    """
    Classic IEEE-754 floating point arithmetic issue: 0.1 + 0.2 = 0.30000000000000004.
    CurrencyService must guarantee exact 0.30.
    """
    p1 = CurrencyService.to_decimal(0.1)
    p2 = CurrencyService.to_decimal(0.2)
    assert p1 + p2 == Decimal('0.30')
    assert CurrencyService.round_money(p1 + p2) == Decimal('0.30')


def test_paise_conversion_exactness():
    """Verify paise conversions do not suffer off-by-one truncation errors."""
    # 29.99 * 100 in float can be 2998.9999999999995 -> int(2998.9999) = 2998 (off by 1)
    # CurrencyService.to_paise must yield exactly 2999
    assert CurrencyService.to_paise(29.99) == 2999
    assert CurrencyService.to_paise('29.99') == 2999
    assert CurrencyService.to_paise(Decimal('29.99')) == 2999

    assert CurrencyService.from_paise(2999) == Decimal('29.99')
    assert CurrencyService.from_paise(100) == Decimal('1.00')
    assert CurrencyService.from_paise(1) == Decimal('0.01')


def test_rounding_boundary_half_up():
    """Test HALF_UP tie-breaking standard across monetary thresholds."""
    # 0.005 rounds up to 0.01
    assert CurrencyService.round_money('0.005') == Decimal('0.01')
    # 0.004 rounds down to 0.00
    assert CurrencyService.round_money('0.004') == Decimal('0.00')
    # 0.015 rounds up to 0.02
    assert CurrencyService.round_money('0.015') == Decimal('0.02')
    # 0.025 rounds up to 0.03
    assert CurrencyService.round_money('0.025') == Decimal('0.03')


def test_authoritative_total_decimal_accumulation():
    """
    Accumulating multiple fractional prices that would cause float drift.
    E.g., 3 items at 33.33 + 3 items at 66.67.
    """
    products = [
        {"name": "Item A", "price": 33.33, "quantity": 3},  # 99.99
        {"name": "Item B", "price": 66.67, "quantity": 3},  # 200.01
    ]
    # require_catalog=False tests the pure calculation path with simulated items
    valid, msg, subtotal, fee, total = PaymentService.calculate_authoritative_total(products, require_catalog=False)
    assert valid is True
    # Subtotal = 99.99 + 200.01 = 300.00
    assert subtotal == 300.00
    # Under Rs. 500 threshold, so fee = 30.00
    assert fee == 30.00
    assert total == 330.00


def test_free_delivery_boundary_cases():
    """
    Test boundary cases around the Rs. 500 free-delivery threshold:
      - 499.99: delivery fee applies (Rs. 30) -> total = 529.99
      - 500.00: free delivery (Rs. 0) -> total = 500.00
      - 500.01: free delivery (Rs. 0) -> total = 500.01
    """
    # 1. Just below threshold
    cart_below = [{"name": "Below", "price": 499.99, "quantity": 1}]
    valid, _, subtotal, fee, total = PaymentService.calculate_authoritative_total(cart_below, require_catalog=False)
    assert valid is True
    assert subtotal == 499.99
    assert fee == 30.00
    assert total == 529.99

    # 2. Exactly on threshold
    cart_exact = [{"name": "Exact", "price": 500.00, "quantity": 1}]
    valid, _, subtotal, fee, total = PaymentService.calculate_authoritative_total(cart_exact, require_catalog=False)
    assert valid is True
    assert subtotal == 500.00
    assert fee == 0.00
    assert total == 500.00

    # 3. Just above threshold
    cart_above = [{"name": "Above", "price": 500.01, "quantity": 1}]
    valid, _, subtotal, fee, total = PaymentService.calculate_authoritative_total(cart_above, require_catalog=False)
    assert valid is True
    assert subtotal == 500.01
    assert fee == 0.00
    assert total == 500.01
