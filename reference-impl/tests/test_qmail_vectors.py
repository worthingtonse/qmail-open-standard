#!/usr/bin/env python3
"""Conformance tests: the QMail reference codec against test-vectors/qmail/vectors/*.json.

QMail is the umbrella; its byte-exact surface is the 48-byte preamble (asserted
byte-identical to RKE's — the interop anchor). The file_type mapping, the DRD-gate
decision table, and the status flow are structural/decision vectors, checked against the
library's `filetype`, `gate`, and status constants.

Run directly:   python3 tests/test_qmail_vectors.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(IMPL_ROOT)
QVEC = os.path.join(REPO_ROOT, "test-vectors", "qmail", "vectors")
RVEC = os.path.join(REPO_ROOT, "test-vectors", "rke", "vectors")

sys.path.insert(0, IMPL_ROOT)

import qmail
from qmail import gate, filetype, constants as C

CH_SEED = bytes(range(12))
AN = bytes([0xA0 + (i & 0x0F) for i in range(16)])


def load(path):
    with open(path) as f:
        return json.load(f)


# --- 1. preamble (byte-exact + RKE cross-check) -------------------------------------
def test_preamble_and_rke_cross_check():
    v = load(os.path.join(QVEC, "01-preamble.json"))
    pre = qmail.Preamble(challenge=qmail.challenge(CH_SEED), an=AN, denomination=0, serial=42)
    wire = pre.encode()
    assert wire.hex() == v["bytes_hex"], "QMail preamble bytes must match its vector"
    assert len(wire) == 48
    # The interop anchor: byte-identical to the RKE preamble vector.
    rke_v = load(os.path.join(RVEC, "01-preamble.json"))
    assert wire.hex() == rke_v["bytes_hex"], "QMail preamble must equal the RKE preamble"
    assert qmail.challenge_is_valid(pre.challenge)


# --- 2. file_type -> suffix/role mapping + manifest order ---------------------------
def test_file_type_mapping():
    v = load(os.path.join(QVEC, "02-file-type-mapping.json"))
    for entry in v["mapping"]:
        ft = entry["file_type"]
        if isinstance(ft, int):
            assert filetype.suffix(ft) == entry["suffix"], f"suffix ft={ft}"
    # Attachment suffix rule: 10 -> .0.bin, 11 -> .1.bin.
    assert filetype.suffix(10) == ".0.bin"
    assert filetype.suffix(11) == ".1.bin"
    assert filetype.is_attachment(10) and not filetype.is_attachment(1)
    # Manifest order: private meta first, body second, attachment last.
    want = [e["file_type"] for e in v["manifest_order"]]
    assert filetype.manifest_order([10, 1, 0]) == want == [0, 1, 10]


# --- 3. Tell DRD-gate decision table ------------------------------------------------
def test_drd_gate_scenarios():
    v = load(os.path.join(QVEC, "03-tell-drd-gate.json"))
    # Evaluation order and zero-delivered precedence match the spec/vector.
    assert list(gate.EVALUATION_ORDER) == v["evaluation_order"]
    precedence_codes = [int(s.split()[0]) for s in v["zero_delivered_precedence"]]
    assert list(gate.ZERO_DELIVERED_PRECEDENCE) == precedence_codes

    # list_status uses DRD's LIST_WHITELIST (0x00) / LIST_BLACKLIST (0x01) values.
    fee = 5 * 100_000_000  # 5 CC

    # Whitelisted -> delivered free.
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, list_status=0x00))
    assert o.delivered and o.status == C.STATUS_SUCCESS and o.fee_charged == 0

    # Blacklisted -> skipped (236 when zero deliver).
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, list_status=0x01))
    assert not o.delivered and o.status == C.ERROR_SENDER_BLACKLISTED

    # Class-rejected: recipient CR=1, sender denom 0 (< 1) -> 237.
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, class_rejection=1))
    assert not o.delivered and o.status == C.ERROR_SENDER_CLASS_REJECTED

    # Fee owed, no locker -> 169.
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, inbox_fee_units=fee))
    assert o.status == C.ERROR_PAYMENT_REQUIRED

    # Fee owed, locker below fee -> 168.
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, inbox_fee_units=fee,
                                               locker_units=fee - 1))
    assert o.status == C.ERROR_PAYMENT_INSUFFICIENT

    # Fee owed, funded locker -> delivered, fee consumed.
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, inbox_fee_units=fee,
                                               locker_units=fee))
    assert o.delivered and o.fee_charged == fee

    # No DRD record -> default Tell fee (10 CC); funded -> deliver, unfunded -> 169.
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, has_drd_record=False,
                                               locker_units=C.DEFAULT_TELL_FEE_UNITS))
    assert o.delivered and o.fee_charged == C.DEFAULT_TELL_FEE_UNITS
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, has_drd_record=False))
    assert o.status == C.ERROR_PAYMENT_REQUIRED


def test_drd_gate_multi_recipient_precedence():
    # One delivers, others fail -> overall 250 (allowed recipients still deliver).
    res = gate.evaluate_tell([
        gate.Recipient(sender_denomination=0, list_status=0x01),          # blacklisted
        gate.Recipient(sender_denomination=0, list_status=0x00),          # whitelisted -> deliver
    ])
    assert res["status"] == C.STATUS_SUCCESS

    # Zero deliver -> most specific failure wins: blacklist (236) beats class-reject (237).
    res = gate.evaluate_tell([
        gate.Recipient(sender_denomination=0, class_rejection=1),         # 237
        gate.Recipient(sender_denomination=0, list_status=0x01),          # 236
    ])
    assert res["status"] == C.ERROR_SENDER_BLACKLISTED

    # Zero deliver, only a fee failure -> 169.
    res = gate.evaluate_tell([
        gate.Recipient(sender_denomination=0, inbox_fee_units=100),
    ])
    assert res["status"] == C.ERROR_PAYMENT_REQUIRED


# --- 4. status flow constants -------------------------------------------------------
def test_status_flow_constants():
    v = load(os.path.join(QVEC, "04-status-flow.json"))
    # Every command named in the flow maps to a Group 6 command constant.
    cmd_codes = {C.CMD_UPLOAD, C.CMD_UPLOAD_LARGE_PAGE, C.CMD_TELL, C.CMD_PING,
                 C.CMD_PEEK, C.CMD_DOWNLOAD}
    assert cmd_codes == {70, 75, 71, 72, 73, 74}
    # Every error code the flow references exists in the QMail status subset.
    known = {C.ERROR_INVALID_ENCRYPTION, C.ERROR_INVALID_AN, C.ERROR_FILE_NOT_EXIST}
    for code_str in v["common_errors"]:
        assert int(code_str) in known, code_str


ALL_TESTS = [
    test_preamble_and_rke_cross_check,
    test_file_type_mapping,
    test_drd_gate_scenarios,
    test_drd_gate_multi_recipient_precedence,
    test_status_flow_constants,
]


def main():
    failures = 0
    for t in ALL_TESTS:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {t.__name__}\n        {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    total = len(ALL_TESTS)
    print(f"\n{total - failures}/{total} QMail conformance checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
