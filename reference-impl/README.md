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

**Status:** all four packages are implemented and pass their conformance vectors —
**CBDF**, **RKE**, **DRD**, and the **QMail** umbrella (50 checks across the suites; every
byte-oriented vector matches byte-for-byte). Per-standard implemented-vs-deferred notes
are at the end of this file.

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
  drd/                  DRD/1.0 (RAIDA Group 16) codec — big-endian directory bodies
    constants.py        command group/codes (140–146), status codes, list types, caps
    _io.py              big-endian primitives + Reader + 3E3E trailer + RAIDA challenge
    fee.py              exact decimal inbox fee (int64 units) + class-rejection compare (§4.3)
    records.py          PQ coin address, user record (§4.4.1), list entry (§4.4.2)
    messages.py         the seven commands: post/get/search/delete + list set/remove/get
  qmail/                QMail/1.0 (RAIDA Group 6) umbrella — composes CBDF + RKE + DRD
    constants.py        Group 6 commands (70–84), status codes (+DRD-gate), file_types
    preamble.py         the 48-byte universal preamble — reused from rke (shared structure)
    filetype.py         file_type -> suffix/CBDF-role mapping + Tell manifest order (§4.4)
    gate.py             the Tell DRD-gate per-recipient delivery decision (§4.5)
  tests/
    test_vectors.py     conformance: re-encode/decode each ../test-vectors/cbdf vector
    test_codec.py       CBDF container round-trips + strict-parse rejections
    test_records.py     CBDF §4.4.3 style record layouts, byte-exact + round-trip
    test_compression.py CBDF §4.9 zlib framing + zip-bomb guard, §4.10 extensions
    test_rke_vectors.py conformance: RKE bodies vs ../test-vectors/rke, byte-exact
    test_drd_vectors.py conformance: DRD bodies/records vs ../test-vectors/drd, byte-exact
    test_qmail_vectors.py conformance: QMail preamble/gate/file_type vs ../test-vectors/qmail
    test_qmail_compose.py end-to-end: QMail composing CBDF + RKE + DRD across LE/BE
```

CBDF and the RAIDA groups (RKE, DRD) are **independent wire worlds** — CBDF is
little-endian document encoding, RKE/DRD are big-endian RAIDA protocol bodies — so each
has its own byte-order IO and they never share a codec. **QMail** is the umbrella: it
*composes* the three, reusing RKE's preamble and DRD's class-rejection logic (mirroring
the standard's dependency graph) and converting between the big-endian RAIDA wire and the
little-endian CBDF payload at the boundary. RKE and DRD each re-implement the shared RAIDA
conventions (big-endian, `3E 3E`, the 12+CRC32 challenge) rather than depend on each
other; a future in-repo RAIDA-protocol module could host those primitives.

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
python3 tests/test_drd_vectors.py # 7/7 DRD conformance vectors, byte-exact
python3 tests/test_qmail_vectors.py  # 5/5 QMail vectors (preamble byte-exact + gate/file_type)
python3 tests/test_qmail_compose.py  # 3/3 end-to-end composition across the LE/BE boundary
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

## DRD status — implemented vs. deferred

**Implemented (Group 16, big-endian bodies):**

- All seven command request bodies (§4.5): `post_user`, `get_user`, `search_users`,
  `delete_user`, `list_set`, `list_remove`, `list_get` — encode and decode, each with
  strict trailer and exact-length validation.
- The data-bearing response payloads: the user record (`get_user`), the 1-byte-count
  search results (`search_users`), and the 2-byte-count list (`list_get`). Success (250)
  and error codes ride in the RAIDA response header, not these payloads.
- Record formats: the 5-byte PQ coin address, the user record (§4.4.1), and 6-byte /
  5-byte list entries (§4.4.2).
- Exact-decimal **inbox fee** (`cc_to_units`/`units_to_cc`, int64 10⁻⁸-CC units, no
  float; rejects negative and >8 fractional digits), the **signed** class-rejection
  comparison, and signed denomination range checks (§4.3).
- Batch-alignment enforcement: `list_set` region a multiple of 6, `list_remove` a
  multiple of 5 (else `ERROR_COINS_NOT_DIV`); `search_users` requires ≥1 name field.

**Deferred / out of scope:**

- The **RAIDA header**, **encryption envelopes**, and the **status-code transport** —
  RAIDA protocol layer; the `detect` AN-verification check is referenced, not built.
- Server-side behavior: AN verification against the coin database, the client-driven
  25-RAIDA write/read/repair distribution, `created_at` preservation, prefix-search
  matching, and anti-replay caching — these are directory-server logic, not wire codec.
- The **avatar symbol table** (256-entry client SVG set, versioned outside the format).

## QMail status — implemented vs. deferred

**Implemented (Group 6 umbrella):**

- The 48-byte universal **preamble** (§4.3), reused from `rke` so it is byte-identical to
  RKE's — the interop anchor the vectors assert.
- The **file_type** object model (§4.4): file_type → storage suffix + CBDF role, the
  attachment suffix rule (10 → `.0.bin`), and the canonical Tell manifest order (private
  meta first, body second, attachments last).
- The Tell **DRD gate** (§4.5): the per-recipient decision in normative order
  (blacklist → whitelist-free → class rejection → inbox fee, with the default Tell fee for
  unregistered recipients), and the "zero delivered → most specific failure wins"
  aggregation. It reuses `drd.class_rejects` so the two standards cannot disagree.
- The Group 6 command codes (70–84) and the QMail status-code subset incl. the DRD-gate
  codes (167/168/169/236/237).
- End-to-end composition (`test_qmail_compose.py`): a little-endian CBDF payload under
  big-endian QMail/RKE framing, demonstrating the same coin identity encoded with a
  big-endian serial in the preamble and a little-endian serial in the CBDF mailbox.

**Deferred / out of scope:**

- Full per-command **wire bodies** for upload/tell/ping/peek/download and Object Transfer
  76–84 (routing header, per-recipient address entries, 64-byte file headers, 256 KB
  pages, resumable byte-range framing) — the source pages carry these; the spec's §8
  vectors fix the preamble, file_type model, and gate logic, which is the QMail-specific
  interop surface implemented here.
- Wire **encryption** (RAIDA 32-byte AES-128 header) and the base RAIDA packet header —
  RAIDA protocol layer.
- The erasure-coding **stripe** split/reassembly (7+1) and beacon/storage server logic.
- **RKE ↔ QMail integration point** (§4.7) — unresolved in the source and flagged in the
  spec; not assumed here (Group 6 auth uses the coin AN, not RKE directly).
