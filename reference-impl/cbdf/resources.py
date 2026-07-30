"""The Resources section: packed binary blobs, walked by length (§4.8).

Records are packed with no count field and no separators:
    [Resource ID:1][Type:1][Data Length:4 LE][Raw Data:N]
The parser walks records until the section length is exhausted. Resource IDs are unique
within a document (0-255).
"""
from ._io import u32, CBDFError, Reader


class Resource:
    __slots__ = ("res_id", "res_type", "data")

    def __init__(self, res_id: int, res_type: int, data: bytes):
        if not 0 <= res_id <= 255:
            raise CBDFError(f"resource id out of range: {res_id}")
        if not 0 <= res_type <= 255:
            raise CBDFError(f"resource type out of range: {res_type}")
        self.res_id = res_id
        self.res_type = res_type
        self.data = bytes(data)

    def encode(self) -> bytes:
        return bytes([self.res_id, self.res_type]) + u32(len(self.data)) + self.data


def encode(resources) -> bytes:
    """Encode the Resources payload (the records only, no length prefix)."""
    seen = set()
    out = bytearray()
    for res in resources:
        if res.res_id in seen:
            raise CBDFError(f"duplicate resource id {res.res_id} (must be unique, §4.8)")
        seen.add(res.res_id)
        out += res.encode()
    return bytes(out)


def encode_section(resources) -> bytes:
    """The Resources section as it appears after its FS: [Len:4 LE][records...]."""
    payload = encode(resources)
    return u32(len(payload)) + payload


def decode(payload: bytes):
    """Parse a Resources payload into a list of Resource, walking by length."""
    r = Reader(bytes(payload))
    out = []
    seen = set()
    while not r.at_end():
        res_id = r.byte()
        res_type = r.byte()
        length = r.u32()
        data = r.take(length)
        if res_id in seen:
            raise CBDFError(f"duplicate resource id {res_id} (§4.8)")
        seen.add(res_id)
        out.append(Resource(res_id, res_type, data))
    return out
