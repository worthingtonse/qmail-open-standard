"""The Text section and its control language: framing, and degrade-to-text (§4.5).

The Text payload is [STX][optional SOH styled subject][body][ETX]. This module frames a
body and implements plain-text extraction — the normative "degrade to readable text"
behavior (§4.5.2), which every conforming reader MUST provide.
"""
from ._io import u16, u32, CBDFError, Reader
from .constants import (
    STX, ETX, SOH, TAB, LF, PARA_BREAK, HORIZ_RULE, LINK_START, LINK_END, DATA_ESCAPE,
    STYLE_TEXT, STYLE_CONTAINER, STYLE_TABLE, STYLE_END, ELEMENT_ID, IMAGE, BLOCK_END,
    ITEM_BLOCK, AI_PROMPT, RS, US,
)


def frame_body(body: bytes, styled_subject: bytes = b"") -> bytes:
    """Wrap a body as a Text payload: STX [SOH subject] body ETX."""
    out = bytearray([STX])
    if styled_subject:
        out.append(SOH)
        out += styled_subject
    out += body
    out.append(ETX)
    return bytes(out)


def encode_section(body: bytes, styled_subject: bytes = b"") -> bytes:
    """The Text section as it appears after its FS: [Len:4 LE][STX...ETX]."""
    payload = frame_body(body, styled_subject)
    return u32(len(payload)) + payload


def extract_plaintext(text_payload: bytes, degrade: bool = False) -> str:
    """Degrade a Text payload to readable UTF-8 (§4.5.2).

    Keeps bytes >= 0x20 plus TAB and LF; skips every other control code together with
    its self-delimiting payload. `degrade=True` additionally maps table/structure
    separators to whitespace: US->TAB, RS->newline, PARA_BREAK->blank line.
    """
    b = bytes(text_payload)
    out = bytearray()
    i, n = 0, len(b)
    while i < n:
        c = b[i]
        if c >= 0x20 or c in (TAB, LF):
            out.append(c)
            i += 1
            continue
        # Controls carrying a self-delimiting payload — skip command + payload.
        if c == HORIZ_RULE:
            i += 2                                   # + StyleIndex:1
        elif c == LINK_START:
            i += 3 + _need(b, i + 2)                 # + Type:1 Len:1 Target:N
        elif c == DATA_ESCAPE:
            i += 3 + _le16(b, i + 1)                 # + Len:2 Data:N
        elif c in (STYLE_TEXT, STYLE_CONTAINER, STYLE_TABLE):
            i += 2                                    # + Index:1
        elif c == ELEMENT_ID:
            i += 4 if _need(b, i + 1) == 0xFF else 2  # +1, or +3 when first byte is 0xFF
        elif c == IMAGE:
            i += 2                                    # + ImageDefIndex:1
        elif c == ITEM_BLOCK:
            i += 3                                    # + Type:1 StyleIndex:1
        elif c == AI_PROMPT:
            i += 4 + _le16(b, i + 2)                 # + Type:1 Len:2 UTF-8:N
        elif c == PARA_BREAK:
            if degrade:
                out += bytes([LF, LF])
            i += 1
        elif c == RS:
            if degrade:
                out.append(LF)
            i += 1
        elif c == US:
            if degrade:
                out.append(TAB)
            i += 1
        else:
            # STX, ETX, SOH, LINK_END, STYLE_END, BLOCK_END, NOP, PAGE_BREAK, ... : no payload
            i += 1
    return out.decode("utf-8")


def _need(b: bytes, i: int) -> int:
    if i >= len(b):
        raise CBDFError("truncated control payload during extraction")
    return b[i]


def _le16(b: bytes, i: int) -> int:
    if i + 1 >= len(b):
        raise CBDFError("truncated 2-byte length during extraction")
    return b[i] | (b[i + 1] << 8)
