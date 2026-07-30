"""Big-endian primitives and a forward reader for RKE bodies.

RKE rides the RAIDA protocol wire, whose multi-byte integers are **big-endian** — the
opposite of CBDF (little-endian). Keeping RKE's byte-order helpers in their own module,
separate from the CBDF codec, is deliberate: the two are independent wire worlds and a
QMail implementation must convert at the boundary, never reinterpret one as the other.
"""
import struct


class RKEError(ValueError):
    """An RKE body (or a value being encoded) violates the specification."""


# RAIDA two-byte body terminator (§4.1).
TRAILER = b"\x3E\x3E"


def be16(n: int) -> bytes:
    if not 0 <= n <= 0xFFFF:
        raise RKEError(f"be16 out of range: {n}")
    return struct.pack(">H", n)


def be32(n: int) -> bytes:
    if not 0 <= n <= 0xFFFFFFFF:
        raise RKEError(f"be32 out of range: {n}")
    return struct.pack(">I", n)


def be64(n: int) -> bytes:
    if not 0 <= n <= 0xFFFFFFFFFFFFFFFF:
        raise RKEError(f"be64 out of range: {n}")
    return struct.pack(">Q", n)


def s8(n: int) -> bytes:
    """Signed 8-bit — CloudCoin denominations are signed (§4.2)."""
    if not -128 <= n <= 127:
        raise RKEError(f"signed int8 out of range: {n}")
    return struct.pack("b", n)


class Reader:
    """A cursor over a body with bounds-checked, big-endian forward reads."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int = 0):
        self.data = bytes(data)
        self.pos = pos

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos

    def at_end(self) -> bool:
        return self.pos >= len(self.data)

    def take(self, n: int) -> bytes:
        if n < 0:
            raise RKEError(f"negative read length: {n}")
        if self.remaining < n:
            raise RKEError(f"truncated: wanted {n} bytes, {self.remaining} remain")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def byte(self) -> int:
        return self.take(1)[0]

    def s8(self) -> int:
        return struct.unpack("b", self.take(1))[0]

    def be16(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def be32(self) -> int:
        return struct.unpack(">I", self.take(4))[0]

    def be64(self) -> int:
        return struct.unpack(">Q", self.take(8))[0]

    def expect_trailer(self) -> None:
        got = self.take(2)
        if got != TRAILER:
            raise RKEError(f"expected RAIDA trailer 3E 3E, found {got.hex()}")

    def expect_end(self) -> None:
        if not self.at_end():
            raise RKEError(f"unexpected trailing bytes at offset {self.pos}")
