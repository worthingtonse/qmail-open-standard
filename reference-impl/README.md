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
    records.py          field-level encoders for the 12 style record layouts (§4.4.3)
    text.py             Text framing + plain-text extraction / degrade-to-text (§4.5)
    resources.py        Resources section: packed length-walked records (§4.8)
    compression.py      zlib Styles+Text codec + zip-bomb guard (§4.9)
    document.py         the container: framing, compression, extensions, all wire shapes (§4.1)
  rke/                  RKE/1.0 (RAIDA Group 15) codec — big-endian key-exchange bodies
    constants.py        command group/codes, field sizes, coin type, envelope types
    _io.py              big-endian primitives + a bounds-checked Reader + 3E3E trailer
    preamble.py         48-byte coin-auth preamble + RAIDA challenge (§4.2)
    messages.py         preload_master_key (§4.3) and get_key_share req/resp (§4.4)
  tests/
    test_vectors.py     conformance: re-encode/decode each ../test-vectors/cbdf vector
    test_codec.py       CBDF container round-trips + strict-parse rejections
    test_records.py     CBDF §4.4.3 style record layouts, byte-exact + round-trip
    test_compression.py CBDF §4.9 zlib framing + zip-bomb guard, §4.10 extensions
    test_rke_vectors.py conformance: RKE bodies vs ../test-vectors/rke, byte-exact
```

CBDF and RKE are **independent wire worlds** — CBDF is little-endian document encoding,
RKE is big-endian RAIDA protocol bodies — so each package has its own byte-order IO and
they never share a codec. A QMail implementation converts at the boundary. DRD and QMail
packages will follow the same shape.

## Running the tests

No framework needed — each file is a self-contained runner (they are also importable by
`pytest` if you prefer):

```
cd reference-impl
python3 tests/test_vectors.py     # 6/6 CBDF conformance vectors, byte-exact
python3 tests/test_codec.py       # container round-trips + strict-parse rejections
python3 tests/test_records.py     # §4.4.3 style record layouts, byte-exact + round-trip
python3 tests/test_compression.py # §4.9 zlib framing + zip-bomb guard, §4.10 extensions
python3 tests/test_rke_vectors.py # 4/4 RKE conformance vectors, byte-exact
```

`test_vectors.py` is the interop bar: a second, independent implementation passing the
same vectors is the goal (spec §8).

## CBDF status — implemented vs. deferred

**Implemented (Phase II):**

- All three document wire shapes: Phase I body (`FS FS STX …`), meta-only (`key 33=1`),
  and the five-section Phase II container with canonical empty `FS 00000000` tails.
- Meta section: full key registry, repeated keys, 7-byte CloudCoin mailbox, retired-key
  (34) refusal, and the meta-only forbidden-key rule (§4.3.2).
- Styles section: LayoutID plus twelve fixed-order sub-tables with header-byte
  (tier + count) framing and packed fixed-size records (§4.4.2).
- All twelve style **record layouts** of §4.4.3 as field-level types (`records.py`):
  bitfields, nibble-packed spacing/thickness, 6-bit corner radii, the signed-6-bit
  shadow triple, and the tiered Text Style (8/12/16) and Background (6/12/20) forms.
  `SubTable.of([...])` builds a sub-table from typed records; `SubTable.typed()` decodes
  raw records back. Reserved bytes are written 0 and ignored (non-zero accepted) on read.
- R5G6B5 color: pack/unpack with §4.6 rounding, the five transparency codes, and the
  reserved-band → `0x0011` diversion rule.
- Text: STX/ETX framing and the normative plain-text extraction (strict + degraded),
  with every control code's self-delimiting skip length (§4.5.2).
- Resources: packed, length-walked records with per-document ID-uniqueness.
- Compression (§4.9): the mandatory DEFLATE/zlib codec (key 31 = 1) over the combined
  Styles+Text blob, in the `FS [CompLen][DecompLen][data]` framing with the inter-section
  FS carried inside the blob; decode is bounded by DecompLen and an absolute cap
  (zip-bomb resistance) and verifies the decompressed size exactly.
- Extension sections (§4.10): `FS [SectionID:1][Len:4]` after Logic, round-tripped;
  unknown IDs are skipped by length.
- Strict parsing (§5): bounds-checked reads (truncation is an error, never a silent
  slice), reserved-tier rejection, non-zero Logic rejection, key-40/key-31 conflict.

**Deferred (tracked, not yet built):**

- The optional **page-background** record (§4.4.5): encode accepts pre-framed bytes,
  but decode is not supported because a lone BG record's tier (6/12/20 B) is not
  self-describing on the wire — the size cannot be recovered without an out-of-band
  signal. This is a genuine spec gap worth raising before 1.0, not an implementation
  shortcut. (The §4.4.3 `Background` type can pack/unpack the record given its tier.)
- Optional non-default compression codecs **LZ4/Zstd/Brotli** (keys 2-4) and **semantic**
  (5, Phase III): rejected with a clear error; only 0 (none) and 1 (zlib) are built.
- The **layout catalogue** and **font table** (client-side lookup tables, versioned
  outside the format) — the codec carries the IDs; it does not resolve them.

## RKE status — implemented vs. deferred

**Implemented (Group 15, big-endian bodies):**

- The 48-byte coin-authenticated **preamble** (§4.2) and the RAIDA **challenge** (12
  random bytes + big-endian CRC32, with a validity check). The 7-byte CT‖DN‖SN coin
  identity is exposed (big-endian serial — the CBDF-mailbox boundary).
- **`preload_master_key`** request body (§4.3): CSID-length prefix, variable Content
  Server ID, NS record count, packed `[KID][32-byte secret]` records, `3E 3E` trailer.
- **`get_key_share`** request (§4.4, 46+2 B) and response (`[SK][3E 3E]`), with a
  `client_sn(denom, serial)` helper for the 5-byte field.
- Big-endian IO with bounds checks and strict trailer / trailing-byte validation.

**Deferred / out of scope:**

- The **RAIDA request/response header** (command group/code, routing) and the
  **encryption envelope** (Types 0/1/5) — owned by the RAIDA protocol layer, referenced
  by the spec, not redefined here.
- Unresolved source items flagged in the spec and carried as raw/literal here rather
  than invented: the **share threshold / reconstruction rule** (§5 — the crux of the
  security model, unstated in source), the **preamble-vs-command-body discrepancy**
  (§4.2), the **NS** field (§4.3), and the 16-byte challenge split / 5-byte Client SN
  interpretation (§4.4).
