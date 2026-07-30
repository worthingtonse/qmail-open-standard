# QMail/1.0 test vectors

Conformance vectors for [`../../specs/qmail-1.0.md`](../../specs/qmail-1.0.md) (RAIDA
Group 6, the umbrella). QMail-layer bytes are **big-endian**; embedded message payloads
are CBDF (little-endian). The base RAIDA packet header / AES-128 encryption is out of
scope (RAIDA protocol layer).

QMail is an umbrella that *composes* the other three standards, so its vectors are a mix
of one byte-accurate wire structure (the preamble) and several **mapping / decision-table
/ flow** vectors that fix how the pieces fit together. Same JSON format as the other
suites.

| File | Exercises |
|----|----|
| `01-preamble.json` | The 48-byte universal preamble, **byte-cross-checked against the RKE preamble vector** (§4.3) |
| `02-file-type-mapping.json` | `file_type` → CBDF-section mapping + Tell manifest ordering; payloads reference the CBDF vectors (§4.4) |
| `03-tell-drd-gate.json` | The per-recipient Tell DRD-gate decision table + zero-delivered precedence (§4.5) |
| `04-status-flow.json` | The upload → tell → ping → download lifecycle as a command→status sequence (§4.1) |

## The interop anchor

`01-preamble.json` is built identically to, and asserted **byte-equal** to,
[`../rke/vectors/01-preamble.json`](../rke/vectors/01-preamble.json) for the same coin
identity (CT `0006`, DN 0, SN 42). QMail/1.0 §4.3 and RKE/1.0 §4.2 describe one shared
preamble; `generate.py` fails if the two ever diverge. This is the concrete guarantee
that a QMail stack and an RKE stack agree on the authenticated request header.

## Why several vectors aren't full wire bytes

The umbrella deliberately does not re-encode CBDF/RKE/DRD, and the full Tell manifest wire
layout (routing header, address entries, 64-byte file headers) is documented on the
source `qmail-tell` page rather than reproduced here — so:

- **file-type mapping** points at the CBDF vectors for the actual object bytes
  (`file_type=0` ≈ a CBDF Meta object, `file_type=1` ≈ a CBDF body document).
- **DRD gate** and **status flow** are decision/sequence tables, matching how the source
  specifies behavior (ordering + status codes) rather than a single body layout.

Full Tell/ping/peek/download body-byte vectors are a **next pass** once the manifest wire
format is ported into QMail/1.0 §4.5–§4.6 in full.

## Regenerating

```
python3 generate.py      # rewrites vectors/*.json; non-zero exit if any check fails,
                         # including the RKE preamble cross-check
```

The committed `vectors/*.json` are authoritative; edit `generate.py`, not the JSON.
Note: the RKE cross-check reads `../rke/vectors/01-preamble.json`, so regenerate the RKE
vectors first if that file is stale.
