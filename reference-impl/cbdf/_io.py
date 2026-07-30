"""Little-endian primitives and a small forward byte reader.

All multi-byte integers in CBDF are little-endian (§2). These helpers are the only
place that knows the byte order, so the rest of the codec stays declarative.
"""
import struct


class CBDFError(ValueError):
    """A CBDF document (or a value being encoded) violates the specification."""


def u16(n: int) -> bytes:
    """Encode a 16-bit unsigned integer, little-endian."""
    if not 0 <= n <= 0xFFFF:
        raise CBDFError(f"u16 out of range: {n}")
    return struct.pack("<H", n)


def u32(n: int) -> bytes:
    """Encode a 32-bit unsigned integer, little-endian."""
    if not 0 <= n <= 0xFFFFFFFF:
        raise CBDFError(f"u32 out of range: {n}")
    return struct.pack("<I", n)


def u64(n: int) -> bytes:
    """Encode a 64-bit unsigned integer, little-endian."""
    if not 0 <= n <= 0xFFFFFFFFFFFFFFFF:
        raise CBDFError(f"u64 out of range: {n}")
    return struct.pack("<Q", n)


def read_u16(b: bytes, off: int) -> int:
    return b[off] | (b[off + 1] << 8)


def read_u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


class Reader:
    """A cursor over a byte string with bounds-checked forward reads.

    CBDF parsing is strictly left-to-right (§5 "canonical, strict parsing"), so a
    forward-only reader is all the codec needs — and it makes over-reads a clear error
    rather than a silent slice.
    """

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def __len__(self) -> int:
        return len(self.data)

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos

    def at_end(self) -> bool:
        return self.pos >= len(self.data)

    def peek(self) -> int:
        """The next byte without consuming it; raises at end of input."""
        if self.at_end():
            raise CBDFError("unexpected end of input")
        return self.data[self.pos]

    def byte(self) -> int:
        b = self.peek()
        self.pos += 1
        return b

    def take(self, n: int) -> bytes:
        if n < 0:
            raise CBDFError(f"negative read length: {n}")
        if self.remaining < n:
            raise CBDFError(f"truncated: wanted {n} bytes, {self.remaining} remain")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def u16(self) -> int:
        return read_u16(self.data, self._advance(2))

    def u32(self) -> int:
        return read_u32(self.data, self._advance(4))

    def expect(self, byte: int, what: str) -> None:
        got = self.byte()
        if got != byte:
            raise CBDFError(f"expected {what} (0x{byte:02X}) but found 0x{got:02X} "
                            f"at offset {self.pos - 1}")

    def _advance(self, n: int) -> int:
        if self.remaining < n:
            raise CBDFError(f"truncated: wanted {n} bytes, {self.remaining} remain")
        off = self.pos
        self.pos += n
        return off
