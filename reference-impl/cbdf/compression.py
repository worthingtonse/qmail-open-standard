"""Compression of the Styles+Text blob (Meta key 31, §4.9).

Only the Styles+Text blob is ever CBDF-compressed; Meta and Resources never are. This
codec implements the mandatory-to-implement DEFLATE/zlib codec (key 31 = 1). The other
registered codecs (LZ4/Zstd/Brotli, keys 2-4) are optional and not built here; semantic
(5) is Phase III.

Zip-bomb resistance (§5): decode is bounded by the document's declared DecompLen and by
an absolute cap, and it verifies the decompressed size matches exactly.
"""
import zlib

from ._io import CBDFError
from .constants import COMPRESS_NONE, COMPRESS_ZLIB

# Absolute ceiling on a single decompressed Styles+Text blob (defense in depth on top of
# the per-document DecompLen). Generous for documents; tune per deployment.
MAX_DECOMPRESSED = 64 * 1024 * 1024

SUPPORTED = frozenset({COMPRESS_NONE, COMPRESS_ZLIB})


def is_supported(codec: int) -> bool:
    return codec in SUPPORTED


def compress(blob: bytes, codec: int) -> bytes:
    if codec == COMPRESS_NONE:
        return bytes(blob)
    if codec == COMPRESS_ZLIB:
        return zlib.compress(bytes(blob), 9)
    raise CBDFError(f"compression codec {codec} is not supported by this reference "
                    f"encoder (only 0 none and 1 zlib)")


def decompress(data: bytes, codec: int, decomp_len: int) -> bytes:
    """Decompress `data` to exactly `decomp_len` bytes, or raise."""
    if codec == COMPRESS_NONE:
        if len(data) != decomp_len:
            raise CBDFError("uncompressed blob length disagrees with DecompLen")
        return bytes(data)
    if codec != COMPRESS_ZLIB:
        raise CBDFError(f"compression codec {codec} is not supported by this reference "
                        f"decoder (only 0 none and 1 zlib)")
    if decomp_len < 0 or decomp_len > MAX_DECOMPRESSED:
        raise CBDFError(f"DecompLen {decomp_len} exceeds the {MAX_DECOMPRESSED}-byte cap")

    d = zlib.decompressobj()
    out = d.decompress(bytes(data), decomp_len)
    if not d.eof or d.unconsumed_tail:
        # Stream produced more than DecompLen declared (or did not terminate) -> reject.
        raise CBDFError("decompressed data exceeds declared DecompLen (possible zip bomb)")
    out += d.flush()
    if len(out) != decomp_len:
        raise CBDFError(f"decompressed size {len(out)} != declared DecompLen {decomp_len}")
    return out
