"""The Tell DRD gate: the per-recipient delivery decision (§4.5).

Before writing to each recipient's inbox, the beacon consults its [DRD/1.0] data and
decides, in a fixed order, whether the AN-authenticated sender may deliver and what fee
applies: blacklist → whitelist (free) → class rejection → inbox fee. This module is the
pure decision logic; it reuses DRD's signed class-rejection comparison so the two
standards cannot disagree. Fee/locker amounts are in 10^-8 CC units ([DRD/1.0] §4.3).

With multiple recipients, allowed recipients still deliver and the Tell returns 250; only
when *zero* recipients deliver does the most specific failure win.
"""
from dataclasses import dataclass

from drd import class_rejects
from drd.constants import LIST_WHITELIST, LIST_BLACKLIST
from ._errors import QMailError
from .constants import (
    STATUS_SUCCESS, ERROR_SENDER_BLACKLISTED, ERROR_SENDER_CLASS_REJECTED,
    ERROR_PAYMENT_REQUIRED, ERROR_PAYMENT_INSUFFICIENT, ERROR_WRONG_RAIDA,
    DEFAULT_TELL_FEE_UNITS,
)

# Precedence when zero recipients delivered: most specific failure wins (§4.5).
ZERO_DELIVERED_PRECEDENCE = (
    ERROR_SENDER_BLACKLISTED,     # 236
    ERROR_SENDER_CLASS_REJECTED,  # 237
    ERROR_PAYMENT_INSUFFICIENT,   # 168
    ERROR_PAYMENT_REQUIRED,       # 169
    ERROR_WRONG_RAIDA,            # 18
)

# The order the gate evaluates checks (informational; matches the vector).
EVALUATION_ORDER = ("blacklist", "whitelist", "class_rejection", "inbox_fee")


@dataclass
class GateOutcome:
    delivered: bool
    status: int          # STATUS_SUCCESS when delivered, else the failure status
    fee_charged: int = 0  # units actually consumed from the locker (0 when free/failed)
    reason: str = ""


@dataclass
class Recipient:
    """The DRD state the beacon has for one recipient of a Tell.

    `list_status` is None, DRD's LIST_WHITELIST (0), or LIST_BLACKLIST (1). When
    `has_drd_record` is False the recipient is charged the default Tell fee; otherwise
    `inbox_fee_units` and `class_rejection` come from their DRD record. `locker_units` is
    the funded locker the sender attached for this recipient (None = no locker).
    """
    sender_denomination: int
    list_status: int = None
    has_drd_record: bool = True
    inbox_fee_units: int = 0
    class_rejection: int = 0
    locker_units: int = None


def evaluate_recipient(r: Recipient) -> GateOutcome:
    """Decide one recipient's outcome, in the normative order (§4.5)."""
    # 1. Blacklist.
    if r.list_status == LIST_BLACKLIST:
        return GateOutcome(False, ERROR_SENDER_BLACKLISTED, reason="sender blacklisted")
    # 2. Whitelist → free, skipping class and fee checks.
    if r.list_status == LIST_WHITELIST:
        return GateOutcome(True, STATUS_SUCCESS, 0, "whitelisted: delivered free")
    # 3. Class rejection (signed comparison, via DRD).
    if r.has_drd_record and class_rejects(r.class_rejection, r.sender_denomination):
        return GateOutcome(False, ERROR_SENDER_CLASS_REJECTED,
                           reason="sender denomination below recipient class floor")
    # 4. Inbox fee. No record → the beacon's default Tell fee; else the record's fee.
    fee = r.inbox_fee_units if r.has_drd_record else DEFAULT_TELL_FEE_UNITS
    if fee < 0:
        raise QMailError("negative inbox fee is invalid (DRD/1.0 §4.3)")
    if fee == 0:
        return GateOutcome(True, STATUS_SUCCESS, 0, "free inbox (fee 0)")
    if r.locker_units is None:
        return GateOutcome(False, ERROR_PAYMENT_REQUIRED, reason="fee owed, no locker")
    if r.locker_units < fee:
        return GateOutcome(False, ERROR_PAYMENT_INSUFFICIENT,
                           reason="locker below required fee")
    return GateOutcome(True, STATUS_SUCCESS, fee, "fee paid from funded locker")


def evaluate_tell(recipients) -> dict:
    """Aggregate a Tell across recipients (§4.5).

    Returns {status, outcomes}. If any recipient delivered, status is 250; otherwise the
    highest-precedence failure among them wins (ERROR_WRONG_RAIDA if none applies).
    """
    outcomes = [evaluate_recipient(r) for r in recipients]
    if any(o.delivered for o in outcomes):
        return {"status": STATUS_SUCCESS, "outcomes": outcomes}
    failures = {o.status for o in outcomes if not o.delivered}
    for status in ZERO_DELIVERED_PRECEDENCE:
        if status in failures:
            return {"status": status, "outcomes": outcomes}
    return {"status": ERROR_WRONG_RAIDA, "outcomes": outcomes}
