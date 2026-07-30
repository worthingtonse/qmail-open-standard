"""The CBDF document container: the five-section framing and its three wire shapes (§4.1).

A Phase II document is:
    [Meta] FS [Styles] FS [Text] FS [Resources] FS [Logic]  [FS extension sections...]
with a 4-byte LE length prefix on sections 2-5 (Meta uses its own KV framing). When Meta
key 31 (compression) is non-zero, the Styles and Text sections are replaced by a single
compressed blob (§4.9):
    [Meta] FS [CompLen:4][DecompLen:4][compressed] FS [Resources] FS [Logic]
whose decompressed contents are `[StylesLen][Styles] FS [TextLen][Text]`.

Two other shapes are handled here too:
  * meta-only (Meta key 33 = 1): the Meta section stands alone, no FS markers (§4.1);
  * Phase I body object: `FS FS STX [plain text ... EOF]` (§4.2, §5).
"""
from ._io import u32, CBDFError, Reader
from .constants import FS, STX, Meta as K, VERSION_PHASE_II, COMPRESS_NONE, COMPRESS_ZLIB
from .meta import MetaSection
from .styles import StylesSection
from . import text as textmod
from . import resources as resmod
from . import compression as compmod


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
    Compression is selected by Meta key 31 (0 none, 1 zlib); `extensions` is a list of
    `(section_id, payload)` appended after Logic (§4.10).
    """

    def __init__(self, meta: MetaSection, styles: StylesSection = None,
                 text_body: bytes = b"", resources=None, styled_subject: bytes = b"",
                 logic: bytes = b"", extensions=None):
        self.meta = meta
        self.styles = styles if styles is not None else StylesSection.minimal()
        self.text_body = bytes(text_body)
        self.styled_subject = bytes(styled_subject)
        self.resources = list(resources) if resources else []
        self.logic = bytes(logic)
        self.extensions = list(extensions) if extensions else []

    def _codec(self) -> int:
        v = self.meta.get(K.COMPRESSION)
        return 0 if v is None else v[0]

    def encode(self) -> bytes:
        self.meta.validate()
        if self.meta.is_meta_only:
            # Meta stands alone; no FS markers or sections follow (§4.1).
            return self.meta.encode()

        codec = self._codec()
        if not compmod.is_supported(codec):
            raise CBDFError(f"compression codec {codec} is not supported by this codec")
        if codec != COMPRESS_NONE and self.meta.has(K.TEXT_OFFSET):
            raise CBDFError("Meta key 40 (Text Offset) MUST be absent when key 31 != 0")
        if self.logic:
            raise CBDFError("Logic section MUST be empty in Phase II (§4.4.7)")

        styles_payload = self.styles.encode()
        text_payload = textmod.frame_body(self.text_body, self.styled_subject)

        out = bytearray(self.meta.encode())
        if codec == COMPRESS_NONE:
            out.append(FS)
            out += u32(len(styles_payload)) + styles_payload
            out.append(FS)
            out += u32(len(text_payload)) + text_payload
        else:
            inner = (u32(len(styles_payload)) + styles_payload + bytes([FS])
                     + u32(len(text_payload)) + text_payload)
            comp = compmod.compress(inner, codec)
            out.append(FS)
            out += u32(len(comp)) + u32(len(inner)) + comp
        out.append(FS)
        out += resmod.encode_section(self.resources)
        out.append(FS)
        out += u32(len(self.logic)) + self.logic  # canonical empty tail: FS 00 00 00 00
        for section_id, payload in self.extensions:
            if not 0 <= section_id <= 255:
                raise CBDFError(f"extension section id out of range: {section_id}")
            out.append(FS)
            out += bytes([section_id]) + u32(len(payload)) + bytes(payload)
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

    codec_v = meta.get(K.COMPRESSION)
    codec = 0 if codec_v is None else codec_v[0]
    if not compmod.is_supported(codec):
        raise CBDFError(f"compression codec {codec} is not supported by this codec")

    if codec == COMPRESS_NONE:
        styles = StylesSection.decode(_read_section(r))
        text_payload = _read_section(r)
    else:
        r.expect(FS, "FS before compressed Styles+Text blob")
        comp_len = r.u32()
        decomp_len = r.u32()
        comp = r.take(comp_len)
        inner = compmod.decompress(comp, codec, decomp_len)
        ir = Reader(inner)
        styles = StylesSection.decode(ir.take(ir.u32()))
        ir.expect(FS, "FS between Styles and Text inside the compressed blob")
        text_payload = ir.take(ir.u32())
        if not ir.at_end():
            raise CBDFError("trailing bytes inside the decompressed Styles+Text blob")

    if not text_payload or text_payload[0] != STX or text_payload[-1] != textmod.ETX:
        raise CBDFError("Text section must be framed by STX ... ETX (§4.5)")

    resources = resmod.decode(_read_section(r))

    logic = _read_section(r)
    if logic:
        raise CBDFError("non-zero Logic length in a v1 document is a hard failure (§4.4.7)")

    extensions = []
    while not r.at_end():
        r.expect(FS, "FS before extension section")
        section_id = r.byte()
        length = r.u32()
        extensions.append((section_id, r.take(length)))

    return {
        "kind": "phase2",
        "meta": meta,
        "compression": codec,
        "styles": styles,
        "text_payload": text_payload,
        "resources": resources,
        "extensions": extensions,
    }
