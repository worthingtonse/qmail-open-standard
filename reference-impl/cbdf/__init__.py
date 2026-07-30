"""CBDF/1.0 (Phase II) reference codec.

A small, dependency-free implementation of the Compact Binary Document Format defined in
`specs/cbdf-1.0.md`, optimizing for clarity and correctness against the spec (and the
conformance vectors in `test-vectors/cbdf/`), not performance.

Quick start:

    from cbdf import Document, MetaSection, StylesSection, constants as C

    meta = (MetaSection()
            .add_u8(C.Meta.FILE_TYPE, C.FILE_TYPE_GENERIC)
            .add_u8(C.Meta.VERSION, C.VERSION_PHASE_II))
    doc = Document(meta, StylesSection.minimal(), text_body=b"Hello")
    wire = doc.encode()
    parsed = cbdf.parse(wire)          # -> {"kind": "phase2", "meta": ..., ...}
"""
from . import constants
from ._io import CBDFError
from .color import (
    rgb_to_565, c565_to_rgb, encode_rgb, divert_reserved, is_transparency,
    TRANSPARENCY, RESERVED_SAFE_CODE,
)
from .meta import MetaSection, mailbox, parse_mailbox
from .styles import StylesSection, SubTable
from . import records
from .records import (
    TextStyle, Background, Border, Spacing, Shadow, Composite, FontEffect,
    NavBar, Table, ImageDef, FrameDef, decode_record,
)
from .resources import Resource
from . import text
from .text import extract_plaintext, frame_body
from . import compression
from .document import Document, parse, encode_phase1_body

__all__ = [
    "constants", "CBDFError",
    "rgb_to_565", "c565_to_rgb", "encode_rgb", "divert_reserved", "is_transparency",
    "TRANSPARENCY", "RESERVED_SAFE_CODE",
    "MetaSection", "mailbox", "parse_mailbox",
    "StylesSection", "SubTable",
    "records", "decode_record",
    "TextStyle", "Background", "Border", "Spacing", "Shadow", "Composite",
    "FontEffect", "NavBar", "Table", "ImageDef", "FrameDef",
    "Resource",
    "text", "extract_plaintext", "frame_body",
    "compression",
    "Document", "parse", "encode_phase1_body",
]

__version__ = "0.1.0"
