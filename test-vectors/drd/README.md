# DRD/1.0 test vectors

Byte-accurate conformance vectors for [`../../specs/drd-1.0.md`](../../specs/drd-1.0.md)
(RAIDA Group 16). All values are **big-endian**; request bodies end with the `3E 3E`
trailer. The base RAIDA packet header and encryption envelope are out of scope (supplied
by the RAIDA protocol layer) — these vectors cover the command **body** and record
formats.

Same format as the CBDF set: JSON, one object per vector, with `bytes_hex` and an
`annotated` byte-by-byte breakdown (or purpose-specific fields for tables).

| File | Exercises |
|----|----|
| `01-fee-encoding.json` | Inbox fee → 8-byte BE signed int64 (1e-8 CC units); incl. the spec example and the rejected negative case (§4.3) |
| `02-challenge.json` | 16-byte request challenge = 12 random + BE CRC32 (§4.2) |
| `03-get-user.json` | `get_user` request (23 B) + a user-record response (34 + names, §4.4.1) |
| `04-post-user.json` | `post_user` request: minimal (52 B, empty names) and named (62 B) (§4.5 cmd 140) |
| `05-list-set-remove.json` | `list_set` (6-byte entries) and `list_remove` (5-byte entries), 2-entry batches (§4.5) |
| `06-list-get.json` | `list_get` response: 2-byte BE count + 6-byte entries, and the empty list (§4.5 cmd 146) |
| `07-class-rejection.json` | Signed class-rejection decision table (`0x00`/`0x01`/`0x02`/`0xFF`/`0xF8` × sender denominations) (§4.3) |

## Regenerating

[`generate.py`](generate.py) is a small reference encoder with `assert`s pinning every
non-trivial value (the fee example `000000fff2fe1c88`, the 23-byte `get_user` and 52-byte
minimal `post_user` lengths, the `39+6N`/`39+5N` batch lengths, and the signed
class-rejection logic). Running it is a conformance smoke test:

```
python3 generate.py      # rewrites vectors/*.json; non-zero exit if any check fails
```

The committed `vectors/*.json` are the authoritative artifacts; edit `generate.py`, not
the JSON.

## Not yet covered (next passes)

The AN-authentication path (matching against a stored AN), `search_users` request/
response, multi-page `list_get` at the 1000-entry cap, and negative-path status codes
beyond the class-rejection table.
