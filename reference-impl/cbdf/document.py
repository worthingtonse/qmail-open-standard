"""The CBDF document container: the five-section framing and its three wire shapes (§4.1).

A Phase II document is:
    [Meta] FS [Styles] FS [Text] FS [Resources] FS [Logic]
with a 4-byte LE length prefix on sections 2-5 (Meta uses its own KV framing). Two other
shapes exist and are handled here too:
  * meta-only (Meta key 33 = 1): the Meta section stands alone, no FS markers (§4.1);
  * Phase I body object: `FS FS STX [plain text ... EOF]` (§4.2, §5).

Compression (key 31) is not yet implemented; this codec emits and accepts only
uncompressed (key 31 absent or 0) documents. See reference-impl/README.md.
"""
from ._io import u32, CBDFError, Reader
from .constants import FS, STX, Meta as K, VERSION_PHASE_II
from .meta import MetaSection
from .styles import StylesSection
from . import text as textmod
from . import resources as resmod


# --- Phase I body object (§4.2, §5) --------------------------------------------------
def encode_phase1_body(body_text) -> bytes:
    """A backward-compatible Phase I body: FS FS STX + plain UTF-8 to EOF.

    Detected on decode by the absence of Meta key 30. ETX is not required.
    """
    if isinstance(body_text, str):
        body_text = body_text.encode("utf-8")
    return bytes([FS, FS, STX]) + bytes(body_text)


class Document:
    """A Phase II CBDF document model.

    `meta` MUST set key 30 = 1 (Phase II) unless it is meta-only (key 33 = 1). The
    canonical encode always emits the Resources and Logic tails, empty as `FS 00000000`.
    """

    def __init__(self, meta: MetaSection, styles: StylesSection = None,
                 text_body: bytes = b"", resources=None, styled_subject: bytes = b"",
                 logic: bytes = b""):
        self.meta = meta
        self.styles = styles if styles is not None else StylesSection.minimal()
        self.text_body = bytes(text_body)
        self.styled_subject = bytes(styled_subject)
        self.resources = list(resources) if resources else []
        self.logic = bytes(logic)

    def encode(self) -> bytes:
        self.meta.validate()
        if self.meta.is_meta_only:
            # Meta stands alone; no FS markers or sections follow (§4.1).
            return self.meta.encode()

        if self.meta.get(K.COMPRESSION) not in (None, bytes([0])):
            raise CBDFError("compression (key 31 != 0) is not supported by this "
                            "reference codec yet")
        if self.logic:
            raise CBDFError("Logic section MUST be empty in Phase II (§4.4.7)")

        out = bytearray(self.meta.encode())
        out.append(FS)
        out += self.styles.encode_section()
        out.append(FS)
        out += textmod.encode_section(self.text_body, self.styled_subject)
        out.append(FS)
        out += resmod.encode_section(self.resources)
        out.append(FS)
        out += u32(len(self.logic)) + self.logic  # canonical empty tail: FS 00 00 00 00
        return bytes(out)


def _read_section(r: Reader) -> bytes:
    """Consume `FS [Len:4 LE][payload]` and return the payload."""
    r.expect(FS, "FS section separator")
    length = r.u32()
    return r.take(length)


def parse(data: bytes) -> dict:
    """Parse any CBDF wire shape into a tagged dict describing what was found.

    Returns a dict with a `kind` of "phase1", "meta_only", or "phase2". This is a
    structural parse; it validates framing but performs no trust decisions (those belong
    to QMail Tell integration, §4.3.4).
    """
    b = bytes(data)

    # Phase I body object: FS FS STX ... (no Meta section) — §4.2/§5.
    if len(b) >= 3 and b[0] == FS and b[1] == FS and b[2] == STX:
        return {"kind": "phase1", "body": b[3:]}

    r = Reader(b)
    meta = MetaSection.decode(b, reader=r)

    if meta.is_meta_only:
        if not r.at_end():
            raise CBDFError("meta-only document (key 33=1) has trailing bytes after Meta")
        return {"kind": "meta_only", "meta": meta}

    version = meta.get(K.VERSION)
    if version is None:
        raise CBDFError("multi-section document without Meta key 30 (Version); a "
                        "version-less body must use the Phase I FS FS STX shape")
    if version != bytes([VERSION_PHASE_II]):
        raise CBDFError(f"unsupported wire version {list(version)}; this codec "
                        f"implements Phase II (version 1) only")
    if meta.get(K.COMPRESSION) not in (None, bytes([0])):
        raise CBDFError("compressed documents (key 31 != 0) are not supported yet")

    styles = StylesSection.decode(_read_section(r))

    text_payload = _read_section(r)
    if not text_payload or text_payload[0] != STX or text_payload[-1] != textmod.ETX:
        raise CBDFError("Text section must be framed by STX ... ETX (§4.5)")

    resources = resmod.decode(_read_section(r))

    logic = _read_section(r)
    if logic:
        raise CBDFError("non-zero Logic length in a v1 document is a hard failure (§4.4.7)")

    if not r.at_end():
        raise CBDFError(f"trailing bytes after Logic section at offset {r.pos} "
                        "(extension sections not yet implemented, §4.10)")

    return {
        "kind": "phase2",
        "meta": meta,
        "styles": styles,
        "text_payload": text_payload,
        "resources": resources,
    }
