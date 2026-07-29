# CBDF/1.0 test vectors

Byte-accurate conformance vectors for [`../../specs/cbdf-1.0.md`](../../specs/cbdf-1.0.md)
(Phase II). A second, independent implementation that reproduces every `bytes_hex`
(encode) and every `expected_*` (decode) has demonstrated interop — the "running code"
bar.

## Vector file format

Each file in [`vectors/`](vectors/) is one JSON object. Common fields:

| Field | Meaning |
|----|----|
| `vector` | stable slug for the vector |
| `spec_ref` | the CBDF/1.0 section(s) it exercises |
| `description` | what it is and why |
| `encoding` | always `little-endian` (CBDF/1.0 §2) |
| `bytes_hex` | the full artifact as a continuous lowercase hex string (document/section vectors) |
| `length_bytes` | byte count of `bytes_hex` |
| `annotated` | `[{hex, field}]` — the same bytes split into labeled runs, in order |

Some vectors carry purpose-specific fields instead of `bytes_hex` (e.g. the color
table has `colors` / `transparency_codes`; the extraction vector has `text_body_hex`
plus `expected_plain_strict` and `expected_plain_degraded`).

**How to use them.** *Encoders:* build the described input and assert your output equals
`bytes_hex` (or the per-field values). *Decoders:* parse `bytes_hex` and assert you
recover the annotated structure (and, for extraction, the `expected_plain_*` strings).

## The vectors

| File | Exercises |
|----|----|
| `01-meta-only-sms.json` | Meta-only document (key 33=1); Meta KLV framing; mailbox format; timestamp (§4.1, §4.3) |
| `02-phase1-body-object.json` | Backward-compatible Phase I body (`FS FS STX … EOF`) (§3, §4.2, §5) |
| `03-phase2-minimal-document.json` | Smallest Phase II doc: 14-byte min Styles, empty STX/ETX Text, canonical empty tails (§4.1, §4.4, §4.5) |
| `04-colors-r5g6b5.json` | R5G6B5 encode/decode reference table + 5 transparency codes → alpha (§4.6) |
| `05-resource-record.json` | Packed Resources record framing, no count field (§4.8) |
| `06-plaintext-extraction.json` | Degrade-to-text: strict + degraded extraction over a styled body (§4.5.2) |

## Regenerating

The vectors are produced by [`generate.py`](generate.py), which is a tiny reference
encoder plus the plain-text extractor, with `assert`s that pin every non-trivial value
(color round-trips, minimum-styles length, extraction output). Running it is itself a
conformance smoke test:

```
python3 generate.py      # rewrites vectors/*.json; exits non-zero if any check fails
```

The generated `vectors/*.json` are committed as the authoritative artifacts; edit
`generate.py` (not the JSON) and regenerate.

## Not yet covered (next passes)

Compressed (zlib) documents (§4.9), full Styles sub-table records (§4.4.3), catalogue
LayoutID rendering (§4.4.6), content-hash (§4.3.5), and Tell cross-check (§4.3.4).
