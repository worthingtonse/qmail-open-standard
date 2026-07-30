#!/usr/bin/env python3
"""Compression (§4.9) and extension sections (§4.10).

Checks the compressed document framing (FS [CompLen][DecompLen][zlib] with the inter-
section FS living inside the blob), round-trips a compressed document, verifies the
decompressed layout matches the uncompressed one, exercises the zip-bomb guard, and
round-trips extension sections after Logic.

Run directly:   python3 tests/test_compression.py
"""
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, IMPL_ROOT)

import cbdf
from cbdf import constants as C
from cbdf import compression as comp
from cbdf._io import CBDFError, read_u32


def _big_doc(compressed: bool):
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_QMAIL)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    if compressed:
        meta.add_u8(C.Meta.COMPRESSION, C.COMPRESS_ZLIB)
    # A highly compressible body so the codec clearly does something.
    body = ("The quick brown fox. " * 40).encode()
    styles = cbdf.StylesSection(
        layout_id=0x0122,
        sub_tables=[cbdf.SubTable.of([cbdf.TextStyle(bold=True, fg_color=0xF800)])
                    if i == cbdf.TextStyle.TABLE_INDEX else cbdf.SubTable(i)
                    for i in range(C.SUBTABLE_COUNT)],
    )
    return cbdf.Document(meta, styles, text_body=body,
                         resources=[cbdf.Resource(0, C.RES_PNG, b"\xDE\xAD\xBE\xEF")])


def test_compressed_roundtrip_matches_uncompressed_content():
    plain = _big_doc(compressed=False).encode()
    packed = _big_doc(compressed=True).encode()
    assert len(packed) < len(plain), "zlib should shrink this body"

    p = cbdf.parse(packed)
    assert p["kind"] == "phase2" and p["compression"] == C.COMPRESS_ZLIB
    assert cbdf.extract_plaintext(p["text_payload"]) == "The quick brown fox. " * 40
    assert p["styles"].sub_tables[cbdf.TextStyle.TABLE_INDEX].typed()[0].bold
    assert p["resources"][0].data == b"\xDE\xAD\xBE\xEF"

    # Both wire shapes decode to the same logical content.
    u = cbdf.parse(plain)
    assert cbdf.extract_plaintext(u["text_payload"]) == cbdf.extract_plaintext(p["text_payload"])
    assert u["styles"].encode() == p["styles"].encode()


def test_compressed_framing_bytes():
    # Locate the compressed section: right after Meta, FS then [CompLen][DecompLen][data].
    doc = _big_doc(compressed=True)
    wire = doc.encode()
    meta_len = len(doc.meta.encode())
    assert wire[meta_len] == C.FS
    off = meta_len + 1
    comp_len = read_u32(wire, off)
    decomp_len = read_u32(wire, off + 4)
    blob = wire[off + 8: off + 8 + comp_len]
    inner = zlib.decompress(blob)
    assert len(inner) == decomp_len
    # Inner blob: [StylesLen][Styles] FS [TextLen][Text].
    styles_len = read_u32(inner, 0)
    fs_pos = 4 + styles_len
    assert inner[fs_pos] == C.FS, "FS between Styles and Text must be inside the blob"


def test_zip_bomb_guard():
    # A blob whose real output is short but declares a huge DecompLen must be rejected.
    real = zlib.compress(b"x" * 10)
    _expect(lambda: comp.decompress(real, C.COMPRESS_ZLIB, 10_000_000), "decompressed size")
    # Declaring less than the true output (bomb pattern) is also rejected.
    _expect(lambda: comp.decompress(real, C.COMPRESS_ZLIB, 3), "exceeds declared")


def test_unsupported_codec_rejected():
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II)
            .add_u8(C.Meta.COMPRESSION, C.COMPRESS_ZSTD))  # 3 — optional, not built
    _expect(cbdf.Document(meta).encode, "not supported")


def test_text_offset_forbidden_when_compressed():
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II)
            .add_u8(C.Meta.COMPRESSION, C.COMPRESS_ZLIB)
            .add_u32(C.Meta.TEXT_OFFSET, 100))
    _expect(cbdf.Document(meta, text_body=b"hi").encode, "key 40")


# --- extension sections (§4.10) ------------------------------------------------------
def test_extension_sections_roundtrip():
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    exts = [(1, b"\x00\x01\x02"), (7, b"listener-data")]
    doc = cbdf.Document(meta, text_body=b"body", extensions=exts)
    p = cbdf.parse(doc.encode())
    assert p["extensions"] == exts, p["extensions"]


def test_unknown_extension_skipped_by_length():
    # A parser must skip an unknown extension id purely by its length and keep going.
    meta = (cbdf.MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    doc = cbdf.Document(meta, text_body=b"x", extensions=[(200, b"opaque future bytes")])
    p = cbdf.parse(doc.encode())
    assert p["extensions"][0][0] == 200
    assert p["extensions"][0][1] == b"opaque future bytes"


def _expect(fn, needle):
    try:
        fn()
    except CBDFError as e:
        assert needle.lower() in str(e).lower(), f"wrong error {e!r} (wanted {needle!r})"
        return
    raise AssertionError(f"expected CBDFError containing {needle!r}")


ALL_TESTS = [
    test_compressed_roundtrip_matches_uncompressed_content,
    test_compressed_framing_bytes,
    test_zip_bomb_guard,
    test_unsupported_codec_rejected,
    test_text_offset_forbidden_when_compressed,
    test_extension_sections_roundtrip,
    test_unknown_extension_skipped_by_length,
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
    print(f"\n{total - failures}/{total} compression/extension checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
