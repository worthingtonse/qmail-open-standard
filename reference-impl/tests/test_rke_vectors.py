#!/usr/bin/env python3
"""Conformance tests: the RKE reference codec against test-vectors/rke/vectors/*.json.

Re-encodes each RKE body through the library and asserts it is byte-equal to the
vector's `bytes_hex` (big-endian, RAIDA `3E 3E` trailer), then round-trips it. The RAIDA
header and encryption envelope are out of scope (supplied by the RAIDA protocol layer).

Run directly:   python3 tests/test_rke_vectors.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(IMPL_ROOT)
VECTORS = os.path.join(REPO_ROOT, "test-vectors", "rke", "vectors")

sys.path.insert(0, IMPL_ROOT)

import rke

# Fixtures matching the vector generator's fixed inputs.
CH_SEED = bytes(range(12))                              # 00..0B
AN = bytes([0xA0 + (i & 0x0F) for i in range(16)])      # A0..AF
TIMESTAMP = 1785312000


def load(name):
    with open(os.path.join(VECTORS, name)) as f:
        return json.load(f)


def _assert_hex(name, produced, want_hex):
    got = produced.hex()
    assert got == want_hex, f"{name}: byte mismatch\n  want {want_hex}\n  got  {got}"


def test_preamble():
    v = load("01-preamble.json")
    pre = rke.Preamble(challenge=rke.challenge(CH_SEED), an=AN, denomination=0, serial=42)
    wire = pre.encode()
    _assert_hex("preamble", wire, v["bytes_hex"])
    assert len(wire) == 48
    # Challenge self-checks, and round-trip preserves the coin identity.
    assert rke.challenge_is_valid(pre.challenge)
    back = rke.Preamble.decode(wire)
    assert back.serial == 42 and back.coin_type == 0x0006 and back.reserved == 0
    assert back.coin_identity == pre.coin_identity


def test_preload_master_key():
    v = load("02-preload-master-key.json")
    req = rke.PreloadMasterKeyRequest(
        content_server_id=b"CS01",
        records=[rke.KeyRecord(kid=0x01, master_secret=bytes(range(32)))],
    )
    wire = req.encode()
    _assert_hex("preload", wire, v["bytes_hex"])
    back = rke.PreloadMasterKeyRequest.decode(wire)
    assert back.content_server_id == b"CS01"
    assert len(back.records) == 1 and back.records[0].kid == 1
    assert back.records[0].master_secret == bytes(range(32))


def test_get_key_share():
    v = load("03-get-key-share.json")
    req = rke.GetKeyShareRequest(
        challenge=rke.challenge(CH_SEED),
        content_server_id=b"CONTENT-SERVER01",
        kid=0x01,
        client_serial=rke.client_sn(denomination=0, serial=42),
        timestamp=TIMESTAMP,
    )
    wire = req.encode()
    _assert_hex("get_key_share request", wire, v["request"]["bytes_hex"])
    assert len(wire) == 48
    back = rke.GetKeyShareRequest.decode(wire)
    assert back.kid == 1 and back.timestamp == TIMESTAMP
    assert back.content_server_id == b"CONTENT-SERVER01"

    resp = rke.GetKeyShareResponse(key_share=0x2A)
    rwire = resp.encode()
    _assert_hex("get_key_share response", rwire, v["response"]["bytes_hex"])
    assert rke.GetKeyShareResponse.decode(rwire).key_share == 0x2A


def test_trailer_and_bounds_enforced():
    from rke._io import RKEError
    good = rke.GetKeyShareResponse(0x2A).encode()
    # Corrupt the trailer -> must be rejected.
    bad = good[:-1] + b"\x00"
    try:
        rke.GetKeyShareResponse.decode(bad)
        raise AssertionError("expected trailer rejection")
    except RKEError as e:
        assert "trailer" in str(e).lower()
    # Trailing junk after a valid body -> rejected.
    try:
        rke.GetKeyShareResponse.decode(good + b"\x99")
        raise AssertionError("expected trailing-bytes rejection")
    except RKEError:
        pass


ALL_TESTS = [
    test_preamble,
    test_preload_master_key,
    test_get_key_share,
    test_trailer_and_bounds_enforced,
]


def main():
    failures = 0
    for t in ALL_TESTS:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {t.__name__}\n        {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    total = len(ALL_TESTS)
    print(f"\n{total - failures}/{total} RKE conformance checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
