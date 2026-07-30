#!/usr/bin/env python3
"""Conformance tests: the DRD reference codec against test-vectors/drd/vectors/*.json.

Re-encodes each DRD body/record through the library and asserts byte-equality with the
vector (big-endian, `3E 3E` trailer), then round-trips it. Also checks the pure-value
encodings (fee, class-rejection signed comparison) against their vectors.

Run directly:   python3 tests/test_drd_vectors.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(IMPL_ROOT)
VECTORS = os.path.join(REPO_ROOT, "test-vectors", "drd", "vectors")

sys.path.insert(0, IMPL_ROOT)

import drd

CH_SEED = bytes(range(12))
AN = bytes([0xA0 + (i & 0x0F) for i in range(16)])
CREATED_AT = 1700000000
UPDATED_AT = 1785312000


def load(name):
    with open(os.path.join(VECTORS, name)) as f:
        return json.load(f)


def _hex(name, produced, want_hex):
    got = produced.hex()
    assert got == want_hex, f"{name}: byte mismatch\n  want {want_hex}\n  got  {got}"


def _ch():
    return drd.challenge(CH_SEED)


# --- 01 fee encoding (§4.3) ---------------------------------------------------------
def test_fee_encoding():
    v = load("01-fee-encoding.json")
    for case in v["cases"]:
        assert drd.cc_to_units(case["cc"]) == case["units"], case["cc"]
        got = drd.encode_fee(case["units"]).hex()
        want = case["be_int64_hex"].replace(" ", "").lower()
        assert got == want, f"fee {case['cc']}: {got} != {want}"
    # Negative fee is rejected.
    try:
        drd.encode_fee(drd.cc_to_units("-1"))
        raise AssertionError("expected negative-fee rejection")
    except drd.DRDError:
        pass
    # More than 8 fractional digits is rejected.
    try:
        drd.cc_to_units("1.123456789")
        raise AssertionError("expected >8-fraction rejection")
    except drd.DRDError:
        pass


# --- 02 challenge (§4.2) ------------------------------------------------------------
def test_challenge():
    v = load("02-challenge.json")
    ch = _ch()
    _hex("challenge", ch, v["bytes_hex"])
    assert drd.challenge_is_valid(ch)
    assert not drd.challenge_is_valid(ch[:15] + bytes([ch[15] ^ 0xFF]))


# --- 03 get_user request + user record response (§4.5/§4.4.1) -----------------------
def test_get_user():
    v = load("03-get-user.json")
    req = drd.GetUserRequest(challenge=_ch(), denomination=0, serial=42)
    wire = req.encode()
    _hex("get_user req", wire, v["request"]["bytes_hex"])
    assert len(wire) == 23
    back = drd.GetUserRequest.decode(wire)
    assert back.denomination == 0 and back.serial == 42

    rec = drd.UserRecord(denomination=0, serial=42, fee_units=drd.cc_to_units("10"),
                         symbol1=5, symbol2=17, class_rejection=0,
                         created_at=CREATED_AT, updated_at=UPDATED_AT,
                         first_name="Alice", last_name="Smith")
    rec_bytes = rec.encode()
    _hex("user record", rec_bytes, v["response_user_record"]["bytes_hex"])
    back_rec = drd.UserRecord.decode(rec_bytes)
    assert back_rec == rec


# --- 04 post_user request (§4.5 cmd 140) --------------------------------------------
def test_post_user():
    v = load("04-post-user.json")
    minimal = drd.PostUserRequest(challenge=_ch(), denomination=0, serial=42, an=AN)
    _hex("post_user minimal", minimal.encode(), v["minimal_empty_names"]["bytes_hex"])
    assert len(minimal.encode()) == 52

    named = drd.PostUserRequest(challenge=_ch(), denomination=0, serial=42, an=AN,
                                fee_units=drd.cc_to_units("10"), symbol1=5, symbol2=17,
                                class_rejection=0, first_name="Alice", last_name="Smith")
    nbytes = named.encode()
    _hex("post_user named", nbytes, v["named_example"]["bytes_hex"])
    assert len(nbytes) == 62
    assert drd.PostUserRequest.decode(nbytes) == named


# --- 05 list_set / list_remove (§4.5 cmd 144/145) -----------------------------------
def test_list_set_remove():
    v = load("05-list-set-remove.json")
    entries = [drd.ListEntry(0, 100, drd.constants.LIST_WHITELIST),
               drd.ListEntry(1, 200, drd.constants.LIST_BLACKLIST)]
    set_req = drd.ListSetRequest(challenge=_ch(), denomination=0, serial=42, an=AN,
                                 entries=entries)
    _hex("list_set", set_req.encode(), v["list_set"]["bytes_hex"])
    assert drd.ListSetRequest.decode(set_req.encode()).entries == entries

    rm_req = drd.ListRemoveRequest(challenge=_ch(), denomination=0, serial=42, an=AN,
                                   entries=[drd.ListEntry(0, 100), drd.ListEntry(1, 200)])
    _hex("list_remove", rm_req.encode(), v["list_remove"]["bytes_hex"])
    back = drd.ListRemoveRequest.decode(rm_req.encode())
    assert [(e.listed_dn, e.listed_sn) for e in back.entries] == [(0, 100), (1, 200)]

    # A misaligned entry region is rejected (ERROR_COINS_NOT_DIV): insert one stray
    # byte before the trailer so the region is 13 bytes (not a multiple of 6).
    good = set_req.encode()
    bad = good[:-2] + b"\x99" + good[-2:]
    try:
        drd.ListSetRequest.decode(bad)
        raise AssertionError("expected COINS_NOT_DIV rejection")
    except drd.DRDError:
        pass


# --- 06 list_get response (§4.5 cmd 146) --------------------------------------------
def test_list_get_response():
    v = load("06-list-get.json")
    resp = drd.ListGetResponse([drd.ListEntry(0, 100, 0), drd.ListEntry(1, 200, 1)])
    _hex("list_get resp", resp.encode(), v["response_two_entries"]["bytes_hex"])
    back = drd.ListGetResponse.decode(resp.encode())
    assert len(back.entries) == 2 and back.entries[1].list_type == 1

    empty = drd.ListGetResponse([])
    _hex("list_get empty", empty.encode(), v["response_empty"]["bytes_hex"])
    assert drd.ListGetResponse.decode(empty.encode()).entries == []


# --- 07 class-rejection signed comparison (§4.3) ------------------------------------
def test_class_rejection():
    v = load("07-class-rejection.json")
    for row in v["table"]:
        cr = row["class_rejection_signed"]
        for dn_str, expected in row["results"].items():
            got = "REJECT" if drd.class_rejects(cr, int(dn_str)) else "accept"
            assert got == expected, f"CR={cr} sender={dn_str}: {got} != {expected}"


ALL_TESTS = [
    test_fee_encoding,
    test_challenge,
    test_get_user,
    test_post_user,
    test_list_set_remove,
    test_list_get_response,
    test_class_rejection,
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
    print(f"\n{total - failures}/{total} DRD conformance checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
