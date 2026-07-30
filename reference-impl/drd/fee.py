"""Inbox-fee and class-rejection encodings (§4.3).

Fees are exact decimal — an 8-byte signed int64 counting 10^-8 CC units, never floating
point. Class rejection is a signed denomination floor. Both are pure value logic (no
wire framing), kept apart from the message layouts so they can be unit-tested directly.
"""
from ._io import DRDError, be64s
from .constants import FEE_UNITS_PER_CC, FEE_MAX_FRACTION_DIGITS


def cc_to_units(cc_str: str) -> int:
    """Decimal CC string -> signed int64 count of 10^-8 CC units, exactly.

    `"10992.934002"` -> 1099293400200. Rejects more than 8 fractional digits (§4.3:
    they cannot be represented and MUST NOT be sent).
    """
    cc_str = cc_str.strip()
    neg = cc_str.startswith("-")
    s = cc_str[1:] if neg else cc_str
    whole, _, frac = s.partition(".")
    if len(frac) > FEE_MAX_FRACTION_DIGITS:
        raise DRDError(f"fee has more than {FEE_MAX_FRACTION_DIGITS} fractional digits: "
                       f"{cc_str!r}")
    if whole and not whole.isdigit():
        raise DRDError(f"invalid fee: {cc_str!r}")
    if frac and not frac.isdigit():
        raise DRDError(f"invalid fee: {cc_str!r}")
    frac = (frac + "0" * FEE_MAX_FRACTION_DIGITS)[:FEE_MAX_FRACTION_DIGITS]
    units = (int(whole or 0) * FEE_UNITS_PER_CC) + int(frac or 0)
    return -units if neg else units


def units_to_cc(units: int) -> str:
    """Inverse of cc_to_units — a canonical decimal string (8 fractional digits)."""
    neg = units < 0
    u = -units if neg else units
    whole, frac = divmod(u, FEE_UNITS_PER_CC)
    return f"{'-' if neg else ''}{whole}.{frac:08d}"


def encode_fee(fee_units: int) -> bytes:
    """8-byte big-endian signed fee. Negative fees are rejected (ERROR_INVALID_PARAMETER)."""
    if fee_units < 0:
        raise DRDError("negative inbox fee is rejected (ERROR_INVALID_PARAMETER 198)")
    return be64s(fee_units)


def class_rejects(class_rejection: int, sender_denomination: int) -> bool:
    """Does a user with this (signed) class-rejection floor reject a sender at this
    (signed) address denomination? `0` = accept all; otherwise reject senders strictly
    below the floor by signed comparison (§4.3). A whitelist entry bypasses this — that
    decision lives at the QMail Tell gate, not here.
    """
    if class_rejection == 0:
        return False
    return sender_denomination < class_rejection
