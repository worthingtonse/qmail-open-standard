#!/usr/bin/env python3
"""
DRD/1.0 (RAIDA Group 16) conformance test-vector generator.

Builds the vectors described in specs/drd-1.0.md §8, byte-accurate, into
test-vectors/drd/vectors/*.json. The builders are a small reference encoder; the
asserts pin every non-trivial value, so running this script is a conformance smoke test.

DRD is BIG-ENDIAN throughout (RAIDA wire). Request bodies end with the 3E 3E trailer.
The RAIDA packet header and encryption envelope are out of scope (RAIDA protocol layer).

Usage:  python3 generate.py
"""
import json, os, struct, zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")
TERM = bytes([0x3E, 0x3E])

# Fixed, reproducible sample values (arbitrary; only determinism matters).
CH_RANDOM = bytes(range(12))                 # 00 01 02 ... 0B  ("random" part of challenge)
AN = bytes([0xA0 + (i & 0x0F) for i in range(16)])   # 16-byte sample Authenticity Number
CREATED_AT = 1700000000
UPDATED_AT = 1785312000

def s8(v):  return struct.pack("b", v)       # signed int8 (denomination, class rejection)
def be16(v): return struct.pack(">H", v)
def be32(v): return struct.pack(">I", v)
def be64s(v): return struct.pack(">q", v)    # signed int64 (fee)
def hx(b): return " ".join(f"{x:02X}" for x in b)

def challenge():
    """16-byte challenge: 12 random bytes + big-endian CRC32 of them (§4.2)."""
    crc = zlib.crc32(CH_RANDOM) & 0xFFFFFFFF
    return CH_RANDOM + be32(crc)

def cc_to_units(cc_str):
    """Decimal CloudCoin string -> signed int64 count of 1e-8 CC units, exactly (no float)."""
    neg = cc_str.startswith("-")
    s = cc_str.lstrip("-")
    whole, _, frac = s.partition(".")
    frac = (frac + "00000000")[:8]           # pad/truncate to 8 fractional digits
    units = int(whole) * 100_000_000 + int(frac)
    return -units if neg else units

def write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote vectors/{name}")

def user_record(dn, sn, fee_units, s1, s2, cr, created, updated, first, last):
    """DRD user record (§4.4.1): 34 + FL + LL bytes, big-endian."""
    fb = first.encode("utf-8"); lb = last.encode("utf-8")
    assert len(fb) <= 63 and len(lb) <= 63
    return (s8(dn) + be32(sn) + be64s(fee_units) + bytes([s1, s2]) + s8(cr)
            + be64s(created) + be64s(updated)
            + bytes([len(fb)]) + fb + bytes([len(lb)]) + lb)

# ======================================================================================
# 1. Inbox fee encoding (§4.3)
# ======================================================================================
def v_fee():
    cases = []
    for cc in ["10992.934002", "0.00000001", "0", "10"]:
        u = cc_to_units(cc)
        cases.append({"cc": cc, "units": u, "be_int64_hex": hx(be64s(u))})
    # Spec-documented example must match exactly.
    assert be64s(cc_to_units("10992.934002")).hex() == "000000fff2fe1c88"
    assert be64s(cc_to_units("0.00000001")).hex() == "0000000000000001"
    assert be64s(0).hex() == "0000000000000000"
    write("01-fee-encoding.json", {
        "vector": "fee-encoding",
        "spec_ref": "DRD/1.0 §4.3",
        "description": "Inbox fee = 8-byte big-endian signed int64 counting 1e-8 CC units "
                       "(fee_CC x 100,000,000). No floating point. Negative fees are rejected "
                       "with ERROR_INVALID_PARAMETER (198).",
        "encoding": "big-endian",
        "cases": cases,
        "rejected": {"cc": "-1", "reason": "negative fee", "status": "198 ERROR_INVALID_PARAMETER"},
    })

# ======================================================================================
# 2. Challenge (§4.2)
# ======================================================================================
def v_challenge():
    ch = challenge()
    crc = zlib.crc32(CH_RANDOM) & 0xFFFFFFFF
    write("02-challenge.json", {
        "vector": "challenge",
        "spec_ref": "DRD/1.0 §4.2",
        "description": "16-byte request challenge: 12 client-random bytes followed by their "
                       "4-byte big-endian CRC32. Provides per-request freshness/integrity.",
        "encoding": "big-endian",
        "random_12_hex": hx(CH_RANDOM),
        "crc32": f"0x{crc:08X}",
        "length_bytes": len(ch),
        "bytes_hex": ch.hex(),
        "annotated": [
            {"hex": hx(CH_RANDOM), "field": "12 random bytes (fixed sample 00..0B)"},
            {"hex": hx(be32(crc)), "field": f"CRC32 of the 12 random bytes, big-endian (0x{crc:08X})"},
        ],
    })

# ======================================================================================
# 3. get_user request (23 B) + user record response (§4.5, §4.4.1)
# ======================================================================================
def v_get_user():
    dn, sn = 0, 42
    req = challenge() + s8(dn) + be32(sn) + TERM
    assert len(req) == 23, len(req)
    rec = user_record(dn, sn, cc_to_units("10"), 5, 17, 0, CREATED_AT, UPDATED_AT, "Alice", "Smith")
    assert len(rec) == 34 + 5 + 5, len(rec)
    write("03-get-user.json", {
        "vector": "get-user",
        "spec_ref": "DRD/1.0 §4.5 (cmd 141), §4.4.1",
        "description": "get_user request (exactly 23 bytes, no auth) fetching DN=0 SN=42, and "
                       "the success user-record response (34 + name bytes) for Alice Smith: "
                       "fee 10 CC, symbols 5/17, class-rejection 0 (accept all).",
        "encoding": "big-endian",
        "request": {
            "length_bytes": len(req),
            "bytes_hex": req.hex(),
            "annotated": [
                {"hex": hx(challenge()), "field": "challenge (12 random + BE CRC32)"},
                {"hex": "00", "field": "Denomination = 0 (signed; 1 CC / .bit)"},
                {"hex": hx(be32(sn)), "field": "Serial Number = 42 (BE)"},
                {"hex": hx(TERM), "field": "terminator 3E 3E"},
            ],
        },
        "response_user_record": {
            "length_bytes": len(rec),
            "bytes_hex": rec.hex(),
            "annotated": [
                {"hex": "00", "field": "DN = 0"},
                {"hex": hx(be32(sn)), "field": "SN = 42 (BE)"},
                {"hex": hx(be64s(cc_to_units("10"))), "field": "inbox fee = 10 CC (BE int64, 1e-8 units)"},
                {"hex": "05", "field": "first symbol = 5"},
                {"hex": "11", "field": "second symbol = 17"},
                {"hex": "00", "field": "class rejection = 0 (accept all)"},
                {"hex": hx(be64s(CREATED_AT)), "field": f"created_at = {CREATED_AT} (BE Unix seconds)"},
                {"hex": hx(be64s(UPDATED_AT)), "field": f"updated_at = {UPDATED_AT} (BE Unix seconds)"},
                {"hex": "05", "field": "first-name length = 5"},
                {"hex": hx(b"Alice"), "field": '"Alice"'},
                {"hex": "05", "field": "last-name length = 5"},
                {"hex": hx(b"Smith"), "field": '"Smith"'},
            ],
        },
    })

# ======================================================================================
# 4. post_user request — minimal (52 B) and named (62 B) (§4.5 cmd 140)
# ======================================================================================
def post_user(dn, sn, fee_units, s1, s2, cr, first, last):
    fb = first.encode(); lb = last.encode()
    return (challenge() + s8(dn) + be32(sn) + AN + be64s(fee_units) + bytes([s1, s2]) + s8(cr)
            + bytes([len(fb)]) + fb + bytes([len(lb)]) + lb + TERM)

def v_post_user():
    minimal = post_user(0, 42, 0, 0, 0, 0, "", "")
    named = post_user(0, 42, cc_to_units("10"), 5, 17, 0, "Alice", "Smith")
    assert len(minimal) == 52, len(minimal)
    assert len(named) == 62, len(named)
    write("04-post-user.json", {
        "vector": "post-user",
        "spec_ref": "DRD/1.0 §4.5 (cmd 140)",
        "description": "post_user request bodies (Owner AN). Minimal = both names empty (52 "
                       "bytes, the documented minimum); named = Alice Smith, fee 10 CC (62 bytes). "
                       "Upsert keyed by PQ; created_at is preserved by the server across updates.",
        "encoding": "big-endian",
        "minimal_empty_names": {"length_bytes": len(minimal), "bytes_hex": minimal.hex()},
        "named_example": {
            "length_bytes": len(named),
            "bytes_hex": named.hex(),
            "annotated": [
                {"hex": hx(challenge()), "field": "challenge (16)"},
                {"hex": "00", "field": "DN = 0"},
                {"hex": hx(be32(42)), "field": "SN = 42 (BE)"},
                {"hex": hx(AN), "field": "owner AN (16)"},
                {"hex": hx(be64s(cc_to_units("10"))), "field": "inbox fee = 10 CC"},
                {"hex": "05 11", "field": "symbols S1=5 S2=17"},
                {"hex": "00", "field": "class rejection = 0"},
                {"hex": "05", "field": "FL = 5"}, {"hex": hx(b"Alice"), "field": '"Alice"'},
                {"hex": "05", "field": "LL = 5"}, {"hex": hx(b"Smith"), "field": '"Smith"'},
                {"hex": hx(TERM), "field": "terminator 3E 3E"},
            ],
        },
    })

# ======================================================================================
# 5. list_set (6-byte entries) and list_remove (5-byte entries) (§4.5 cmd 144/145)
# ======================================================================================
def v_list_set_remove():
    owner_dn, owner_sn = 0, 42
    # two listed users: (denom 0, sn 100, whitelist) and (denom 1, sn 200, blacklist)
    entries_set = s8(0) + be32(100) + bytes([0x00]) + s8(1) + be32(200) + bytes([0x01])
    set_body = challenge() + s8(owner_dn) + be32(owner_sn) + AN + entries_set + TERM
    entries_rm = s8(0) + be32(100) + s8(1) + be32(200)     # no type byte
    rm_body = challenge() + s8(owner_dn) + be32(owner_sn) + AN + entries_rm + TERM
    assert len(set_body) == 39 + 6 * 2, len(set_body)      # 51
    assert len(rm_body) == 39 + 5 * 2, len(rm_body)        # 49
    write("05-list-set-remove.json", {
        "vector": "list-set-remove",
        "spec_ref": "DRD/1.0 §4.5 (cmd 144 list_set, cmd 145 list_remove), §4.4.2",
        "description": "Two-entry batches. list_set entries are 6 bytes (LDN, LSN BE, type); "
                       "list_remove entries are 5 bytes (no type). The entry region must be an "
                       "exact multiple of 6 / 5 bytes respectively (else ERROR_COINS_NOT_DIV 39).",
        "encoding": "big-endian",
        "list_set": {
            "length_bytes": len(set_body), "formula": "39 + 6N (N=2)", "bytes_hex": set_body.hex(),
            "entries": [
                {"listed_dn": 0, "listed_sn": 100, "type": "0x00 whitelist"},
                {"listed_dn": 1, "listed_sn": 200, "type": "0x01 blacklist"},
            ],
        },
        "list_remove": {
            "length_bytes": len(rm_body), "formula": "39 + 5N (N=2)", "bytes_hex": rm_body.hex(),
            "entries": [{"listed_dn": 0, "listed_sn": 100}, {"listed_dn": 1, "listed_sn": 200}],
        },
    })

# ======================================================================================
# 6. list_get response — count(2 BE) + 6-byte entries; and the empty list (§4.5 cmd 146)
# ======================================================================================
def v_list_get():
    entries = s8(0) + be32(100) + bytes([0x00]) + s8(1) + be32(200) + bytes([0x01])
    resp = be16(2) + entries
    empty = be16(0)
    assert len(resp) == 2 + 6 * 2, len(resp)
    write("06-list-get.json", {
        "vector": "list-get",
        "spec_ref": "DRD/1.0 §4.5 (cmd 146), §4.4.2",
        "description": "list_get success payload: 2-byte big-endian entry count followed by that "
                       "many 6-byte entries (LDN, LSN BE, type), sorted by listed DN then SN. "
                       "The count is 2 bytes because a list may hold up to 1000 entries. Empty "
                       "list = count 0 with status 250.",
        "encoding": "big-endian",
        "response_two_entries": {
            "length_bytes": len(resp), "bytes_hex": resp.hex(),
            "annotated": [
                {"hex": hx(be16(2)), "field": "entry count = 2 (BE)"},
                {"hex": hx(s8(0) + be32(100) + bytes([0])), "field": "entry: DN 0, SN 100, whitelist"},
                {"hex": hx(s8(1) + be32(200) + bytes([1])), "field": "entry: DN 1, SN 200, blacklist"},
            ],
        },
        "response_empty": {"length_bytes": len(empty), "bytes_hex": empty.hex(),
                           "note": "count 0; status 250 (list exists but is empty)"},
    })

# ======================================================================================
# 7. Class-rejection signed comparison (§4.3)
# ======================================================================================
def v_class_rejection():
    def rejects(cr_byte, sender_dn):
        cr = struct.unpack("b", bytes([cr_byte]))[0]   # signed
        if cr == 0:
            return False                                # 0x00 = accept all
        return sender_dn < cr                           # signed comparison
    senders = [-8, -1, 0, 1, 2, 6]
    table = []
    for cr_hex in [0x00, 0x01, 0x02, 0xFF, 0xF8]:
        cr = struct.unpack("b", bytes([cr_hex]))[0]
        row = {"class_rejection_byte": f"0x{cr_hex:02X}", "class_rejection_signed": cr,
               "results": {str(dn): ("REJECT" if rejects(cr_hex, dn) else "accept") for dn in senders}}
        table.append(row)
    # sanity: CR=0x01 accepts denom>=1, rejects below; CR=0x00 accepts everyone
    assert rejects(0x01, 0) is True and rejects(0x01, 1) is False
    assert rejects(0x00, -8) is False
    assert rejects(0xFF, -1) is False and rejects(0xFF, -8) is True   # 0xFF = -1
    write("07-class-rejection.json", {
        "vector": "class-rejection",
        "spec_ref": "DRD/1.0 §4.3 (enforced at the QMail/1.0 Tell gate -> 237)",
        "description": "Class-rejection is a SIGNED denomination byte: 0x00 = accept all "
                       "(default), otherwise reject senders whose address denomination is below "
                       "it by signed comparison (0xFF = -1 ranks BELOW 0x00 = 0). Sender columns "
                       "are address denominations -8..+6.",
        "sender_denominations": senders,
        "table": table,
    })

def main():
    print("Generating DRD/1.0 test vectors ->", OUT)
    v_fee()
    v_challenge()
    v_get_user()
    v_post_user()
    v_list_set_remove()
    v_list_get()
    v_class_rejection()
    print("All vectors generated and self-checks passed.")

if __name__ == "__main__":
    main()
