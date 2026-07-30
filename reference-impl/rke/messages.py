"""The two Group 15 command bodies (§4.3–§4.4).

Each request/response body is big-endian and ends with the RAIDA `3E 3E` trailer. The
RAIDA header (command group/code, routing) and the encryption envelope are supplied by
the RAIDA protocol layer and are not part of these bodies.

Where the source is unsettled — the `preload_master_key` NS field, the `get_key_share`
16-byte challenge split, and the 5-byte Client SN interpretation (all flagged in the
spec) — these encoders follow the layout each command's source page specifies literally
and leave the unconfirmed fields as raw bytes rather than inventing structure.
"""
from dataclasses import dataclass, field

from ._io import be32, be64, TRAILER, Reader, RKEError
from .constants import (
    MASTER_SECRET_LEN, GET_KEY_SHARE_CSID_LEN, CLIENT_SN_LEN, CHALLENGE_LEN,
)


# --- §4.3 preload_master_key (code 01) ----------------------------------------------
@dataclass
class KeyRecord:
    """One staged key record: a 1-byte Key ID and a 32-byte master secret."""
    kid: int
    master_secret: bytes

    def encode(self) -> bytes:
        if not 0 <= self.kid <= 255:
            raise RKEError(f"KID out of range: {self.kid}")
        if len(self.master_secret) != MASTER_SECRET_LEN:
            raise RKEError(f"master secret must be {MASTER_SECRET_LEN} bytes, "
                           f"got {len(self.master_secret)}")
        return bytes([self.kid]) + bytes(self.master_secret)


@dataclass
class PreloadMasterKeyRequest:
    """`preload_master_key` request body (§4.3).

    Layout: [CSID Len:4 BE][Content Server ID][NS:1][KeyRecord × NS][3E 3E]. NS is the
    number of key records; the source labels it inferred — confirm before 1.0.
    """
    content_server_id: bytes
    records: list = field(default_factory=list)

    def encode(self) -> bytes:
        csid = bytes(self.content_server_id)
        ns = len(self.records)
        if not 0 <= ns <= 255:
            raise RKEError(f"NS (record count) must fit in one byte, got {ns}")
        body = be32(len(csid)) + csid + bytes([ns])
        for rec in self.records:
            body += rec.encode()
        return body + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "PreloadMasterKeyRequest":
        r = Reader(data)
        csid_len = r.be32()
        csid = r.take(csid_len)
        ns = r.byte()
        records = []
        for _ in range(ns):
            kid = r.byte()
            secret = r.take(MASTER_SECRET_LEN)
            records.append(KeyRecord(kid, secret))
        r.expect_trailer()
        r.expect_end()
        return cls(content_server_id=csid, records=records)


# --- §4.4 get_key_share (code 02) ---------------------------------------------------
def client_sn(denomination: int, serial: int) -> bytes:
    """Build the 5-byte Client SN as denom(1, signed) + serial(4 BE).

    The 5-byte field's exact interpretation is unconfirmed in the source (§4.4); this
    helper follows the vector's reading. Pass raw 5 bytes to GetKeyShareRequest if you
    need a different layout.
    """
    from ._io import s8
    out = s8(denomination) + be32(serial)
    assert len(out) == CLIENT_SN_LEN
    return out


@dataclass
class GetKeyShareRequest:
    """`get_key_share` request body (§4.4): 46 bytes + trailer = 48 bytes total.

    Layout: [Challenge:16][Content Server ID:16][KID:1][Client SN:5][Timestamp:8 BE][3E 3E].
    """
    challenge: bytes
    content_server_id: bytes            # fixed 16 bytes here (variable in preload)
    kid: int
    client_serial: bytes                # 5 raw bytes; see client_sn()
    timestamp: int                      # u64, big-endian

    def encode(self) -> bytes:
        if len(self.challenge) != CHALLENGE_LEN:
            raise RKEError(f"challenge must be {CHALLENGE_LEN} bytes")
        if len(self.content_server_id) != GET_KEY_SHARE_CSID_LEN:
            raise RKEError(f"Content Server ID must be {GET_KEY_SHARE_CSID_LEN} bytes")
        if not 0 <= self.kid <= 255:
            raise RKEError(f"KID out of range: {self.kid}")
        if len(self.client_serial) != CLIENT_SN_LEN:
            raise RKEError(f"Client SN must be {CLIENT_SN_LEN} bytes")
        return (bytes(self.challenge) + bytes(self.content_server_id) + bytes([self.kid])
                + bytes(self.client_serial) + be64(self.timestamp) + TRAILER)

    @classmethod
    def decode(cls, data: bytes) -> "GetKeyShareRequest":
        r = Reader(data)
        chal = r.take(CHALLENGE_LEN)
        csid = r.take(GET_KEY_SHARE_CSID_LEN)
        kid = r.byte()
        csn = r.take(CLIENT_SN_LEN)
        ts = r.be64()
        r.expect_trailer()
        r.expect_end()
        return cls(challenge=chal, content_server_id=csid, kid=kid,
                   client_serial=csn, timestamp=ts)


@dataclass
class GetKeyShareResponse:
    """`get_key_share` response body (§4.4): [SK:1][3E 3E]."""
    key_share: int

    def encode(self) -> bytes:
        if not 0 <= self.key_share <= 255:
            raise RKEError(f"key share out of range: {self.key_share}")
        return bytes([self.key_share]) + TRAILER

    @classmethod
    def decode(cls, data: bytes) -> "GetKeyShareResponse":
        r = Reader(data)
        sk = r.byte()
        r.expect_trailer()
        r.expect_end()
        return cls(key_share=sk)
