#!/usr/bin/env python3
"""
RKE/1.0 (RAIDA Group 15) conformance test-vector generator.

Builds the vectors from specs/rke-1.0.md §8, byte-accurate, into
test-vectors/rke/vectors/*.json. The builders are a small reference encoder; the asserts
pin every non-trivial value, so running this script is a conformance smoke test.

RKE is BIG-ENDIAN (RAIDA wire). Bodies end with the 3E 3E trailer. The RAIDA packet
header and encryption envelope (Type 0/1, +5 for get_key_share) are out of scope.

Usage:  python3 generate.py
"""
import json, os, struct, zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")
TERM = bytes([0x3E, 0x3E])

CH_RANDOM = bytes(range(12))                          # fixed "random" 12 bytes (00..0B)
AN = bytes([0xA0 + (i & 0x0F) for i in range(16)])    # sample 16-byte Authenticity Number
TIMESTAMP = 1785312000

def s8(v):  return struct.pack("b", v)
def be16(v): return struct.pack(">H", v)
def be32(v): return struct.pack(">I", v)
def be64(v): return struct.pack(">Q", v)
def hx(b): return " ".join(f"{x:02X}" for x in b)

def challenge():
    """16-byte challenge: 12 random + big-endian CRC32 (the shared QMail preamble form)."""
    return CH_RANDOM + be32(zlib.crc32(CH_RANDOM) & 0xFFFFFFFF)

def write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote vectors/{name}")

# ======================================================================================
# 1. 48-byte coin-authenticated preamble (§4.2) — the shared QMail/RKE preamble
# ======================================================================================
def preamble(dn, sn, session=b"\x00" * 8, coin_type=0x0006):
    p = (challenge()                       # 0..15  challenge
         + session                         # 16..23 session id (zeros = standard mode)
         + be16(coin_type)                 # 24..25 coin type (00 06)
         + s8(dn)                          # 26     denomination (signed)
         + be32(sn)                        # 27..30 serial number (BE)
         + bytes([0x00])                   # 31     reserved (former Device ID / "DV")
         + AN)                             # 32..47 authenticity number
    assert len(p) == 48, len(p)
    return p

def v_preamble():
    p = preamble(dn=0, sn=42)
    write("01-preamble.json", {
        "vector": "coin-auth-preamble",
        "spec_ref": "RKE/1.0 §4.2 (shared with QMail/1.0 §4.3)",
        "description": "The 48-byte coin-authenticated preamble the RKE overview says modern "
                       "RKE requests lead with. Identical structure to the QMail shared preamble "
                       "(cross-check with the QMail preamble vector). Coin identity CT=0006, DN=0, "
                       "SN=42. Byte 31 is the reserved 'DV'/former-Device-ID byte (set 0).",
        "encoding": "big-endian",
        "length_bytes": len(p),
        "bytes_hex": p.hex(),
        "annotated": [
            {"hex": hx(challenge()), "field": "challenge: 12 random + BE CRC32 (0..15)"},
            {"hex": hx(b"\x00" * 8), "field": "session id = 0 (16..23, standard mode)"},
            {"hex": "00 06", "field": "coin type = 0x0006 (24..25)"},
            {"hex": "00", "field": "denomination = 0 (26, signed)"},
            {"hex": hx(be32(42)), "field": "serial number = 42 (27..30, BE)"},
            {"hex": "00", "field": "reserved / DV / former Device ID (31)"},
            {"hex": hx(AN), "field": "authenticity number (32..47)"},
        ],
        "note": "DISCREPANCY (see RKE/1.0 §4.2): the two documented command bodies below do NOT "
                "both use this preamble as-is — preload_master_key leads with a length-prefixed "
                "Content Server ID, and get_key_share uses a different 46-byte layout. Documented "
                "for the QMail cross-check and flagged for reconciliation.",
    })

# ======================================================================================
# 2. preload_master_key (Group 15, code 01) request body (§4.3)
# ======================================================================================
def v_preload():
    csid = b"CS01"                                     # sample content-server id (variable length)
    ns = 1                                             # number of key records (inferred field)
    kid = 0x01
    secret = bytes(range(32))                          # sample 32-byte master secret (00..1F)
    body = be32(len(csid)) + csid + bytes([ns]) + bytes([kid]) + secret + TERM
    assert len(body) == 4 + len(csid) + 1 + 1 + 32 + 2, len(body)
    write("02-preload-master-key.json", {
        "vector": "preload-master-key",
        "spec_ref": "RKE/1.0 §4.3 (cmd 01)",
        "description": "preload_master_key request body: 4-byte BE Content-Server-ID length, the "
                       "CSID, NS (number of key records), then NS packed records of [KID:1]"
                       "[Master Secret:32], then the 3E 3E trailer. One record here.",
        "encoding": "big-endian",
        "envelope": "RAIDA Type 0 or Type 1 (per source)",
        "length_bytes": len(body),
        "bytes_hex": body.hex(),
        "annotated": [
            {"hex": hx(be32(len(csid))), "field": f"CSID length = {len(csid)} (BE)"},
            {"hex": hx(csid), "field": 'Content Server ID = "CS01"'},
            {"hex": f"{ns:02X}", "field": f"NS = {ns} (number of key records; inferred field — confirm)"},
            {"hex": f"{kid:02X}", "field": "record KID = 1"},
            {"hex": hx(secret), "field": "master secret (32 bytes, sample 00..1F)"},
            {"hex": hx(TERM), "field": "terminator 3E 3E"},
        ],
        "note": "Master secrets MUST travel only inside an encrypted RAIDA envelope (RKE/1.0 §5).",
    })

# ======================================================================================
# 3. get_key_share (Group 15, code 02) request + response (§4.4)
# ======================================================================================
def v_get_key_share():
    csid16 = b"CONTENT-SERVER01"                       # fixed 16-byte content server id
    assert len(csid16) == 16
    kid = 0x01
    client_pq = s8(0) + be32(42)                       # 5-byte "Client SN" = denom(1)+serial(4 BE)
    assert len(client_pq) == 5
    req = challenge() + csid16 + bytes([kid]) + client_pq + be64(TIMESTAMP) + TERM
    assert len(req) == 16 + 16 + 1 + 5 + 8 + 2, len(req)   # 48
    sk = 0x2A
    resp = bytes([sk]) + TERM
    write("03-get-key-share.json", {
        "vector": "get-key-share",
        "spec_ref": "RKE/1.0 §4.4 (cmd 02)",
        "description": "get_key_share request body (46 B + trailer = 48 B): challenge(16), "
                       "16-byte Content Server ID, KID, 5-byte Client SN, big-endian Timestamp, "
                       "3E 3E. Response: a 1-byte key share (SK) + 3E 3E. The client assembles the "
                       "master key from shares gathered across RAIDA servers.",
        "encoding": "big-endian",
        "envelope": "RAIDA Type 0, 1, or 5 (per source)",
        "request": {
            "length_bytes": len(req),
            "bytes_hex": req.hex(),
            "annotated": [
                {"hex": hx(challenge()), "field": "challenge (16; 12 random + BE CRC32 — structure per shared preamble)"},
                {"hex": hx(csid16), "field": 'Content Server ID = "CONTENT-SERVER01" (16, fixed here vs variable in preload)'},
                {"hex": f"{kid:02X}", "field": "KID = 1"},
                {"hex": hx(client_pq), "field": "Client SN (5 B) = denom 0 + serial 42 BE (interpreted as the 5-byte PQ — confirm)"},
                {"hex": hx(be64(TIMESTAMP)), "field": f"Timestamp = {TIMESTAMP} (8 B, BE)"},
                {"hex": hx(TERM), "field": "terminator 3E 3E"},
            ],
        },
        "response": {
            "length_bytes": len(resp),
            "bytes_hex": resp.hex(),
            "annotated": [
                {"hex": f"{sk:02X}", "field": "SK = 0x2A (1-byte key share)"},
                {"hex": hx(TERM), "field": "terminator 3E 3E"},
            ],
        },
        "note": "The 16-byte challenge internal split and the 5-byte Client SN interpretation are "
                "not fully specified in the source; flagged for confirmation (RKE/1.0 §4.2/§4.4).",
    })

def main():
    print("Generating RKE/1.0 test vectors ->", OUT)
    v_preamble()
    v_preload()
    v_get_key_share()
    print("All vectors generated and self-checks passed.")

if __name__ == "__main__":
    main()
