#!/usr/bin/env python3
"""Conformance tests: the CBDF reference codec against test-vectors/cbdf/vectors/*.json.

Each check either (a) re-encodes a document through the library and asserts it is
byte-equal to the vector's `bytes_hex`, or (b) drives a decoder (extraction, color) and
asserts the vector's expected result. Passing all of these is the interop bar (§8).

Run directly:   python3 tests/test_vectors.py
Or under pytest: pytest reference-impl/tests
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(IMPL_ROOT)
VECTORS = os.path.join(REPO_ROOT, "test-vectors", "cbdf", "vectors")

sys.path.insert(0, IMPL_ROOT)

import cbdf
from cbdf import constants as C

TIMESTAMP = 1785312000  # matches the vectors' fixed reproducible timestamp


def load(name):
    with open(os.path.join(VECTORS, name)) as f:
        return json.load(f)


def _hex(b):
    return b.hex()


def _assert_bytes(name, produced, vector):
    want = vector["bytes_hex"]
    got = _hex(produced)
    assert got == want, (
        f"{name}: byte mismatch\n  want {want}\n  got  {got}")


# --- 01 meta-only SMS-class document (§4.1, §4.3) -----------------------------------
def test_meta_only_sms():
    v = load("01-meta-only-sms.json")
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_SMS)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II)
            .add_u8(C.Meta.EOF_FLAG, 1)
            .add_text(C.Meta.SUBJECT, "On my way")
            .add(C.Meta.FROM, cbdf.mailbox(1, 42))
            .add(C.Meta.TO, cbdf.mailbox(1, 100))
            .add_u32(C.Meta.TIMESTAMP, TIMESTAMP))
    doc = cbdf.Document(meta)
    _assert_bytes("meta-only", doc.encode(), v)

    # Round-trip: parse recognizes the meta-only shape and preserves the message.
    parsed = cbdf.parse(doc.encode())
    assert parsed["kind"] == "meta_only"
    assert parsed["meta"].get(C.Meta.SUBJECT).decode() == "On my way"
    assert cbdf.parse_mailbox(parsed["meta"].get(C.Meta.TO))["serial"] == 100


# --- 02 Phase I body object (§4.2, §5) ----------------------------------------------
def test_phase1_body():
    v = load("02-phase1-body-object.json")
    produced = cbdf.encode_phase1_body("Hello, world.")
    _assert_bytes("phase1-body", produced, v)
    parsed = cbdf.parse(produced)
    assert parsed["kind"] == "phase1"
    assert parsed["body"].decode() == "Hello, world."


# --- 03 minimal Phase II document (§4.1, §4.4, §4.5) --------------------------------
def test_phase2_minimal():
    v = load("03-phase2-minimal-document.json")
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    doc = cbdf.Document(meta, cbdf.StylesSection.minimal(0x0000), text_body=b"")
    wire = doc.encode()
    _assert_bytes("phase2-minimal", wire, v)

    parsed = cbdf.parse(wire)
    assert parsed["kind"] == "phase2"
    assert parsed["styles"].layout_id == 0x0000
    assert all(st.is_empty for st in parsed["styles"].sub_tables)
    assert cbdf.extract_plaintext(parsed["text_payload"]) == ""


# --- 04 R5G6B5 colors + transparency (§4.6) -----------------------------------------
def test_colors():
    v = load("04-colors-r5g6b5.json")
    for case in v["colors"]:
        r, g, b = case["rgb8_in"]
        code = int(case["r5g6b5"], 16)
        assert cbdf.rgb_to_565(r, g, b) == code, case["name"]
        assert _hex(cbdf.rgb_to_565(r, g, b).to_bytes(2, "little")) == \
            case["le_bytes"].replace(" ", "").lower(), case["name"]
        assert list(cbdf.c565_to_rgb(code)) == case["rgb8_decoded"], case["name"]
    for t in v["transparency_codes"]:
        code = int(t["code"], 16)
        assert cbdf.is_transparency(code)
        assert cbdf.TRANSPARENCY[code] == t["alpha"]
    # An RGB result colliding with the reserved band diverts to the safe code.
    safe = int(v["reserved_safe_code"], 16)
    for code in cbdf.TRANSPARENCY:
        assert cbdf.divert_reserved(code) == safe


# --- 05 resource record framing (§4.8) ----------------------------------------------
def test_resource_record():
    v = load("05-resource-record.json")
    res = cbdf.Resource(res_id=0, res_type=C.RES_PNG, data=bytes([0xDE, 0xAD, 0xBE, 0xEF]))
    from cbdf import resources as resmod
    produced = resmod.encode_section([res])
    _assert_bytes("resource-record", produced, v)

    # Round-trip the payload (drop the 4-byte length prefix).
    payload = produced[4:]
    back = resmod.decode(payload)
    assert len(back) == 1 and back[0].res_id == 0 and back[0].res_type == C.RES_PNG
    assert back[0].data == bytes([0xDE, 0xAD, 0xBE, 0xEF])


# --- 06 plain-text extraction (§4.5.2) ----------------------------------------------
def test_plaintext_extraction():
    v = load("06-plaintext-extraction.json")
    body = bytes.fromhex(v["text_body_hex"])
    assert cbdf.extract_plaintext(body, degrade=False) == v["expected_plain_strict"]
    assert cbdf.extract_plaintext(body, degrade=True) == v["expected_plain_degraded"]


ALL_TESTS = [
    test_meta_only_sms,
    test_phase1_body,
    test_phase2_minimal,
    test_colors,
    test_resource_record,
    test_plaintext_extraction,
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
        except Exception as e:  # noqa: BLE001 - surface any codec error as a failure
            failures += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    total = len(ALL_TESTS)
    print(f"\n{total - failures}/{total} conformance checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
