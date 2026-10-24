"""
Currency and financial precision service.
Guarantees exact Decimal representation for monetary calculations,
preventing IEEE-754 binary floating-point inaccuracies.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Union

TWO_PLACES = Decimal('0.01')
ZERO = Decimal('0.00')


class CurrencyService:
    """Service providing exact decimal arithmetic, currency formatting, and paise conversion."""

    @staticmethod
    def to_decimal(value: Any) -> Decimal:
        """
        Safely converts any numeric or string representation into a quantized 2-decimal Decimal.
        Uses string conversion to avoid float representation artifacts.
        """
        if value is None:
            return ZERO
        if isinstance(value, Decimal):
            return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        try:
            # Converting via str() preserves the literal digits provided
            str_val = str(value).strip()
            if not str_val:
                return ZERO
            return Decimal(str_val).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"Cannot convert {repr(value)} to valid monetary Decimal")

    @classmethod
    def round_money(cls, amount: Union[Decimal, float, int, str]) -> Decimal:
        """Quantizes an amount to 2 decimal places using standard ROUND_HALF_UP."""
        return cls.to_decimal(amount)

    @classmethod
    def to_paise(cls, amount: Union[Decimal, float, int, str]) -> int:
        """
        Converts Rupees to integer paise without floating-point truncation issues.
        Example: Decimal('19.99') -> 1999 paise.
        """
        dec_amount = cls.to_decimal(amount)
        # Multiply by 100 and quantize to whole integer
        paise_dec = (dec_amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        return int(paise_dec)

    @classmethod
    def from_paise(cls, paise: Union[int, str]) -> Decimal:
        """Converts integer paise to exact Decimal Rupees."""
        try:
            int_paise = int(paise)
            return (Decimal(int_paise) / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert paise {repr(paise)} to Decimal")
