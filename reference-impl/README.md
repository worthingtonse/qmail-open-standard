# Reference implementation

At least one open-source implementation of the QMail-family standards, used to
demonstrate that the specs are implementable and to run against the conformance
[`../test-vectors/`](../test-vectors/).

- **License:** Apache-2.0 (see [`LICENSE`](LICENSE)) — a code license with its own
  explicit patent grant, distinct from the document license (`../LICENSE-DOC`) and
  the standards' patent grant (`../PATENTS`).
- **Build order:** implement **CBDF first** (everything encodes through it), then
  RKE and DRD, then QMail.
- **Conformance:** the implementation MUST pass the vectors in `../test-vectors/`.

## Toolchain

**Python 3, standard library only** — no third-party dependencies, no build step. A
reference implementation optimizes for clarity and correctness against the spec, so the
codec reads like the document it implements (module and symbol names track the spec's
section numbers). The conformance vectors are also Python, and the test runner loads the
vector JSON directly and checks the codec reproduces it byte-for-byte.

Requires Python ≥ 3.8. Tested with the system `python3`.

## Layout

```
reference-impl/
  cbdf/                 CBDF/1.0 (Phase II) codec — the foundation format
    constants.py        control codes, meta-key registry, sub-table order, enums (§4.x)
    _io.py              little-endian primitives + a bounds-checked forward Reader (§2)
    color.py            R5G6B5 pack/unpack + reserved transparency codes (§4.6)
    meta.py             Meta section + 7-byte mailbox encode/decode (§4.3, §4.3.5)
    styles.py           Styles section: LayoutID + 12 GS-separated sub-tables (§4.4)
    text.py             Text framing + plain-text extraction / degrade-to-text (§4.5)
    resources.py        Resources section: packed length-walked records (§4.8)
    document.py         the container: 5-section framing + all three wire shapes (§4.1)
  tests/
    test_vectors.py     conformance: re-encode/decode each ../test-vectors/cbdf vector
    test_codec.py       unit tests for paths the vectors don't cover
```

RKE, DRD, and QMail packages will follow the same shape once CBDF is complete.

## Running the tests

No framework needed — each file is a self-contained runner (they are also importable by
`pytest` if you prefer):

```
cd reference-impl
python3 tests/test_vectors.py     # 6/6 CBDF conformance vectors, byte-exact
python3 tests/test_codec.py       # round-trips + strict-parse rejections
```

`test_vectors.py` is the interop bar: a second, independent implementation passing the
same vectors is the goal (spec §8).

## CBDF status — implemented vs. deferred

**Implemented (Phase II):**

- All three document wire shapes: Phase I body (`FS FS STX …`), meta-only (`key 33=1`),
  and the five-section Phase II container with canonical empty `FS 00000000` tails.
- Meta section: full key registry, repeated keys, 7-byte CloudCoin mailbox, retired-key
  (34) refusal, and the meta-only forbidden-key rule (§4.3.2).
- Styles section: **structural** codec — LayoutID plus twelve fixed-order sub-tables
  with header-byte (tier + count) framing and packed fixed-size records (sizes per
  §4.4.2). Record interiors are carried as opaque bytes and round-trip exactly.
- R5G6B5 color: pack/unpack with §4.6 rounding, the five transparency codes, and the
  reserved-band → `0x0011` diversion rule.
- Text: STX/ETX framing and the normative plain-text extraction (strict + degraded),
  with every control code's self-delimiting skip length (§4.5.2).
- Resources: packed, length-walked records with per-document ID-uniqueness.
- Strict parsing (§5): bounds-checked reads (truncation is an error, never a silent
  slice), reserved-tier rejection, non-zero Logic rejection.

**Deferred (tracked, not yet built):**

- Per-field encoders/decoders for the twelve style **record** layouts of §4.4.3 (the
  structural codec frames them; it does not yet interpret their fields).
- The optional **page-background** record (§4.4.5): encode accepts pre-framed bytes;
  decode of a non-GS byte after the LayoutID is not yet supported (its on-wire size is
  not self-describing — needs the §4.4.3 background record decoder above).
- **Compression** (Meta key 31 ≠ 0, §4.9): this codec emits and accepts uncompressed
  documents only.
- **Extension sections** (§4.10) after Logic.
- The **layout catalogue** and **font table** (client-side lookup tables, versioned
  outside the format) — the codec carries the IDs; it does not resolve them.
