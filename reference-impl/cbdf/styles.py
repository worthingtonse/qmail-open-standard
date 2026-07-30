"""The Styles section: LayoutID + twelve GS-separated style sub-tables (§4.4).

This is a *structural* codec: it frames the section, the 2-byte LayoutID, and each
sub-table's header byte (tier + count) and its packed fixed-size records, treating each
record's interior as opaque bytes. That is enough to round-trip any well-formed Styles
section (and to reject malformed framing) without yet hand-encoding all twelve record
field layouts of §4.4.3 — those field-level encoders are the next layer up.

Not yet implemented (see reference-impl/README.md): the optional page-background record
(§4.4.5) and per-field record encoders/decoders (§4.4.3).
"""
from ._io import u16, u32, CBDFError, Reader
from .constants import GS, FS, SUBTABLE_ORDER, SUBTABLE_COUNT, TIER_RESERVED


def _record_size(table_index: int, tier: int) -> int:
    name, sizes = SUBTABLE_ORDER[table_index]
    if sizes is None:
        raise CBDFError(f"sub-table '{name}' is reserved for Phase III and carries "
                        f"no records in v1")
    if not 0 <= tier <= 2:
        raise CBDFError(f"tier {tier} is reserved; reject in Phase II (§4.4.1)")
    return sizes[tier]


class SubTable:
    """One style sub-table: a shared tier plus 0-63 packed records of that tier's size.

    Records are stored as raw bytes, each exactly `record_size(tier)` long. An empty
    sub-table encodes as nothing (its preceding GS stands alone), matching the canonical
    14-byte minimum Styles section of GS x 12.
    """

    def __init__(self, table_index: int, tier: int = 0, records=None):
        self.table_index = table_index
        self.tier = tier
        self.records = list(records) if records else []
        for rec in self.records:
            self._check_record(rec)

    def _check_record(self, rec: bytes) -> None:
        size = _record_size(self.table_index, self.tier)
        if len(rec) != size:
            name = SUBTABLE_ORDER[self.table_index][0]
            raise CBDFError(f"sub-table '{name}' tier {self.tier} record must be "
                            f"{size} bytes, got {len(rec)}")

    @classmethod
    def of(cls, records) -> "SubTable":
        """Build a sub-table from typed record objects (see `records.py`).

        Infers the sub-table index from the record class and the shared tier from the
        records themselves (all records in a sub-table share one tier, §4.4.1).
        """
        records = list(records)
        if not records:
            raise CBDFError("SubTable.of needs at least one record; use SubTable(index) "
                            "for an empty table")
        index = type(records[0]).TABLE_INDEX
        tiers = {getattr(r, "tier", 0) for r in records}
        if len(tiers) != 1:
            raise CBDFError("all records in a sub-table must share one tier (§4.4.1)")
        if any(type(r).TABLE_INDEX != index for r in records):
            raise CBDFError("all records in a sub-table must be the same record type")
        return cls(index, tiers.pop(), [r.pack() for r in records])

    def typed(self):
        """Decode this sub-table's raw records into typed record objects (§4.4.3)."""
        from .records import decode_record
        return [decode_record(self.table_index, rec) for rec in self.records]

    @property
    def is_empty(self) -> bool:
        return not self.records

    def encode(self) -> bytes:
        if self.is_empty:
            return b""  # bare GS (emitted by StylesSection) represents an empty table
        if len(self.records) > 63:
            raise CBDFError("a sub-table holds at most 63 records (§4.4.1)")
        header = (self.tier & 0x03) | (len(self.records) << 2)
        return bytes([header]) + b"".join(self.records)


class StylesSection:
    """LayoutID + twelve sub-tables in fixed order (§4.4.2)."""

    def __init__(self, layout_id: int = 0x0000, sub_tables=None, page_background: bytes = b""):
        if not 0 <= layout_id <= 0xFFFF:
            raise CBDFError(f"LayoutID out of range: {layout_id}")
        self.layout_id = layout_id
        self.page_background = bytes(page_background)
        if sub_tables is None:
            self.sub_tables = [SubTable(i) for i in range(SUBTABLE_COUNT)]
        else:
            if len(sub_tables) != SUBTABLE_COUNT:
                raise CBDFError(f"expected {SUBTABLE_COUNT} sub-tables, "
                                f"got {len(sub_tables)}")
            self.sub_tables = list(sub_tables)

    @classmethod
    def minimal(cls, layout_id: int = 0x0000) -> "StylesSection":
        """The 14-byte minimum: LayoutID + GS x 12 empty sub-tables (§4.4)."""
        return cls(layout_id)

    def encode(self) -> bytes:
        if self.page_background:
            # A page-background record has no self-describing size on the wire, so we
            # only pass through bytes the caller already framed; decode is not yet
            # supported (see module docstring / README).
            body = u16(self.layout_id) + self.page_background
        else:
            body = u16(self.layout_id)
        for st in self.sub_tables:
            body += bytes([GS]) + st.encode()
        return body

    def encode_section(self) -> bytes:
        """The Styles section as it appears after its FS: [Len:4 LE][payload]."""
        payload = self.encode()
        return u32(len(payload)) + payload

    @classmethod
    def decode(cls, payload: bytes) -> "StylesSection":
        r = Reader(bytes(payload))
        layout_id = r.u16()
        # Page background (§4.4.5): present iff the next byte is not GS. Decoding it needs
        # a record size we cannot yet infer, so only the "no page background" form parses.
        if not r.at_end() and r.peek() != GS:
            raise CBDFError("page-background record decoding not yet implemented "
                            "(§4.4.5); next byte after LayoutID is not GS")
        sub_tables = []
        for i in range(SUBTABLE_COUNT):
            r.expect(GS, f"GS before sub-table {i + 1}")
            sub_tables.append(cls._decode_subtable(r, i))
        if not r.at_end():
            raise CBDFError(f"trailing bytes after 12 sub-tables at offset {r.pos}")
        return cls(layout_id, sub_tables)

    @staticmethod
    def _decode_subtable(r: Reader, table_index: int) -> SubTable:
        # Empty sub-table: the GS we just consumed stands alone (next is GS or end).
        if r.at_end() or r.peek() in (GS, FS):
            return SubTable(table_index)
        header = r.byte()
        tier = header & 0x03
        count = header >> 2
        if tier == TIER_RESERVED:
            raise CBDFError("sub-table tier 3 is reserved; reject in Phase II (§4.4.1)")
        if count == 0:
            return SubTable(table_index, tier)  # header with count 0 == empty (§4.4.1)
        size = _record_size(table_index, tier)
        records = [r.take(size) for _ in range(count)]
        return SubTable(table_index, tier, records)
