"""RKE/1.0 (RAIDA Group 15) reference codec — Raida Key Exchange.

A small, dependency-free implementation of the big-endian RKE command bodies defined in
`specs/rke-1.0.md`. RKE rides the RAIDA protocol wire; this package encodes/decodes only
the command **bodies** (§4.3–§4.4) and the shared coin-authenticated preamble (§4.2).
The RAIDA header and encryption envelope are out of scope (RAIDA protocol layer).

    from rke import Preamble, challenge, PreloadMasterKeyRequest, KeyRecord

    pre = Preamble(challenge=challenge(), an=my_an, denomination=1, serial=42)
    wire = pre.encode()                      # 48 bytes, big-endian
"""
from . import constants
from ._io import RKEError, TRAILER
from .preamble import Preamble, challenge, challenge_is_valid
from .messages import (
    KeyRecord, PreloadMasterKeyRequest, GetKeyShareRequest, GetKeyShareResponse,
    client_sn,
)

__all__ = [
    "constants", "RKEError", "TRAILER",
    "Preamble", "challenge", "challenge_is_valid",
    "KeyRecord", "PreloadMasterKeyRequest", "GetKeyShareRequest", "GetKeyShareResponse",
    "client_sn",
]

__version__ = "0.1.0"
