#!/usr/bin/env python3
"""Field-level style record layouts (§4.4.3).

Two kinds of checks per record: (1) byte-exact against a hand-computed layout so the
field positions and bit packing are pinned, and (2) round-trip through pack/unpack. Also
exercises SubTable.of()/typed() and the tiered records' 8/12/16 and 6/12/20 forms.

Run directly:   python3 tests/test_records.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, IMPL_ROOT)

import cbdf
from cbdf import constants as C
from cbdf import records as R
from cbdf._io import CBDFError


def _eq(got, want, msg=""):
    assert got == want, f"{msg}\n  want {want.hex() if isinstance(want, bytes) else want}" \
                        f"\n  got  {got.hex() if isinstance(got, bytes) else got}"


def _roundtrip(rec):
    raw = rec.pack()
    back = type(rec).unpack(raw)
    assert back == rec, f"round-trip mismatch\n  {rec}\n  {back}"
    return raw


# --- Text Style: byte layout + tiers ------------------------------------------------
def test_text_style_base_bytes():
    # FontID 0x0203, size 14, bold+center (bits0 and 0x40|0x80? center=1 -> bits6-7=01),
    # fg Pure Red 0xF800, bg White 0xFFFF.
    ts = R.TextStyle(font_id=0x0203, font_size=14, bold=True, alignment=1,
                     fg_color=0xF800, bg_color=0xFFFF)
    raw = _roundtrip(ts)
    # 03 02 | 0E | flags(bold=1, align=1 -> 0x40) = 0x41 | 00 F8 | FF FF
    _eq(raw, bytes([0x03, 0x02, 0x0E, 0x41, 0x00, 0xF8, 0xFF, 0xFF]), "text base")
    assert len(raw) == 8


def test_text_style_extended_and_rare():
    ts = R.TextStyle(font_id=1, tier=C.TIER_EXTENDED, shadow=(-2, 3, 5),
                     letter_spacing=-4, line_height=15)
    raw = _roundtrip(ts)
    assert len(raw) == 12
    # shadow: X=-2 -> 0x3E (6-bit), Y=3, blur=5 => 0x3E | 3<<6 | 5<<12 = 0x50FE
    assert raw[8:10] == bytes([0xFE, 0x50])
    assert raw[10] == (-4 & 0xFF)  # letter spacing signed
    assert raw[11] == 15

    rare = R.TextStyle(tier=C.TIER_RARE, effect_id=10, effect_intensity=7,
                       transform=1, direction=2, word_spacing=3, effect_color=0x07E0)
    raw = _roundtrip(rare)
    assert len(raw) == 16
    assert raw[12] == (10 | (7 << 4))          # effect id low nibble, intensity high
    assert raw[13] == (1 | (2 << 2) | (3 << 4))  # transform|direction|word_spacing
    assert raw[14:16] == bytes([0xE0, 0x07])


# --- Background tiers ----------------------------------------------------------------
def test_background_tiers():
    base = R.Background(bg_color=0x001F, image_id=0, opacity=200, cover=True)
    raw = _roundtrip(base)
    _eq(raw, bytes([0x1F, 0x00, 0x00, 0x00, 200, 0x08]), "bg base")

    ext = R.Background(tier=C.TIER_EXTENDED, grad_color2=0xF800, grad_type=1,
                       grad_angle=128, color2_stop=255)
    raw = _roundtrip(ext)
    assert len(raw) == 12 and raw[11] == 0  # reserved zeroed

    rare = R.Background(tier=C.TIER_RARE, grad_color3=0x07E0, grad_color4=0xFFFF,
                        color3_stop=100, color4_stop=200)
    raw = _roundtrip(rare)
    assert len(raw) == 20 and raw[18:20] == b"\x00\x00"


# --- Border: nibble thickness + 6-bit corner radii ----------------------------------
def test_border_packing():
    b = R.Border(border_color=0x0000, thickness_top=1, thickness_right=2,
                 thickness_bottom=3, thickness_left=4, outside_color=0xFFFF,
                 radius_tl=1, radius_tr=2, radius_br=3, radius_bl=4)
    raw = _roundtrip(b)
    assert len(raw) == 9
    assert raw[2] == 0x12 and raw[3] == 0x34          # top|right, bottom|left
    # radii LSB-first: 1 | 2<<6 | 3<<12 | 4<<18 = 0x103081 -> 81 30 10
    assert raw[6:9] == bytes([0x81, 0x30, 0x10])


# --- Spacing nibble semantics --------------------------------------------------------
def test_spacing_packing():
    s = R.Spacing(margin_top=0, margin_right=15, margin_bottom=5, margin_left=1,
                  padding_top=2, padding_right=3, padding_bottom=4, padding_left=14)
    raw = _roundtrip(s)
    _eq(raw, bytes([0x0F, 0x51, 0x23, 0x4E]), "spacing")


# --- Shadow shares Text's packing ----------------------------------------------------
def test_shadow_signed():
    sh = R.Shadow(shadow_color=0x1234, x=-32, y=31, blur=15)
    raw = _roundtrip(sh)
    assert raw[0:2] == bytes([0x34, 0x12])
    # X=-32 -> 0x20, Y=31 -> 0x1F, blur=15 -> 0xF: 0x20 | 0x1F<<6 | 0xF<<12 = 0xF7E0
    assert raw[2:4] == bytes([0xE0, 0xF7])


# --- Composite overflow + layer_id ---------------------------------------------------
def test_composite():
    c = R.Composite(background_index=0, border_index=1, spacing_index=2,
                    shadow_index=255, overflow=2, layer_id=8)
    raw = _roundtrip(c)
    assert raw[0:4] == bytes([0, 1, 2, 255])
    assert raw[4] == (2 | (8 << 2))
    # layer_id out of range rejected
    try:
        R.Composite(layer_id=64).pack()
        raise AssertionError("expected layer_id range error")
    except CBDFError:
        pass


# --- The remaining single-tier records: round-trip + length -------------------------
def test_remaining_records_roundtrip():
    for rec, size in [
        (R.FontEffect(effect_id=3, intensity=200, param_a=1, param_b=2), 4),
        (R.NavBar(item_style_index=0, active_index=1, collapse_breakpoint=96,
                  orientation=1, item_mode=2, alignment=3), 12),
        (R.Table(header_style_index=0, body_style_index=1, first_row_header=True,
                 row_stripes=True, column_rules=True, row_rules=True), 6),
        (R.ImageDef(source_type=0, source_id=5, width=640, height=480, fit=1,
                    border_index=2), 8),
        (R.FrameDef(source_type=0, source_id=1, width=320, height=240,
                    allow_scrolling=True, allow_nested_frames=True, border_index=255), 8),
    ]:
        raw = _roundtrip(rec)
        assert len(raw) == size, f"{type(rec).__name__} size {len(raw)} != {size}"


def test_navbar_reserved_zeroed():
    raw = R.NavBar().pack()
    assert raw[8:12] == b"\x00\x00\x00\x00"


def test_decoder_ignores_nonzero_reserved():
    # §4.4.3: decoders MUST accept non-zero reserved bytes and ignore them.
    raw = bytearray(R.NavBar(item_style_index=7).pack())
    raw[8:12] = b"\xFF\xFF\xFF\xFF"
    nb = R.NavBar.unpack(bytes(raw))
    assert nb.item_style_index == 7
    assert nb == R.NavBar(item_style_index=7)  # reserved dropped -> equal to canonical


# --- SubTable.of()/typed() integration through the full Styles section --------------
def test_subtable_of_and_typed_via_styles():
    styles_in = cbdf.StylesSection(
        layout_id=0x0122,
        sub_tables=[
            cbdf.SubTable.of([R.TextStyle(font_size=12, bold=True, fg_color=0xF800),
                              R.TextStyle(font_size=10, italic=True)])
            if i == R.TextStyle.TABLE_INDEX
            else cbdf.SubTable.of([R.Composite(layer_id=1)])
            if i == R.Composite.TABLE_INDEX
            else cbdf.SubTable(i)
            for i in range(C.SUBTABLE_COUNT)
        ],
    )
    wire = styles_in.encode_section()
    back = cbdf.StylesSection.decode(wire[4:])
    texts = back.sub_tables[R.TextStyle.TABLE_INDEX].typed()
    assert len(texts) == 2 and texts[0].bold and texts[0].fg_color == 0xF800
    assert texts[1].italic and texts[1].font_size == 10
    comp = back.sub_tables[R.Composite.TABLE_INDEX].typed()[0]
    assert comp.layer_id == 1

    # A whole document carrying real style records still parses and round-trips.
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_QMAIL)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    doc = cbdf.Document(meta, styles_in, text_body=b"Styled")
    parsed = cbdf.parse(doc.encode())
    assert parsed["styles"].sub_tables[R.TextStyle.TABLE_INDEX].typed()[0].bold


def test_subtable_of_rejects_mixed():
    try:
        cbdf.SubTable.of([R.TextStyle(), R.Composite()])
        raise AssertionError("expected mixed-type rejection")
    except CBDFError:
        pass


ALL_TESTS = [
    test_text_style_base_bytes,
    test_text_style_extended_and_rare,
    test_background_tiers,
    test_border_packing,
    test_spacing_packing,
    test_shadow_signed,
    test_composite,
    test_remaining_records_roundtrip,
    test_navbar_reserved_zeroed,
    test_decoder_ignores_nonzero_reserved,
    test_subtable_of_and_typed_via_styles,
    test_subtable_of_rejects_mixed,
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
    print(f"\n{total - failures}/{total} record checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
