"""The 48-byte coin-authenticated preamble and the RAIDA challenge (§4.2).

The preamble identifies the coin used for an operation (CT ‖ DN ‖ SN — the same 7-byte
coin identity as a CBDF mailbox, but with a big-endian serial) and provides replay
protection via a per-request challenge. This is the shared QMail/RKE preamble; the QMail
reference package asserts its preamble vector is byte-equal to RKE's.
"""
import os
import zlib
from dataclasses import dataclass, field

from ._io import be16, be32, s8, Reader, RKEError
from .constants import (
    PREAMBLE_LEN, CHALLENGE_LEN, SESSION_ID_LEN, AN_LEN, CLOUDCOIN_COIN_TYPE,
)


def challenge(random12: bytes = None) -> bytes:
    """A 16-byte challenge: 12 random bytes followed by their big-endian CRC32.

    The trailing CRC32 lets a receiver detect a corrupted/forged challenge cheaply.
    Pass `random12` for deterministic output (tests/vectors); otherwise it is random.
    """
    if random12 is None:
        random12 = os.urandom(12)
    random12 = bytes(random12)
    if len(random12) != 12:
        raise RKEError(f"challenge seed must be 12 bytes, got {len(random12)}")
    return random12 + be32(zlib.crc32(random12) & 0xFFFFFFFF)


def challenge_is_valid(chal: bytes) -> bool:
    """True iff `chal` is 16 bytes whose last 4 are the BE CRC32 of the first 12."""
    if len(chal) != CHALLENGE_LEN:
        return False
    return chal[12:16] == be32(zlib.crc32(chal[:12]) & 0xFFFFFFFF)


@dataclass
class Preamble:
    challenge: bytes                       # 16 bytes (see challenge())
    an: bytes                              # 16-byte Authenticity Number
    denomination: int = 0                  # signed int8
    serial: int = 0                        # u32 (big-endian on the wire)
    coin_type: int = CLOUDCOIN_COIN_TYPE   # 2 bytes, CloudCoin = 0x0006
    session_id: bytes = field(default_factory=lambda: b"\x00" * SESSION_ID_LEN)
    reserved: int = 0                      # byte 31: reserved / former Device ID; set 0

    def encode(self) -> bytes:
        if len(self.challenge) != CHALLENGE_LEN:
            raise RKEError(f"challenge must be {CHALLENGE_LEN} bytes")
        if len(self.an) != AN_LEN:
            raise RKEError(f"AN must be {AN_LEN} bytes")
        if len(self.session_id) != SESSION_ID_LEN:
            raise RKEError(f"session id must be {SESSION_ID_LEN} bytes")
        out = (bytes(self.challenge)
               + bytes(self.session_id)
               + be16(self.coin_type)
               + s8(self.denomination)
               + be32(self.serial)
               + bytes([self.reserved & 0xFF])
               + bytes(self.an))
        assert len(out) == PREAMBLE_LEN
        return out

    @property
    def coin_identity(self) -> bytes:
        """The 7-byte CT ‖ DN ‖ SN coin identity (big-endian serial)."""
        return be16(self.coin_type) + s8(self.denomination) + be32(self.serial)

    @classmethod
    def decode(cls, data: bytes) -> "Preamble":
        if len(data) != PREAMBLE_LEN:
            raise RKEError(f"preamble must be {PREAMBLE_LEN} bytes, got {len(data)}")
        r = Reader(data)
        chal = r.take(CHALLENGE_LEN)
        session = r.take(SESSION_ID_LEN)
        coin_type = r.be16()
        denom = r.s8()
        serial = r.be32()
        reserved = r.byte()
        an = r.take(AN_LEN)
        return cls(challenge=chal, an=an, denomination=denom, serial=serial,
                   coin_type=coin_type, session_id=session, reserved=reserved)
