#!/usr/bin/env python3
"""Unit tests for codec behavior the conformance vectors don't directly cover:
non-empty Styles round-trips, resource walking, and strict-parse rejections (§5).

Run directly:   python3 tests/test_codec.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, IMPL_ROOT)

import cbdf
from cbdf import constants as C
from cbdf import styles as stylesmod
from cbdf import resources as resmod
from cbdf._io import CBDFError


def _expect_error(fn, needle=""):
    try:
        fn()
    except CBDFError as e:
        assert needle.lower() in str(e).lower(), f"wrong error: {e!r} (wanted {needle!r})"
        return
    raise AssertionError(f"expected CBDFError containing {needle!r}, none raised")


# --- Styles: non-empty sub-tables round-trip ----------------------------------------
def test_styles_roundtrip_with_records():
    # Two text-style records (base tier, 8 bytes each) in sub-table #6 (index 5).
    text_style_idx = 5
    rec_a = bytes(range(8))
    rec_b = bytes([0xFF] * 8)
    sub = stylesmod.SubTable(text_style_idx, tier=C.TIER_BASE, records=[rec_a, rec_b])
    tables = [stylesmod.SubTable(i) for i in range(C.SUBTABLE_COUNT)]
    tables[text_style_idx] = sub
    styles = cbdf.StylesSection(layout_id=0x0122, sub_tables=tables)  # holy-grail

    payload = styles.encode()
    back = cbdf.StylesSection.decode(payload)
    assert back.layout_id == 0x0122
    got = back.sub_tables[text_style_idx]
    assert got.tier == C.TIER_BASE
    assert got.records == [rec_a, rec_b]
    # All other tables stay empty.
    assert sum(1 for st in back.sub_tables if not st.is_empty) == 1


def test_styles_extended_tier_record_size():
    # Background sub-table (#1, index 0) extended tier is 12 bytes.
    sub = stylesmod.SubTable(0, tier=C.TIER_EXTENDED, records=[bytes(12)])
    tables = [stylesmod.SubTable(i) for i in range(C.SUBTABLE_COUNT)]
    tables[0] = sub
    styles = cbdf.StylesSection(sub_tables=tables)
    back = cbdf.StylesSection.decode(styles.encode())
    assert back.sub_tables[0].tier == C.TIER_EXTENDED
    assert len(back.sub_tables[0].records[0]) == 12


def test_styles_reject_wrong_record_size():
    _expect_error(lambda: stylesmod.SubTable(0, tier=C.TIER_BASE, records=[bytes(5)]),
                  "6 bytes")


def test_styles_reject_reserved_tier():
    # A header byte with tier 3 must be rejected on decode.
    bad = b"\x00\x00" + bytes([C.GS, 0x07]) + bytes([C.GS] * 11)  # tier=3,count=1 in table 1
    _expect_error(lambda: cbdf.StylesSection.decode(bad), "reserved")


# --- Resources: walking and uniqueness ----------------------------------------------
def test_resources_multi_roundtrip():
    r1 = cbdf.Resource(0, C.RES_PNG, b"\x01\x02")
    r2 = cbdf.Resource(1, C.RES_JPEG, b"\x03\x04\x05")
    payload = resmod.encode([r1, r2])
    back = resmod.decode(payload)
    assert [(x.res_id, x.res_type, x.data) for x in back] == [
        (0, C.RES_PNG, b"\x01\x02"), (1, C.RES_JPEG, b"\x03\x04\x05")]


def test_resources_reject_duplicate_id():
    _expect_error(lambda: resmod.encode(
        [cbdf.Resource(0, C.RES_PNG, b""), cbdf.Resource(0, C.RES_JPEG, b"")]),
        "duplicate")


# --- Meta: retired key and meta-only forbidden keys ---------------------------------
def test_meta_reject_retired_key():
    _expect_error(lambda: cbdf.MetaSection().add(34, b"\x00"), "retired")


def test_meta_only_forbidden_key():
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.EOF_FLAG, 1)
            .add_u8(C.Meta.DEFAULT_STYLE_SET, 1))  # key 32 forbidden when meta-only
    _expect_error(meta.encode, "meta-only")


# --- Document strict parsing (§5) ---------------------------------------------------
def test_full_document_roundtrip():
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_QMAIL)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II)
            .add(C.Meta.QMAIL_ID, bytes(16))
            .add(C.Meta.FROM, cbdf.mailbox(1, 7))
            .add(C.Meta.TO, cbdf.mailbox(1, 8)))
    doc = cbdf.Document(
        meta,
        cbdf.StylesSection.minimal(0x0101),
        text_body="Hi there".encode(),
        resources=[cbdf.Resource(0, C.RES_PNG, b"\xDE\xAD")],
    )
    wire = doc.encode()
    parsed = cbdf.parse(wire)
    assert parsed["kind"] == "phase2"
    assert parsed["styles"].layout_id == 0x0101
    assert cbdf.extract_plaintext(parsed["text_payload"]) == "Hi there"
    assert parsed["resources"][0].data == b"\xDE\xAD"


def test_reject_nonzero_logic():
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    doc = cbdf.Document(meta, logic=b"\x01")
    _expect_error(doc.encode, "logic")


def test_reject_truncated_section():
    # A Phase II doc claiming a longer Styles section than present must fail, not slice.
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II)).encode()
    truncated = meta + bytes([C.FS]) + (100).to_bytes(4, "little") + b"\x00\x00"
    _expect_error(lambda: cbdf.parse(truncated), "truncated")


ALL_TESTS = [
    test_styles_roundtrip_with_records,
    test_styles_extended_tier_record_size,
    test_styles_reject_wrong_record_size,
    test_styles_reject_reserved_tier,
    test_resources_multi_roundtrip,
    test_resources_reject_duplicate_id,
    test_meta_reject_retired_key,
    test_meta_only_forbidden_key,
    test_full_document_roundtrip,
    test_reject_nonzero_logic,
    test_reject_truncated_section,
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
    print(f"\n{total - failures}/{total} unit checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
