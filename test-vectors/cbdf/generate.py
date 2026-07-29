#!/usr/bin/env python3
"""
CBDF/1.0 (Phase II) conformance test-vector generator.

Builds the vectors described in specs/cbdf-1.0.md §8 and writes them, byte-accurate,
to test-vectors/cbdf/vectors/*.json. The builders here ARE a small reference encoder,
so running this script (it self-checks with asserts) is itself a conformance smoke test.

Usage:  python3 generate.py          # regenerate vectors/*.json
Vectors are little-endian throughout, per CBDF/1.0 §2.
"""
import json, os, struct

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")

# ---- control codes (CBDF/1.0 §4.5.1) -------------------------------------------------
SOH, STX, ETX = 0x01, 0x02, 0x03
TAB, LF, PARA_BREAK, HORIZ_RULE = 0x09, 0x0A, 0x0B, 0x0D
LINK_START, LINK_END, DATA_ESCAPE = 0x0E, 0x0F, 0x10
STYLE_TEXT, STYLE_CONTAINER, STYLE_TABLE, STYLE_END = 0x11, 0x12, 0x13, 0x14
ELEMENT_ID, IMAGE, BLOCK_END, ITEM_BLOCK, AI_PROMPT = 0x15, 0x16, 0x17, 0x19, 0x1A
FS, GS, RS, US = 0x1C, 0x1D, 0x1E, 0x1F

# A fixed, arbitrary timestamp so vectors are reproducible: 2026-07-13 00:00:00 kind of
# value is not important — only that the bytes are deterministic. Unix seconds.
TIMESTAMP = 1785312000  # 0x6A69B300

def u16(n): return struct.pack("<H", n)
def u32(n): return struct.pack("<I", n)
def hx(b): return " ".join(f"{x:02X}" for x in b)

def mailbox(denom, serial, group=0x0006):
    """7-byte CBDF mailbox: [CoinGroup:2 BE-looking 00 06][Denom:1][Serial:4 LE] (§4.3.5)."""
    # CloudCoin coin-group is the literal bytes 00 06 (§4.3.5).
    return bytes([group >> 8, group & 0xFF, denom]) + u32(serial)

def meta(pairs):
    """pairs = list of (key:int, value:bytes). Returns Meta section bytes (§4.3)."""
    out = u16(len(pairs))
    for k, v in pairs:
        assert 0 <= k <= 255 and len(v) <= 255, (k, len(v))
        out += bytes([k, len(v)]) + v
    return out

def section(payload):
    """A length-prefixed section body as it appears after its FS: [Len:4 LE][payload]."""
    return u32(len(payload)) + payload

def write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote vectors/{name} ({obj.get('length_bytes', '-')} bytes)")

# ======================================================================================
# 1. Meta-only SMS-class document (§4.1 meta-only, §4.3)
# ======================================================================================
def v_meta_only_sms():
    text = "On my way".encode("utf-8")
    pairs = [
        (0,  bytes([0x02])),            # Meta File Type = 2 (sms)
        (30, bytes([0x01])),            # Version = 1 (Phase II)
        (33, bytes([0x01])),            # EOF Flag = 1 (meta-only; no FS markers follow)
        (2,  text),                     # Subject / message text (no Text section exists)
        (19, mailbox(1, 42)),           # From mailbox
        (13, mailbox(1, 100)),          # To mailbox
        (25, u32(TIMESTAMP)),           # Timestamp (Unix seconds, 4 LE)
    ]
    b = meta(pairs)
    # meta-only forbids keys 31/32/37/40/42/43 (§4.3.2) — none present. Good.
    assert 14 <= len(b) <= 60, len(b)
    ann = [
        {"hex": "07 00", "field": "Meta pair count = 7 (LE)"},
        {"hex": "00 01 02", "field": "key 0 Meta File Type, len 1, = 2 (sms)"},
        {"hex": "1E 01 01", "field": "key 30 Version, len 1, = 1 (Phase II)"},
        {"hex": "21 01 01", "field": "key 33 EOF Flag, len 1, = 1 (meta-only)"},
        {"hex": f"02 {len(text):02X} {hx(text)}", "field": 'key 2 Subject, len 9, = "On my way"'},
        {"hex": "13 07 " + hx(mailbox(1, 42)), "field": "key 19 From mailbox (group 00 06, denom 1, serial 42 LE)"},
        {"hex": "0D 07 " + hx(mailbox(1, 100)), "field": "key 13 To mailbox (serial 100 LE)"},
        {"hex": "19 04 " + hx(u32(TIMESTAMP)), "field": f"key 25 Timestamp, len 4, = {TIMESTAMP} (0x{TIMESTAMP:08X} LE)"},
    ]
    write("01-meta-only-sms.json", {
        "vector": "meta-only-sms",
        "spec_ref": "CBDF/1.0 §4.1 (meta-only), §4.3",
        "description": "Ultra-compact SMS-class document: Meta section only (key 33=1), "
                       "no FS markers or other sections follow. The visible message rides "
                       "in key 2 (Subject) because there is no Text section.",
        "encoding": "little-endian",
        "length_bytes": len(b),
        "bytes_hex": b.hex(),
        "annotated": ann,
    })

# ======================================================================================
# 2. Phase I body object (§3, §4.2, §5) — the Tell file_type=1 body form
# ======================================================================================
def v_phase1_body():
    text = "Hello, world.".encode("utf-8")
    # Phase I body object begins FS FS STX, then plain text to EOF (ETX optional). (§5)
    b = bytes([FS, FS, STX]) + text
    ann = [
        {"hex": "1C 1C", "field": "FS FS — empty Styles slot (Phase I has no length prefixes)"},
        {"hex": "02", "field": "STX — start of text body"},
        {"hex": hx(text), "field": '"Hello, world." (UTF-8; runs to EOF, ETX not required)'},
    ]
    write("02-phase1-body-object.json", {
        "vector": "phase1-body-object",
        "spec_ref": "CBDF/1.0 §3, §4.2 (version 0), §5 (QMail file_type=1 body)",
        "description": "Backward-compatible Phase I body object. Detected by the absence "
                       "of Meta key 30. A tolerant decoder must accept this exact shape.",
        "encoding": "little-endian",
        "length_bytes": len(b),
        "bytes_hex": b.hex(),
        "annotated": ann,
    })

# ======================================================================================
# 3. Minimal Phase II uncompressed document (§4.1, §4.4 minimum styles, §4.5)
# ======================================================================================
def v_phase2_minimal():
    m = meta([(0, bytes([0x00])),   # Meta File Type = 0 (generic)
              (30, bytes([0x01]))])  # Version = 1 (Phase II)
    # Minimum Styles section (§4.4): LayoutID 0x0000 then GS × 12 empty sub-tables = 14 bytes.
    styles = u16(0x0000) + bytes([GS] * 12)
    assert len(styles) == 14, len(styles)
    text = bytes([STX, ETX])                       # empty body, still framed by STX/ETX
    resources = b""                                # empty
    logic = b""                                    # must be empty in Phase II
    b = (m
         + bytes([FS]) + section(styles)
         + bytes([FS]) + section(text)
         + bytes([FS]) + section(resources)
         + bytes([FS]) + section(logic))
    ann = [
        {"hex": "02 00", "field": "Meta pair count = 2"},
        {"hex": "00 01 00", "field": "key 0 Meta File Type = 0 (generic)"},
        {"hex": "1E 01 01", "field": "key 30 Version = 1 (Phase II)"},
        {"hex": "1C", "field": "FS — section separator"},
        {"hex": "0E 00 00 00", "field": "Styles length = 14 (LE)"},
        {"hex": "00 00", "field": "LayoutID = 0x0000 (compatibility page, single main flow)"},
        {"hex": "1D 1D 1D 1D 1D 1D 1D 1D 1D 1D 1D 1D", "field": "GS × 12 — twelve empty style sub-tables"},
        {"hex": "1C", "field": "FS"},
        {"hex": "02 00 00 00", "field": "Text length = 2 (LE)"},
        {"hex": "02 03", "field": "STX ETX — empty body"},
        {"hex": "1C", "field": "FS"},
        {"hex": "00 00 00 00", "field": "Resources length = 0 (empty tail, canonical)"},
        {"hex": "1C", "field": "FS"},
        {"hex": "00 00 00 00", "field": "Logic length = 0 (MUST be 0 in Phase II)"},
    ]
    write("03-phase2-minimal-document.json", {
        "vector": "phase2-minimal-document",
        "spec_ref": "CBDF/1.0 §4.1, §4.3.2, §4.4 (§9 minimum styles), §4.5",
        "description": "Smallest well-formed Phase II document: generic Meta with version=1, "
                       "the 14-byte minimum Styles section, an empty STX/ETX Text body, and "
                       "the canonical empty Resources and Logic tails (FS + 0x00000000).",
        "encoding": "little-endian",
        "length_bytes": len(b),
        "bytes_hex": b.hex(),
        "annotated": ann,
    })

# ======================================================================================
# 4. R5G6B5 color system + transparency codes (§4.6)
# ======================================================================================
def rgb_to_565(r, g, b):
    return ((r * 31 // 255) << 11) | ((g * 63 // 255) << 5) | (b * 31 // 255)

def c565_to_rgb(c):
    return (((c >> 11) & 0x1F) * 255 // 31,
            ((c >> 5) & 0x3F) * 255 // 63,
            (c & 0x1F) * 255 // 31)

def v_colors():
    # Reference table from spec §4.6 / source doc 08. (value is the on-wire 16-bit color)
    refs = [
        ("Black",     0x0000, (0, 0, 0)),
        ("White",     0xFFFF, (255, 255, 255)),
        ("Pure Red",  0xF800, (255, 0, 0)),
        ("Pure Green",0x07E0, (0, 255, 0)),
        ("Pure Blue", 0x001F, (0, 0, 255)),
        ("Yellow",    0xFFE0, (255, 255, 0)),
        ("Cyan",      0x07FF, (0, 255, 255)),
        ("Magenta",   0xF81F, (255, 0, 255)),
    ]
    cases = []
    for name, val, rgb8 in refs:
        # Check the canonical hex encodes the stated pure RGB and round-trips its LE bytes.
        assert rgb_to_565(*rgb8) == val, (name, hex(rgb_to_565(*rgb8)), hex(val))
        cases.append({
            "name": name,
            "rgb8_in": list(rgb8),
            "r5g6b5": f"0x{val:04X}",
            "le_bytes": hx(u16(val)),
            "rgb8_decoded": list(c565_to_rgb(val)),
        })
    transparency = [
        {"code": "0x000C", "alpha": 0.0, "meaning": "100% transparent"},
        {"code": "0x000D", "alpha": 0.2, "meaning": "80% transparent"},
        {"code": "0x000E", "alpha": 0.4, "meaning": "60% transparent"},
        {"code": "0x000F", "alpha": 0.6, "meaning": "40% transparent"},
        {"code": "0x0010", "alpha": 0.8, "meaning": "20% transparent"},
    ]
    # Encoder must bump an RGB result landing in the reserved band to the safe code 0x0011.
    reserved = {0x000C, 0x000D, 0x000E, 0x000F, 0x0010}
    write("04-colors-r5g6b5.json", {
        "vector": "colors-r5g6b5",
        "spec_ref": "CBDF/1.0 §4.6",
        "description": "R5G6B5 reference colors (2-byte LE on the wire) with decode-back, "
                       "plus the five reserved transparency codes and their alpha. Encoders "
                       "converting RGB->565 must divert any result in 0x000C-0x0010 to 0x0011.",
        "encoding": "little-endian",
        "colors": cases,
        "transparency_codes": transparency,
        "reserved_safe_code": "0x0011",
    })

# ======================================================================================
# 5. Resource section record framing (§4.8)
# ======================================================================================
def v_resource_record():
    data = bytes([0xDE, 0xAD, 0xBE, 0xEF])   # stand-in "PNG" payload, 4 bytes
    rec = bytes([0x00, 0x00]) + u32(len(data)) + data   # ResID 0, Type 0 (png), len, data
    payload = rec
    b = section(payload)   # [Len:4 LE][records...]
    assert len(payload) == 6 + len(data)
    ann = [
        {"hex": hx(u32(len(payload))), "field": f"Resources length = {len(payload)} (LE)"},
        {"hex": "00", "field": "Resource ID = 0"},
        {"hex": "00", "field": "Resource Type = 0 (image/png)"},
        {"hex": hx(u32(len(data))), "field": f"Data length = {len(data)} (LE)"},
        {"hex": hx(data), "field": "raw resource bytes (stand-in payload)"},
    ]
    write("05-resource-record.json", {
        "vector": "resource-record",
        "spec_ref": "CBDF/1.0 §4.8",
        "description": "A Resources section holding one packed record (no count field, no "
                       "separators). The parser walks records until the section length is "
                       "exhausted. Per-record overhead is 6 bytes.",
        "encoding": "little-endian",
        "length_bytes": len(b),
        "bytes_hex": b.hex(),
        "annotated": ann,
    })

# ======================================================================================
# 6. Plain-text extraction (§4.5.2) — strict and degraded
# ======================================================================================
def build_extraction_text():
    body = bytearray([STX])
    body += bytes([STYLE_TEXT, 0x00])            # push text style 0 (skip 1)
    body += "Hello ".encode()
    target = "example.com".encode()
    body += bytes([LINK_START, 0x00, len(target)]) + target  # URL link (skip 1+1+N)
    body += "site".encode()                      # visible link text -> kept
    body += bytes([LINK_END])
    body += " and ".encode()
    body += bytes([IMAGE, 0x00])                 # image (skip 1)
    body += bytes([LF])                          # newline -> kept
    body += bytes([STYLE_TABLE, 0x00])           # table (skip 1)
    body += "A".encode() + bytes([US]) + "B".encode() + bytes([RS])
    body += "C".encode() + bytes([US]) + "D".encode()
    body += bytes([BLOCK_END])
    body += bytes([PARA_BREAK])                  # paragraph break
    body += "Bye".encode()
    body += bytes([STYLE_END, ETX])
    return bytes(body)

# self-delimiting skip table (§4.5.2)
def extract(text, degrade=False):
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c >= 0x20:
            out.append(c); i += 1; continue
        if c in (TAB, LF):
            out.append(c); i += 1; continue
        # controls with payloads to skip:
        if c == HORIZ_RULE: i += 2
        elif c == LINK_START:
            ln = text[i + 2]; i += 3 + ln
        elif c == DATA_ESCAPE:
            ln = text[i + 1] | (text[i + 2] << 8); i += 3 + ln
        elif c in (STYLE_TEXT, STYLE_CONTAINER, STYLE_TABLE): i += 2
        elif c == ELEMENT_ID:
            i += 4 if text[i + 1] == 0xFF else 2
        elif c == IMAGE: i += 2
        elif c == ITEM_BLOCK: i += 3
        elif c == AI_PROMPT:
            ln = text[i + 2] | (text[i + 3] << 8); i += 4 + ln
        elif c == PARA_BREAK:
            if degrade: out += [LF, LF]
            i += 1
        elif c == RS:
            if degrade: out.append(LF)
            i += 1
        elif c == US:
            if degrade: out.append(TAB)
            i += 1
        else:
            i += 1  # STX, ETX, LINK_END, STYLE_END, BLOCK_END, SOH, etc. — no payload
    return bytes(out).decode("utf-8")

def v_extraction():
    body = build_extraction_text()
    strict = extract(body, degrade=False)
    degraded = extract(body, degrade=True)
    assert strict == "Hello site and \nABCDBye", repr(strict)
    assert degraded == "Hello site and \nA\tB\nC\tD\n\nBye", repr(degraded)
    write("06-plaintext-extraction.json", {
        "vector": "plaintext-extraction",
        "spec_ref": "CBDF/1.0 §4.5.2",
        "description": "A styled Text body (text style, URL link, image, a 2x2 table, a "
                       "paragraph break) and its plain-text extraction. Strict keeps bytes "
                       ">=0x20 plus TAB/LF and skips each control's self-delimiting payload. "
                       "Degraded additionally maps table US->TAB, RS->newline, PARA_BREAK->blank line.",
        "encoding": "little-endian",
        "text_body_hex": body.hex(),
        "text_body_annotated": hx(body),
        "expected_plain_strict": strict,
        "expected_plain_degraded": degraded,
    })

def main():
    print("Generating CBDF/1.0 test vectors ->", OUT)
    v_meta_only_sms()
    v_phase1_body()
    v_phase2_minimal()
    v_colors()
    v_resource_record()
    v_extraction()
    print("All vectors generated and self-checks passed.")

if __name__ == "__main__":
    main()
