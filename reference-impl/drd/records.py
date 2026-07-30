"""DRD record formats: the coin address (PQ), the user record, and list entries (§4.4)."""
from dataclasses import dataclass

from ._io import DRDError, be32, be64, s8, Reader
from .constants import (
    MAX_NAME_LEN, DENOM_MIN, DENOM_MAX, LIST_WHITELIST, LIST_BLACKLIST,
)
from .fee import encode_fee


def _check_denom(dn: int, what: str = "denomination") -> None:
    if not DENOM_MIN <= dn <= DENOM_MAX:
        raise DRDError(f"{what} {dn} out of signed range {DENOM_MIN}..{DENOM_MAX}")


def pq(denomination: int, serial: int) -> bytes:
    """The 5-byte coin address / identity: [DN:1 signed][SN:4 BE] (§4.2)."""
    _check_denom(denomination)
    return s8(denomination) + be32(serial)


def _encode_name(name: str) -> bytes:
    b = name.encode("utf-8")
    if len(b) > MAX_NAME_LEN:
        raise DRDError(f"name exceeds {MAX_NAME_LEN} bytes: {len(b)}")
    return bytes([len(b)]) + b


def _read_name(r: Reader) -> str:
    length = r.byte()
    if length > MAX_NAME_LEN:
        raise DRDError(f"name length {length} exceeds {MAX_NAME_LEN}")
    return r.take(length).decode("utf-8")


@dataclass
class UserRecord:
    """A DRD user record (§4.4.1): 34 + name bytes, big-endian."""
    denomination: int
    serial: int
    fee_units: int
    symbol1: int
    symbol2: int
    class_rejection: int
    created_at: int
    updated_at: int
    first_name: str = ""
    last_name: str = ""

    def encode(self) -> bytes:
        _check_denom(self.denomination)
        _check_denom(self.class_rejection, "class rejection")
        for s in (self.symbol1, self.symbol2):
            if not 0 <= s <= 255:
                raise DRDError(f"avatar symbol out of range: {s}")
        return (s8(self.denomination) + be32(self.serial) + encode_fee(self.fee_units)
                + bytes([self.symbol1, self.symbol2]) + s8(self.class_rejection)
                + be64(self.created_at) + be64(self.updated_at)
                + _encode_name(self.first_name) + _encode_name(self.last_name))

    @classmethod
    def decode(cls, data, reader: Reader = None) -> "UserRecord":
        r = reader if reader is not None else Reader(data)
        dn = r.s8()
        sn = r.be32()
        fee = r.be64s()
        s1 = r.byte()
        s2 = r.byte()
        cr = r.s8()
        created = r.be64()
        updated = r.be64()
        first = _read_name(r)
        last = _read_name(r)
        return cls(dn, sn, fee, s1, s2, cr, created, updated, first, last)


@dataclass
class ListEntry:
    """A white/black list entry (§4.4.2)."""
    listed_dn: int
    listed_sn: int
    list_type: int = LIST_WHITELIST   # 0 whitelist, 1 blacklist

    def encode(self) -> bytes:
        _check_denom(self.listed_dn, "listed denomination")
        if self.list_type not in (LIST_WHITELIST, LIST_BLACKLIST):
            raise DRDError(f"list type must be 0 (white) or 1 (black), got "
                           f"{self.list_type}")
        return s8(self.listed_dn) + be32(self.listed_sn) + bytes([self.list_type])

    def encode_without_type(self) -> bytes:
        """5-byte form for list_remove (removal ignores type)."""
        _check_denom(self.listed_dn, "listed denomination")
        return s8(self.listed_dn) + be32(self.listed_sn)

    @classmethod
    def decode(cls, data) -> "ListEntry":
        r = Reader(data)
        return cls(r.s8(), r.be32(), r.byte())
