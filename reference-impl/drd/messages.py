"""The seven Group 16 command bodies and their response payloads (§4.5).

Each request body is big-endian, begins with a 16-byte challenge, and ends with the
RAIDA `3E 3E` trailer. The RAIDA header (group/code, routing) and the encryption
envelope come from the RAIDA protocol layer and are not part of these bodies. Success
status (250) and error codes travel in the RAIDA response header (§4.6), so the response
classes here model only the payloads that carry data (get_user, search_users, list_get).
"""
from dataclasses import dataclass, field

from ._io import DRDError, be16, be32, s8, TRAILER, Reader
from .constants import (
    AN_LEN, CHALLENGE_LEN, MAX_NAME_LEN, LIST_ENTRY_LEN, LIST_REMOVE_ENTRY_LEN,
    SEARCH_FLAG_FIRST, SEARCH_FLAG_LAST, DENOM_MIN, DENOM_MAX,
)
from .records import UserRecord, ListEntry, pq, _encode_name, _read_name, _check_denom
from .fee import encode_fee


def _check_challenge(chal: bytes) -> None:
    if len(chal) != CHALLENGE_LEN:
        raise DRDError(f"challenge must be {CHALLENGE_LEN} bytes, got {len(chal)}")


def _check_an(an: bytes) -> None:
    if len(an) != AN_LEN:
        raise DRDError(f"AN must be {AN_LEN} bytes, got {len(an)}")


# --- 140 post_user ------------------------------------------------------------------
@dataclass
class PostUserRequest:
    challenge: bytes
    denomination: int
    serial: int
    an: bytes
    fee_units: int = 0
    symbol1: int = 0
    symbol2: int = 0
    class_rejection: int = 0
    first_name: str = ""
    last_name: str = ""

    def encode(self) -> bytes:
        _check_challenge(self.challenge)
        _check_an(self.an)
        _check_denom(self.class_rejection, "class rejection")
        for sym in (self.symbol1, self.symbol2):
            if not 0 <= sym <= 255:
                raise DRDError(f"avatar symbol out of range: {sym}")
        return (bytes(self.challenge) + pq(self.denomination, self.serial) + bytes(self.an)
                + encode_fee(self.fee_units) + bytes([self.symbol1, self.symbol2])
                + s8(self.class_rejection)
                + _encode_name(self.first_name) + _encode_name(self.last_name) + TRAILER)

    @classmethod
    def decode(cls, data: bytes) -> "PostUserRequest":
        r = Reader(data)
        chal = r.challenge()
        dn = r.s8(); sn = r.be32(); an = r.take(AN_LEN)
        fee = r.be64s(); s1 = r.byte(); s2 = r.byte(); cr = r.s8()
        first = _read_name(r); last = _read_name(r)
        r.expect_trailer(); r.expect_end()
        return cls(chal, dn, sn, an, fee, s1, s2, cr, first, last)


# --- 141 get_user -------------------------------------------------------------------
@dataclass
class GetUserRequest:
    challenge: bytes
    denomination: int
    serial: int

    def encode(self) -> bytes:
        _check_challenge(self.challenge)
        return bytes(self.challenge) + pq(self.denomination, self.serial) + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "GetUserRequest":
        r = Reader(data)
        chal = r.challenge(); dn = r.s8(); sn = r.be32()
        r.expect_trailer(); r.expect_end()
        return cls(chal, dn, sn)


# get_user success response is a single UserRecord (§4.4.1) — use UserRecord.decode.


# --- 142 search_users ---------------------------------------------------------------
@dataclass
class SearchUsersRequest:
    challenge: bytes
    limit: int = 0
    first_prefix: str = None   # None = field absent
    last_prefix: str = None

    def encode(self) -> bytes:
        _check_challenge(self.challenge)
        if not 0 <= self.limit <= 255:
            raise DRDError(f"limit must fit in one byte: {self.limit}")
        flags = 0
        body = bytearray(self.challenge)
        if self.first_prefix is not None:
            flags |= SEARCH_FLAG_FIRST
        if self.last_prefix is not None:
            flags |= SEARCH_FLAG_LAST
        if flags == 0:
            raise DRDError("search_users needs at least one name field "
                           "(ERROR_INVALID_PARAMETER 198)")
        body += bytes([flags, self.limit])
        if self.first_prefix is not None:
            body += _encode_name(self.first_prefix)
        if self.last_prefix is not None:
            body += _encode_name(self.last_prefix)
        return bytes(body) + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "SearchUsersRequest":
        r = Reader(data)
        chal = r.challenge()
        flags = r.byte(); limit = r.byte()
        if flags & ~(SEARCH_FLAG_FIRST | SEARCH_FLAG_LAST):
            raise DRDError(f"unknown search flag bits set: 0x{flags:02X}")
        if flags == 0:
            raise DRDError("search_users needs at least one name field")
        first = _read_name(r) if flags & SEARCH_FLAG_FIRST else None
        last = _read_name(r) if flags & SEARCH_FLAG_LAST else None
        r.expect_trailer(); r.expect_end()
        return cls(chal, limit, first, last)


@dataclass
class SearchUsersResponse:
    """Success payload: 1-byte count + that many variable-length user records (§4.5)."""
    users: list = field(default_factory=list)

    def encode(self) -> bytes:
        if not 0 <= len(self.users) <= 255:
            raise DRDError("search result count must fit in one byte")
        out = bytes([len(self.users)])
        for u in self.users:
            out += u.encode()
        return out

    @classmethod
    def decode(cls, data: bytes) -> "SearchUsersResponse":
        r = Reader(data)
        count = r.byte()
        users = [UserRecord.decode(None, reader=r) for _ in range(count)]
        r.expect_end()
        return cls(users)


# --- 143 delete_user ----------------------------------------------------------------
@dataclass
class DeleteUserRequest:
    challenge: bytes
    denomination: int
    serial: int
    an: bytes

    def encode(self) -> bytes:
        _check_challenge(self.challenge)
        _check_an(self.an)
        return (bytes(self.challenge) + pq(self.denomination, self.serial)
                + bytes(self.an) + TRAILER)

    @classmethod
    def decode(cls, data: bytes) -> "DeleteUserRequest":
        r = Reader(data)
        chal = r.challenge(); dn = r.s8(); sn = r.be32(); an = r.take(AN_LEN)
        r.expect_trailer(); r.expect_end()
        return cls(chal, dn, sn, an)


# --- 144 list_set / 145 list_remove -------------------------------------------------
def _owner_prefix(challenge, denomination, serial, an) -> bytes:
    _check_challenge(challenge)
    _check_an(an)
    return bytes(challenge) + pq(denomination, serial) + bytes(an)


@dataclass
class ListSetRequest:
    challenge: bytes
    denomination: int
    serial: int
    an: bytes
    entries: list = field(default_factory=list)

    def encode(self) -> bytes:
        body = bytearray(_owner_prefix(self.challenge, self.denomination, self.serial, self.an))
        for e in self.entries:
            body += e.encode()          # 6-byte entries
        return bytes(body) + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "ListSetRequest":
        r = Reader(data)
        chal = r.challenge(); dn = r.s8(); sn = r.be32(); an = r.take(AN_LEN)
        region = r.remaining - 2       # everything up to the trailer
        if region < 0 or region % LIST_ENTRY_LEN != 0:
            raise DRDError("list_set entry region is not a multiple of 6 bytes "
                           "(ERROR_COINS_NOT_DIV 39)")
        entries = [ListEntry.decode(r.take(LIST_ENTRY_LEN)) for _ in range(region // LIST_ENTRY_LEN)]
        r.expect_trailer(); r.expect_end()
        return cls(chal, dn, sn, an, entries)


@dataclass
class ListRemoveRequest:
    challenge: bytes
    denomination: int
    serial: int
    an: bytes
    entries: list = field(default_factory=list)

    def encode(self) -> bytes:
        body = bytearray(_owner_prefix(self.challenge, self.denomination, self.serial, self.an))
        for e in self.entries:
            body += e.encode_without_type()   # 5-byte entries
        return bytes(body) + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "ListRemoveRequest":
        r = Reader(data)
        chal = r.challenge(); dn = r.s8(); sn = r.be32(); an = r.take(AN_LEN)
        region = r.remaining - 2
        if region < 0 or region % LIST_REMOVE_ENTRY_LEN != 0:
            raise DRDError("list_remove entry region is not a multiple of 5 bytes "
                           "(ERROR_COINS_NOT_DIV 39)")
        entries = []
        for _ in range(region // LIST_REMOVE_ENTRY_LEN):
            entries.append(ListEntry(r.s8(), r.be32()))
        r.expect_trailer(); r.expect_end()
        return cls(chal, dn, sn, an, entries)


# --- 146 list_get -------------------------------------------------------------------
@dataclass
class ListGetRequest:
    challenge: bytes
    denomination: int
    serial: int
    an: bytes

    def encode(self) -> bytes:
        return _owner_prefix(self.challenge, self.denomination, self.serial, self.an) + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "ListGetRequest":
        r = Reader(data)
        chal = r.challenge(); dn = r.s8(); sn = r.be32(); an = r.take(AN_LEN)
        r.expect_trailer(); r.expect_end()
        return cls(chal, dn, sn, an)


@dataclass
class ListGetResponse:
    """Success payload: 2-byte big-endian count + that many 6-byte entries (§4.5)."""
    entries: list = field(default_factory=list)

    def encode(self) -> bytes:
        out = bytearray(be16(len(self.entries)))
        for e in self.entries:
            out += e.encode()
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> "ListGetResponse":
        r = Reader(data)
        count = r.be16()
        entries = [ListEntry.decode(r.take(LIST_ENTRY_LEN)) for _ in range(count)]
        r.expect_end()
        return cls(entries)
