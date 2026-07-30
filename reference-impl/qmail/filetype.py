"""The QMail object model: file_type -> storage suffix + CBDF role, and manifest order (§4.4).

Each stored object is tagged by a 1-byte file_type that selects both a storage suffix and
a role within the CBDF document ([CBDF/1.0]). The Tell manifest lists private meta first,
body second, then attachments; the recipient passes file_type back in `download` to fetch
a specific object. Human-readable fields live only in file_type=0 — never in the public
Tell (the §4.4 privacy boundary).
"""
from ._errors import QMailError
from .constants import FT_ATTACHMENT_BASE

# Fixed-role file types (0–5). Attachments (10+) are computed, not table entries.
_FIXED = {
    0: (".meta", "Private CBDF Meta (subject/preview/display)", "CBDF/1.0 §4.3"),
    1: (".qmail", "Body/content object (CBDF body)", "CBDF/1.0 §4.1"),
    2: (".style", "CBDF Styles section", "CBDF/1.0 §4.4"),
    3: (".text", "CBDF Text section", "CBDF/1.0 §4.5"),
    4: (".resource", "CBDF Resources section", "CBDF/1.0 §4.8"),
    5: (".logic", "CBDF Logic section (Phase III)", "CBDF/1.0 §4.4.7"),
}
_RESERVED = range(6, 10)  # 6–9 reserved (.blob)


def suffix(file_type: int) -> str:
    """Storage suffix for a file_type. Attachments: 10 -> .0.bin, 11 -> .1.bin, ..."""
    if not 0 <= file_type <= 255:
        raise QMailError(f"file_type out of range: {file_type}")
    if file_type in _FIXED:
        return _FIXED[file_type][0]
    if file_type in _RESERVED:
        return ".blob"
    if file_type >= FT_ATTACHMENT_BASE:
        return f".{file_type - FT_ATTACHMENT_BASE}.bin"
    raise QMailError(f"unmapped file_type: {file_type}")


def role(file_type: int) -> str:
    if file_type in _FIXED:
        return _FIXED[file_type][1]
    if file_type in _RESERVED:
        return "Reserved"
    if file_type >= FT_ATTACHMENT_BASE:
        n = file_type - FT_ATTACHMENT_BASE
        return "First attachment" if n == 0 else f"Attachment {n}"
    raise QMailError(f"unmapped file_type: {file_type}")


def cbdf_ref(file_type: int):
    """The CBDF section this file_type maps onto, or None for body/reserved/attachments."""
    return _FIXED[file_type][2] if file_type in _FIXED and file_type != 1 else None


def is_attachment(file_type: int) -> bool:
    return file_type >= FT_ATTACHMENT_BASE


def manifest_order(file_types) -> list:
    """Canonical Tell manifest order: private meta (0) first, body (1) second, then the
    remaining objects by ascending file_type (attachments last, in order)."""
    fts = list(file_types)
    for ft in fts:
        suffix(ft)  # validates each file_type
    return sorted(fts)
