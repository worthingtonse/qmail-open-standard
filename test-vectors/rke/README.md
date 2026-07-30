# RKE/1.0 test vectors

Byte-accurate conformance vectors for [`../../specs/rke-1.0.md`](../../specs/rke-1.0.md)
(RAIDA Group 15). All values are **big-endian**; request bodies end with the `3E 3E`
trailer. The base RAIDA packet header and encryption envelope (Type 0/1, and +5 for
`get_key_share`) are out of scope — these cover the command **body**.

Same format as the CBDF/DRD sets: JSON, one object per vector, `bytes_hex` + `annotated`
breakdown.

| File | Exercises |
|----|----|
| `01-preamble.json` | The 48-byte coin-authenticated preamble (shared with QMail); CT/DN/SN/AN + the reserved "DV" byte (§4.2) |
| `02-preload-master-key.json` | `preload_master_key` (cmd 01): CSID length + CSID + NS + `[KID][32-byte secret]` record + trailer (§4.3) |
| `03-get-key-share.json` | `get_key_share` (cmd 02): 46-byte request (+trailer) and the 1-byte-share response (§4.4) |

## Cross-check with QMail

`01-preamble.json` is the same 48-byte structure as the QMail shared preamble
([QMail/1.0] §4.3). The challenge here (12 random `00..0B` + big-endian CRC32 `9270C965`)
is built the same way, so the QMail preamble vector must reproduce these bytes given the
same coin identity — an intentional interop anchor between the two specs.

## Flagged (faithful to source gaps)

The source leaves several things unspecified; the vectors encode a documented choice and
label it, rather than inventing certainty:

- The **preamble discrepancy** (§4.2): the two command bodies do not both use the 48-byte
  preamble — `preload_master_key` leads with a length-prefixed CSID; `get_key_share` uses
  a different 46-byte layout. The preamble vector notes this.
- **NS** (number of key records) in `preload_master_key` is an inferred field name.
- The `get_key_share` **16-byte challenge** internal split and the **5-byte Client SN**
  interpretation (encoded here as the 5-byte PQ = denom + serial) are not fully specified.

The **share threshold / reconstruction rule** (how many `get_key_share` shares rebuild
the master key) is not in the source and is not yet a vector — it must be specified before
1.0 (RKE/1.0 §5).

## Regenerating

[`generate.py`](generate.py) is a small reference encoder with `assert`s pinning the
48-byte preamble, the preload record framing, and the 48-byte `get_key_share` request.
Running it is a conformance smoke test:

```
python3 generate.py      # rewrites vectors/*.json; non-zero exit if any check fails
```

The committed `vectors/*.json` are authoritative; edit `generate.py`, not the JSON.
