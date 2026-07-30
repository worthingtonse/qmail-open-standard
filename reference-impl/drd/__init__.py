"""DRD/1.0 (RAIDA Group 16) reference codec — Distributed Resource Directory.

A small, dependency-free implementation of the big-endian DRD command bodies defined in
`specs/drd-1.0.md`: the user directory (post/get/search/delete) and the private
white/black lists (set/remove/get). This package encodes/decodes the command **bodies**
and record formats; the RAIDA header, encryption envelope, and status-code transport are
the RAIDA protocol layer's job.

    from drd import GetUserRequest, UserRecord, challenge, fee

    req = GetUserRequest(challenge=challenge(), denomination=0, serial=42)
    wire = req.encode()                      # 23 bytes, big-endian
"""
from . import constants
from . import fee
from ._io import DRDError, TRAILER, challenge, challenge_is_valid
from .records import UserRecord, ListEntry, pq
from .fee import cc_to_units, units_to_cc, encode_fee, class_rejects
from .messages import (
    PostUserRequest, GetUserRequest, SearchUsersRequest, SearchUsersResponse,
    DeleteUserRequest, ListSetRequest, ListRemoveRequest, ListGetRequest, ListGetResponse,
)

__all__ = [
    "constants", "fee", "DRDError", "TRAILER",
    "challenge", "challenge_is_valid",
    "UserRecord", "ListEntry", "pq",
    "cc_to_units", "units_to_cc", "encode_fee", "class_rejects",
    "PostUserRequest", "GetUserRequest", "SearchUsersRequest", "SearchUsersResponse",
    "DeleteUserRequest", "ListSetRequest", "ListRemoveRequest", "ListGetRequest",
    "ListGetResponse",
]

__version__ = "0.1.0"
