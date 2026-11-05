"""GTIN / EAN / UPC helpers (GS1 check-digit rules). Pure functions, no Django imports."""

import re

VALID_LENGTHS = (8, 12, 13, 14)  # GTIN-8 (EAN-8), UPC-A, EAN-13, GTIN-14


def normalize_gtin(value) -> str:
    """Keep digits only, so '890-1234 56789 0' and '8901234567890' are treated alike."""
    return re.sub(r'\D', '', str(value or ''))


def check_digit(body: str) -> int:
    """GS1 check digit for the digits *before* the final one (weights 3,1,3,1... from the right)."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10


def is_valid_gtin(digits: str) -> bool:
    return len(digits) in VALID_LENGTHS and check_digit(digits[:-1]) == int(digits[-1])


def to_gtin14(digits: str) -> str:
    """Canonical form used for lookups/uniqueness: UPC-A and the same code as EAN-13 collapse to one value."""
    return digits.zfill(14)


def validate_gtin(value) -> str:
    """Return the normalised digits or raise ValueError with a user-readable message."""
    digits = normalize_gtin(value)
    if len(digits) not in VALID_LENGTHS:
        raise ValueError('Barcode must be 8, 12, 13 or 14 digits (EAN-8, UPC-A, EAN-13 or GTIN-14).')
    if not is_valid_gtin(digits):
        raise ValueError('Barcode check digit is invalid. Please re-scan or re-type the number.')
    return digits
