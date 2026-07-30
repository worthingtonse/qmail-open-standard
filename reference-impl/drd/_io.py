"""Big-endian primitives, the RAIDA challenge, and a forward reader for DRD bodies.

DRD rides the RAIDA protocol wire (big-endian, `3E 3E` trailer) — the same wire
conventions as RKE, but DRD does not depend on RKE, so it keeps its own copy rather than
importing across standards. (A future in-repo RAIDA-protocol module could host the shared
big-endian/challenge/PQ primitives; the spec notes RAIDA is a candidate normative
standard.)
"""
import os
import struct
import zlib


class DRDError(ValueError):
    """A DRD body (or a value being encoded) violates the specification."""


TRAILER = b"\x3E\x3E"
CHALLENGE_LEN = 16


def be16(n: int) -> bytes:
    if not 0 <= n <= 0xFFFF:
        raise DRDError(f"be16 out of range: {n}")
    return struct.pack(">H", n)


def be32(n: int) -> bytes:
    if not 0 <= n <= 0xFFFFFFFF:
        raise DRDError(f"be32 out of range: {n}")
    return struct.pack(">I", n)


def be64(n: int) -> bytes:
    """Unsigned 64-bit big-endian (timestamps)."""
    if not 0 <= n <= 0xFFFFFFFFFFFFFFFF:
        raise DRDError(f"be64 out of range: {n}")
    return struct.pack(">Q", n)


def be64s(n: int) -> bytes:
    """Signed 64-bit big-endian (inbox fee)."""
    if not -(2 ** 63) <= n <= 2 ** 63 - 1:
        raise DRDError(f"signed int64 out of range: {n}")
    return struct.pack(">q", n)


def s8(n: int) -> bytes:
    """Signed 8-bit (denomination, class rejection)."""
    if not -128 <= n <= 127:
        raise DRDError(f"signed int8 out of range: {n}")
    return struct.pack("b", n)


def challenge(random12: bytes = None) -> bytes:
    """16-byte request challenge: 12 random bytes + their big-endian CRC32 (§4.2)."""
    if random12 is None:
        random12 = os.urandom(12)
    random12 = bytes(random12)
    if len(random12) != 12:
        raise DRDError(f"challenge seed must be 12 bytes, got {len(random12)}")
    return random12 + be32(zlib.crc32(random12) & 0xFFFFFFFF)


def challenge_is_valid(chal: bytes) -> bool:
    if len(chal) != CHALLENGE_LEN:
        return False
    return chal[12:16] == be32(zlib.crc32(chal[:12]) & 0xFFFFFFFF)


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
            raise DRDError(f"negative read length: {n}")
        if self.remaining < n:
            raise DRDError(f"truncated: wanted {n} bytes, {self.remaining} remain")
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

    def be64s(self) -> int:
        return struct.unpack(">q", self.take(8))[0]

    def challenge(self) -> bytes:
        return self.take(CHALLENGE_LEN)

    def expect_trailer(self) -> None:
        got = self.take(2)
        if got != TRAILER:
            raise DRDError(f"expected RAIDA trailer 3E 3E, found {got.hex()}")

    def expect_end(self) -> None:
        if not self.at_end():
            raise DRDError(f"unexpected trailing bytes at offset {self.pos} "
                           "(ERROR_INVALID_PACKET_LENGTH)")
