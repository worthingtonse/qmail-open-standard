"""The Meta section: the document envelope (§4.3).

Meta is never compressed and always readable without touching Styles/Text. It is a
2-byte LE pair count followed by [key:1][len:1][value:N] triples. Values are 0-255
bytes; there is no extended-length sentinel.
"""
from ._io import u16, u32, u64, CBDFError, Reader
from .constants import (
    Meta as K, CLOUDCOIN_COIN_GROUP, RETIRED_META_KEY, META_ONLY_FORBIDDEN_KEYS,
)


def mailbox(denom: int, serial: int, group: int = CLOUDCOIN_COIN_GROUP) -> bytes:
    """A 7-byte mailbox: [CoinGroup:2][Denomination:1][Serial:4 LE] (§4.3.5).

    The coin-group field is written big-endian-looking (00 06 for CloudCoin); only the
    serial number is a little-endian scalar.
    """
    if not 0 <= denom <= 255:
        raise CBDFError(f"denomination out of range: {denom}")
    if not 0 <= group <= 0xFFFF:
        raise CBDFError(f"coin group out of range: {group}")
    return bytes([(group >> 8) & 0xFF, group & 0xFF, denom]) + u32(serial)


def parse_mailbox(b: bytes) -> dict:
    if len(b) != 7:
        raise CBDFError(f"mailbox must be 7 bytes, got {len(b)}")
    return {
        "coin_group": (b[0] << 8) | b[1],
        "denomination": b[2],
        "serial": b[3] | (b[4] << 8) | (b[5] << 16) | (b[6] << 24),
    }


class MetaSection:
    """An ordered list of (key, value_bytes) pairs.

    Order is preserved on the wire (keys MAY appear in any order; §4.3 recommends key 0
    then key 30 early). Repeated keys — e.g. multiple `To` recipients — are allowed and
    each counts toward the pair count.
    """

    def __init__(self, pairs=None):
        self.pairs = list(pairs) if pairs else []

    # -- building -------------------------------------------------------------------
    def add(self, key: int, value: bytes) -> "MetaSection":
        if not 0 <= key <= 255:
            raise CBDFError(f"meta key out of range: {key}")
        if key == RETIRED_META_KEY:
            raise CBDFError("meta key 34 is permanently retired and MUST NOT be emitted")
        value = bytes(value)
        if len(value) > 255:
            raise CBDFError(f"meta value for key {key} exceeds 255 bytes ({len(value)})")
        self.pairs.append((key, value))
        return self

    def add_u8(self, key: int, n: int) -> "MetaSection":
        if not 0 <= n <= 255:
            raise CBDFError(f"u8 value out of range: {n}")
        return self.add(key, bytes([n]))

    def add_u32(self, key: int, n: int) -> "MetaSection":
        return self.add(key, u32(n))

    def add_u64(self, key: int, n: int) -> "MetaSection":
        return self.add(key, u64(n))

    def add_text(self, key: int, s: str) -> "MetaSection":
        return self.add(key, s.encode("utf-8"))

    # -- lookup ---------------------------------------------------------------------
    def get(self, key: int):
        """First value for `key`, or None. Use `get_all` for repeated keys."""
        for k, v in self.pairs:
            if k == key:
                return v
        return None

    def get_all(self, key: int) -> list:
        return [v for k, v in self.pairs if k == key]

    def has(self, key: int) -> bool:
        return any(k == key for k, _ in self.pairs)

    @property
    def is_meta_only(self) -> bool:
        v = self.get(K.EOF_FLAG)
        return v is not None and len(v) == 1 and v[0] == 1

    # -- (de)serialization ----------------------------------------------------------
    def validate(self) -> None:
        if len(self.pairs) > 0xFFFF:
            raise CBDFError("too many meta pairs for a 16-bit count")
        if self.is_meta_only:
            for k, _ in self.pairs:
                if k in META_ONLY_FORBIDDEN_KEYS:
                    raise CBDFError(
                        f"meta-only document (key 33=1) MUST NOT carry key {k} (§4.3.2)")

    def encode(self) -> bytes:
        self.validate()
        out = bytearray(u16(len(self.pairs)))
        for k, v in self.pairs:
            out += bytes([k, len(v)]) + v
        return bytes(out)

    @classmethod
    def decode(cls, data, reader: Reader = None) -> "MetaSection":
        """Parse a Meta section. Pass a Reader to continue parsing after it."""
        r = reader if reader is not None else Reader(bytes(data))
        count = r.u16()
        pairs = []
        for _ in range(count):
            key = r.byte()
            length = r.byte()
            value = r.take(length)
            pairs.append((key, value))
        return cls(pairs)
