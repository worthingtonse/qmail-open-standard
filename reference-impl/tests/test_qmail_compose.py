#!/usr/bin/env python3
"""End-to-end composition: QMail composing CBDF + RKE + DRD across the byte-order boundary.

QMail is the umbrella; this exercises all four packages together — a little-endian CBDF
message payload wrapped by big-endian QMail/RKE preamble bytes, with the DRD-backed gate
deciding delivery — to demonstrate the standards compose and that LE and BE stay on their
own sides of the boundary.

Run directly:   python3 tests/test_qmail_compose.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, IMPL_ROOT)

import cbdf
import drd
import qmail
from cbdf import constants as CC
from qmail import gate, filetype


def test_message_payload_is_cbdf_little_endian():
    # file_type=0 is a private CBDF Meta object; file_type=1 is the CBDF body — both are
    # genuine CBDF documents (little-endian), carried under QMail (big-endian) framing.
    meta = (cbdf.MetaSection()
            .add_u8(CC.Meta.FILE_TYPE, CC.FILE_TYPE_QMAIL)
            .add_u8(CC.Meta.VERSION, CC.VERSION_PHASE_II)
            .add_u8(CC.Meta.EOF_FLAG, 1)
            .add_text(CC.Meta.SUBJECT, "Lunch?"))
    meta_obj = cbdf.Document(meta).encode()                 # file_type=0 (.meta)
    body_doc = cbdf.Document(
        (cbdf.MetaSection()
         .add_u8(CC.Meta.FILE_TYPE, CC.FILE_TYPE_QMAIL)
         .add_u8(CC.Meta.VERSION, CC.VERSION_PHASE_II)),
        text_body="See you at noon.".encode())
    body_obj = body_doc.encode()                            # file_type=1 (.qmail)

    # The QMail object model maps these to suffixes/roles and orders the manifest.
    assert filetype.suffix(qmail.constants.FT_META) == ".meta"
    assert filetype.suffix(qmail.constants.FT_BODY) == ".qmail"
    assert filetype.manifest_order([qmail.constants.FT_BODY, qmail.constants.FT_META,
                                    10]) == [0, 1, 10]

    # The CBDF payload round-trips independently of the QMail framing (LE stays LE).
    assert cbdf.parse(meta_obj)["kind"] == "meta_only"
    parsed_body = cbdf.parse(body_obj)
    assert cbdf.extract_plaintext(parsed_body["text_payload"]) == "See you at noon."


def test_preamble_is_big_endian_and_shared():
    # The QMail request preamble (big-endian) shares the RKE structure and the 7-byte coin
    # identity — but the QMail-layer serial is BIG-endian, the CBDF mailbox serial is
    # LITTLE-endian: the same coin, opposite byte order across the boundary.
    pre = qmail.Preamble(challenge=qmail.challenge(bytes(range(12))),
                         an=bytes(16), denomination=0, serial=42)
    wire = pre.encode()
    assert wire[27:31] == (42).to_bytes(4, "big")           # QMail/RKE serial: big-endian
    cbdf_mailbox = cbdf.mailbox(denom=0, serial=42)
    assert cbdf_mailbox[3:7] == (42).to_bytes(4, "little")  # CBDF mailbox serial: little-endian
    # Same coin (type 0006, denom 0, serial 42), encoded for each wire world.
    assert pre.coin_type == 0x0006
    assert cbdf.parse_mailbox(cbdf_mailbox)["serial"] == 42


def test_gate_uses_drd_class_rejection():
    # The QMail gate's class check IS DRD's signed comparison — a −1 sender is below a
    # class floor of 0 only when the floor is set; below floor 1 it is rejected.
    assert drd.class_rejects(1, 0) is True         # sender denom 0 < floor 1
    assert drd.class_rejects(0, -8) is False       # floor 0 = accept all
    o = gate.evaluate_recipient(gate.Recipient(sender_denomination=0, class_rejection=1))
    assert not o.delivered and o.status == qmail.constants.ERROR_SENDER_CLASS_REJECTED


ALL_TESTS = [
    test_message_payload_is_cbdf_little_endian,
    test_preamble_is_big_endian_and_shared,
    test_gate_uses_drd_class_rejection,
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
    print(f"\n{total - failures}/{total} composition checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
