# CBDF/1.0 — Compact Binary Document Format (Phase II)

- **Standard ID:** CBDF
- **Version:** 1.0 (on-wire format version `1` = Phase II; see §4.2)
- **Status:** Draft
- **Source:** Ported from the CloudCoin CBDF specification, documents `00`–`10`
  (spec revision 1.1, 2026-07-13). This file is the open-standard rendering of that
  material; where this document and the source disagree, that is a porting bug to fix.
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on:** nothing. CBDF is the foundation of the QMail family — RKE, DRD, and
  QMail all encode through it.

> **Naming correction:** CBDF is the **Compact Binary _Document_ Format**, not "Data
> Format" as the original scaffolding handoff had it. It is a binary replacement for
> HTML/CSS for styled documents, not a general-purpose data-serialization codec.

## 1. Abstract

CBDF is a binary open-standard document format that radically reduces the size of
marked-up documents relative to HTML/CSS. A styled CBDF message can be on the order
of 1% of the size of an equivalent HTML email; short messages are a few dozen bytes.
It optimizes for bandwidth, storage, RAM, and parse cost while always degrading
cleanly to plain UTF-8 text. CBDF is the encoding layer for QMail email (`.qmail`),
QWeb pages (`.qweb`), and RAIDA data exchange.

CBDF gets its compactness by keeping large tables (page layouts, fonts, named style
sets) in the client/codec and carrying only small indices on the wire: a 2-byte
Layout ID selects one of 65,536 predefined page layouts, colors are 2 bytes (R5G6B5),
fonts are a 2-byte ID, formatting is a compact binary style record referenced by a
1-byte index, and the 32 ASCII control characters (`0x00`–`0x1F`) are repurposed as
the inline command vocabulary.

## 2. Status & terminology

This document is a Draft and is not stable; conforming implementations MUST NOT rely
on its current content.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

**Byte order.** All multi-byte integers in CBDF are **little-endian** (LE). (Note: the
QMail Tell wire protocol uses big-endian; values are converted at that boundary — see
§4.7 and [QMail/1.0].)

**Design principles** (normative intent):
1. **One canonical encoding.** Strict parsers; no HTML-style quirks repair.
2. **Degrade to readable text.** Stripping bytes `0x00`–`0x1F` (keeping TAB `0x09`
   and LF `0x0A`) from the Text section yields clean UTF-8.
3. **Tables over self-description.** Layouts, fonts, and styles live in the
   codec/catalogue; the wire carries indices.
4. **Fixed sizes and explicit lengths.** No delimiter sniffing for style records or
   section boundaries.
5. **Static documents are safe.** Phase II has no executable Logic; AI prompts are
   receiver-evaluated requests, never executed markup.
6. **User owns the final render.** Themes and accessibility settings outrank document
   chrome.
7. **Claims vs. attestations.** Meta is a sender *claim*; QMail Tell / RAIDA data is
   network *attestation* (see §4.3.4).

## 3. Scope / non-goals

**In scope:** the byte-level document container (five sections); the Meta key/value
envelope; the inline control-character command language; the color, font, resource,
and (by reference) style and layout systems; compression; versioning and phasing.

**Non-goals:** transport and key exchange (see [RKE/1.0]); resource/mailbox discovery
and directory (see [DRD/1.0]); mail semantics, Tell manifests, and routing (see
[QMail/1.0]); executable Logic (deferred to Phase III).

## 4. Normative definitions

### 4.1 Document structure

A CBDF document is five sections separated by FS (`0x1C`). Core sections are
identified by **position**, not by a per-section ID byte:

```
[Meta] FS [Styles] FS [Text] FS [Resources] FS [Logic]
[ optional: FS [SectionID:1][Len:4 LE][payload] ... ]   ; extension sections
```

| # | Section    | Length prefix | Compressed?          | Description                                   |
|---|------------|---------------|----------------------|-----------------------------------------------|
| 1 | Meta       | No (KV pairs) | Never                | Document envelope: identity, routing, preview |
| 2 | Styles     | 4 bytes LE    | With Text if enabled | LayoutID + visual formatting lookup tables    |
| 3 | Text       | 4 bytes LE    | With Styles if enabled | UTF-8 body + inline control codes           |
| 4 | Resources  | 4 bytes LE    | Never (already-compressed media) | Binary blobs (images, fonts)      |
| 5 | Logic      | 4 bytes LE    | —                    | Executable code; **length 0 in Phase II**     |

Text precedes Resources so downloads are **abortable**: a client can render text and
stop before pulling image bytes. The 4-byte length follows the FS and counts **only**
the section payload (the length field itself is not included).

**Canonical encode:** always emit the Resources and Logic tails, as `FS 00 00 00 00`
when empty (10 bytes). **Lenient decode:** parsers MAY treat EOF immediately after a
valid Text section as empty Resources/Logic, but new encoders MUST NOT rely on it. A
non-zero Logic length in a version-1 document is a **hard failure** until Phase III.

**Meta-only documents** (Meta key 33 = 1): the Meta section stands alone with no
following FS markers — used for ultra-compact notifications and SMS-class messages
(on the order of 14–50 bytes).

### 4.2 Versioning and phases

| Wire version (Meta key 30) | Phase | Body shape |
|----|----|----|
| absent → 0 | Phase I | `FS FS STX [plain text … EOF]` (backward-compatible, deployed) |
| 1 | Phase II | Length-prefixed Styles, Text, Resources, Logic; full style/control language |
| ≥ 2 | future | Bump only when old parsers cannot safely skip new constructs |

There is **no leading magic byte** before the Meta pair count — that would break
deployed Phase I files. A major (wire-incompatible) change is signalled by bumping the
version byte; published versions are immutable (see `../GOVERNANCE.md`).

- **Phase I** — plain text only. Implemented (`qmail_cbdf.c`).
- **Phase II** — this document: styled text, layout catalogue, images, nav, tables,
  layers, feature flags, Tell annotations.
- **Phase III** — Logic section, forms, interactivity, semantic encoding. Planned.

**Migration rule:** ship a tolerant Phase I decoder *before* any Phase II encoder. If
key 30 ≥ 1 or key 33 = 1, do not demand `FS FS STX`; show Preview Text / AI Summary /
Subject labeled as newer-client content.

### 4.3 Meta section

Never compressed; always readable without touching Styles/Text. Format:

```
[Pair Count: 2 bytes LE]
[Key ID: 1][Value Length: 1][Value: N bytes]   × Pair Count
```

- Value length is **0–255 only**; there is no extended-length sentinel (`0xFF` = 255
  bytes). Values over 255 bytes belong in Text/Resources/extension sections.
- Pair count includes every repeated key (e.g. each `To` recipient).
- Unknown keys are skipped by reading key + length + value (forward-compatible).
- Keys MAY appear in any order; encoders SHOULD emit key 0 then key 30 early.

#### 4.3.1 Phase I key registry (deployed — must match `qmail_cbdf.h`)

| Key | Name | Size | Req | Notes |
|----|----|----|----|----|
| 0 | Meta File Type | 1 | * | 0 generic, 1 qmail, 2 sms, 3 qweb, 4 presentation (rsv), 5 form (rsv). Key 34 retired. |
| 1 | QMail ID (GUID) | 16 | * | Sender-assigned; equals Tell `email_id` |
| 2 | Subject | ≤255 | | Plain UTF-8 |
| 3 | Attachment Name | var | | Repeated, attachment order |
| 4 | Attachment Total Pages | 2 LE | | Repeated dense; 0 = legacy |
| 5 | Page Hash | 4 LE | | Optional CRC32 per page |
| 12 | Attachment Count | 1 | * | 0–255 |
| 13 | To Mailbox | 7 | * | Repeated |
| 14 | CC Mailbox | 7 | | Repeated |
| 19 | From Mailbox | 7 | * | Sender claim |
| 25 | Timestamp | 4 LE | * | Unix seconds; low 32 bits of key 41 when both present |

`*` = required for QMail documents. Keys 6–11, 15–18, 20–24, 26–29 reserved.

#### 4.3.2 Phase II key registry

| Key | Name | Size | Notes |
|----|----|----|----|
| 30 | Version | 1 | Absent = Phase I; **1 = Phase II** (required in v1) |
| 31 | Compression Type | 1 | 0 none, 1 zlib (MTI), 2 LZ4, 3 Zstd, 4 Brotli, 5 semantic (experimental) |
| 32 | Default Style Set | 1 | 0 explicit, 1 client default, 2–255 named sets |
| 33 | EOF Flag | 1 | 1 = meta-only document |
| 34 | **RETIRED** | — | Never emit; never reassign |
| 35 | AI Summary | ≤255 | UTF-8 inbox summary / fallback |
| 36 | Preview Text | ≤255 | UTF-8 snippet; SHOULD on all v1 during transition |
| 37 | Subject Style ID | 1 | Text style index for inbox listing |
| 38 | Semantic Model | 20 | Only if compression = 5 |
| 39 | Semantic Flags | 1 | Only if compression = 5 |
| 40 | Text Offset | 4 LE | Optional; MUST be absent if key 31 ≠ 0 |
| 41 | Timestamp64 | 8 LE | Unix epoch **seconds**; prefer over key 25 |
| 42 | Required Features | 1–4 | LE bitfield; trailing zeros omitted; absent = 0 (§4.3.3) |
| 43 | Optional Features | 1–4 | Same shape and bit registry |
| 44 | Content Language | ≤35 | BCP 47 (e.g. `en`, `fr-CA`) |
| 45 | Content Hash | 1+N | `[alg:1][digest]` (§4.3.5) |
| 46–199 | Reserved | | Sender-written future keys |
| 200–219 | Receiver Annotations | var | **Never valid on the wire** (§4.3.4) |
| 220–255 | Reserved | | |

When key 33 = 1 (meta-only), keys 31/32/37/40/42/43 are meaningless and MUST be absent.

#### 4.3.3 Feature flags (keys 42 required / 43 optional)

LE bitfields, 1–4 bytes, trailing zero bytes omitted, absent = 0. Encoders MUST set a
bit only for features actually used. **Required** features render a warning / labeled
fallback on unsupporting clients (not a security boundary; accessibility settings
always override). **Optional** features fall back silently.

| Bit | Feature | Bit | Feature |
|----|----|----|----|
| 0 | Non-default / explicit styles | 6 | Frames / embedded documents |
| 1 | Images / non-empty Resources | 7 | AI prompts |
| 2 | Tables | 8 | Semantic encoding |
| 3 | Nav / structured item blocks | 9 | Extension sections present |
| 4 | Custom fonts (IDs 4000–4094) | 10 | Rare-tier styles |
| 5 | Font effects / animation | 11 | Catalog layout (LayoutID ≥ 0x0100) |

Bits 12–31 reserved.

#### 4.3.4 Tell integration — claims vs. attestations

Meta keys 0–199 are sender **claims**. The QMail Tell (Peek/Ping) carries
RAIDA-confirmed identity, timestamp, locker, servers, and manifest — the
**attestation**. Integration is **cross-check + annotate**, never merge on the wire:

- **GUID:** Tell `email_id` ≠ key 1 → **hard reject** the object.
- **Sender:** Tell ≠ key 19 → display the Tell identity; flag Meta as a conflicting claim.
- **Timestamp:** Tell is authoritative; skew > 48h SHOULD be surfaced.
- **CRC fail:** show labeled plain-text fallback, never a partial styled render.

**Receiver-annotation keys 200–219** are written only by the receiving client into
**local storage** (Tell BE scalars re-encoded to LE). They **MUST NOT** appear on the
wire; clients MUST strip them on receive (before trust decisions) and on send/export.

#### 4.3.5 Content hash (key 45) and mailbox format

Content hash: `[alg:1][digest:N]` — alg 1 = MD5 (N=16), alg 2 = SHA-256 (N=32).
Canonical hash input (decompressed): `[StylesLen][Styles] FS [TextLen][Text]
[ResourcesLen][Resources]` — excludes Meta, outer FS markers, and Logic.

Mailbox fields (To/CC/From/Verified Sender) are exactly **7 bytes**:
`[Coin Group: 2][Denomination: 1][Serial Number: 4 LE]`. CloudCoin mailboxes MUST
encode the coin-group field as bytes `00 06`.

### 4.4 Styles section (structural summary — full port pending)

The Styles section begins with a **2-byte LayoutID** (selecting a predefined page
layout from the catalogue) followed by up to **11 style sub-tables**, separated by GS
(`0x1D`), each holding **packed** fixed-stride records (a header gives count and tier,
so the parser knows the exact stride — no separators between records). Sub-tables
cover text styles, containers (background/border/shadow), nav bars, tables, and Image
Definitions, among others. Records use tiered layouts (base/rare tiers) and reference
the color and font systems (§4.6, §4.7).

> **TODO (next expansion):** port the full sub-table record formats, tiers, and the
> layout catalogue from source docs `03-styles-section` and `10-layout-catalog`,
> including the pane-index model, mobile layout pairs, and the LayoutID registry.
> These are large; they are deliberately deferred from this first draft.

### 4.5 Text section and the control language

```
[Length: 4 bytes LE] [STX] [optional SOH styled subject] [body] [ETX]
```

The length prefix is authoritative; ETX (`0x03`) is a validation sentinel that SHOULD
land where the length indicates. **CRLF normalization is normative:** encoders MUST
convert CRLF and bare CR to LF before writing Text. In Phase II Text, `0x0D` is always
HORIZ_RULE + one style-index byte — never a soft carriage return.

**Style stack (strict):** STYLE_TEXT/CONTAINER/TABLE push; STYLE_END pops style;
BLOCK_END closes a block and pops. Max depth **32**. Popping an empty stack, or an
unclosed block at ETX, is an **invalid document**. With explicit styles (key 32 = 0) a
style index ≥ the sub-table count is invalid (do not clamp).

#### 4.5.1 Control-character assignment table (`0x00`–`0x1F`)

| Hex | CBDF name | Command | Payload | Phase |
|----|----|----|----|----|
| 0x00 | NOP | No-op / padding | — | II |
| 0x01 | SUBJECT_START | Styled subject begins | — | II |
| 0x02 | TEXT_START | Start of body | — | II |
| 0x03 | TEXT_END | End of body (validation) | — | II |
| 0x04 | DOC_END | End of document | — | II |
| 0x05–0x08 | RESERVED | (interactive) | — | III |
| 0x09 | TAB | Horizontal tab | — | II (kept in plain text) |
| 0x0A | LINE_BREAK | Line feed | — | II (kept in plain text) |
| 0x0B | PARA_BREAK | Paragraph break | — | II |
| 0x0C | PAGE_BREAK | Page break | — | II |
| 0x0D | HORIZ_RULE | Horizontal rule | `[StyleIndex:1]` | II |
| 0x0E | LINK_START | Link start | `[Type:1][Len:1][Target:N]` | II |
| 0x0F | LINK_END | Link end | — | II |
| 0x10 | DATA_ESCAPE | Raw binary escape | `[Len:2 LE][Data:N]` | II |
| 0x11 | STYLE_TEXT | Apply text style (push) | `[Index:1]` | II |
| 0x12 | STYLE_CONTAINER | Apply container style (push+block) | `[Index:1]` | II |
| 0x13 | STYLE_TABLE | Apply table style (push+block) | `[Index:1]` | II |
| 0x14 | STYLE_END | Pop style | — | II |
| 0x15 | ELEMENT_ID | Stable element ID | `[ID:1]` (or `[0xFF][id:2 LE]`) | II |
| 0x16 | IMAGE | Insert image | `[ImageDefIndex:1]` | II |
| 0x17 | BLOCK_END | Close block + pop | — | II |
| 0x18 | RESERVED_HIDE | (hide/show) | — | III |
| 0x19 | ITEM_BLOCK | List/nav/etc. start | `[Type:1][StyleIndex:1]` | II |
| 0x1A | AI_PROMPT | Receiver-evaluated AI prompt | `[Type:1][Len:2 LE][UTF-8:N]` | II |
| 0x1B | ESCAPE | Extended command | `[Code:1][Payload:var]` | III |
| 0x1C | SECTION_SEP (FS) | Between major sections | — | II |
| 0x1D | GROUP_SEP (GS) | Between style sub-tables | — | II |
| 0x1E | RECORD_SEP (RS) | Table rows (Text only) | — | II |
| 0x1F | UNIT_SEP (US) | Items / table cells | — | II |

Sub-type enumerations: **Link types** 0 URL, 1 QWeb page ID, 2 mailbox (7 B), 3 action
(Phase III). **Item-block types** 0 unordered, 1 ordered, 2 nav, 3 definition list.
**AI-prompt types** 0 style, 1 image, 2 layout. AI prompts are advisory only; the
document MUST remain legible if they are ignored.

#### 4.5.2 Plain-text extraction (degrade-to-text)

Decompress if needed; scan STX…ETX; keep bytes ≥ `0x20` plus TAB and LF; skip other
controls **and their self-delimiting payloads** (HORIZ_RULE +1; LINK_START +1+1+N;
DATA_ESCAPE +2+N; STYLE_TEXT/CONTAINER/TABLE +1; ELEMENT_ID +1 or +3 if first byte is
`0xFF`; IMAGE +1; ITEM_BLOCK +2; AI_PROMPT +1+2+N). Every future command MUST be
self-delimiting and added to this skip table in the same change.

### 4.6 Color system (R5G6B5)

Each color is a 16-bit LE value: bits 15–11 Red (5), 10–5 Green (6), 4–0 Blue (5) —
65,536 colors in 2 bytes. Conversion to 8-bit: `R8 = round(R5·255/31)`,
`G8 = round(G6·255/63)`, `B8 = round(B5·255/31)`.

**Five reserved transparency codes** (they appear only inside style records, never in
the Text stream):

| Code | Meaning | Alpha |
|----|----|----|
| 0x000C | 100% transparent | 0.0 |
| 0x000D | 80% transparent | 0.2 |
| 0x000E | 60% transparent | 0.4 |
| 0x000F | 40% transparent | 0.6 |
| 0x0010 | 20% transparent | 0.8 |

Any non-reserved code is fully opaque. Encoders converting RGB→R5G6B5 MUST bump a
result that lands in `0x000C`–`0x0010` to the nearest safe code (`0x0011`).

### 4.7 Font system

Fonts are a **2-byte LE Font ID**: bits 0–11 Font Family Index (0–4095), bits 12–15
sub-variant hints (12 condensed, 13 extended, 14 monospace, 15 reserved=0). Family 0 =
client default; 1–2000 = standard CoolText-class set; 2001–3999 reserved; 4000–4094 =
custom fonts (Font Index − 4000 = Resource ID of a type-4 font resource); 4095 =
error/unknown. Bold/italic/underline/strike live in the text-style record's flags
byte, **not** the Font ID; flags take priority over hints.

A **4-bit effect ID + 4-bit intensity** live in the text-style rare tier: 0 none,
1 drop shadow, 2 outer glow, 3 pulsing glow*, 4 linear gradient, 5 multi-gradient,
6 outline, 7 emboss, 8 glitter*, 9 flames*, 10 neon, 11 3D extrude, 12 reflection,
13 frosted glass, 14 metallic, 15 custom (parameters in the Font Effects sub-table).
(* animated.) Effect color is R5G6B5 in the rare tier.

The canonical font table maps Font Family Index → font file; it is maintained and
versioned **outside** the CBDF format (append-only), and distributed with clients. An
unknown index falls back to family 0.

### 4.8 Resources section

Never re-compressed (media codecs are already compressed). Packed records, no count
field and no separators — the parser walks until the section length is exhausted:

```
[Length: 4 bytes LE]
repeat: [Resource ID:1][Type:1][Data Length:4 LE][Raw Data:N]
```

Resource ID is unique within the document (0–255 → max 256 resources; a count field is
absent). Types: 0 image/png, 1 image/jpeg, 2 image/webp, 3 image/svg, 4 font, 5 audio,
6 video, 7 embedded CBDF sub-document; 8–255 reserved. IMAGE always references an
**Image Definition** (which carries width/height/fit for placeholders), which in turn
holds the Resource ID — so stripping one resource never invalidates references to
others. Per-resource data length up to 4 GiB (uint32 LE).

### 4.9 Compression

Meta key 31 selects the codec over the Styles+Text blob only (Meta and Resources are
never CBDF-compressed): 0 none (required), 1 DEFLATE/zlib (**mandatory to implement**;
default), 2 LZ4, 3 Zstd, 4 Brotli (all optional decode; emit only if peer support is
known), 5 semantic (experimental, Phase III), 6–255 reserved. Encoders SHOULD skip
compression when Styles+Text < 256 bytes. When compressed, the FS between Styles and
Text lives **inside** the compressed blob.

### 4.10 Extension sections

After Logic, a document MAY carry `FS [SectionID:1][Len:4 LE][payload]`. IDs are
registry-assigned; Phase II parsers MUST skip unknown IDs by length. Section ID 1 is
reserved for a future Phase III Parse Index.

## 5. Security considerations

**Mandatory.**

- **Static-safe by construction.** Phase II has no executable Logic; a non-zero Logic
  length in a v1 document MUST hard-fail. AI prompts (`0x1A`) are advisory requests the
  receiver's client may evaluate — never executable markup; the document MUST remain
  legible if they are ignored.
- **Claims are not attestations.** Meta keys 0–199 are unauthenticated sender claims.
  Trust decisions and "verified" UI MUST derive only from Tell-based annotations
  (keys 200–219), which MUST never appear on the wire and MUST be stripped on receive
  and on send/export. GUID mismatch → hard reject; sender mismatch → show Tell identity
  and flag the conflict; CRC failure → labeled plain-text fallback, never a partial
  styled render (anti-phishing).
- **Decoder hardening.** Enforce the max style-stack depth of 32; validate that style
  indices are within bounds (do not clamp); require every control payload to be
  self-delimiting; bound total size and per-resource length; treat a stray `0x1E`
  between packed style/resource records as a document error.
- **Canonical, strict parsing.** One canonical encoding; no quirks repair. Reject
  malformed input deterministically to avoid parser-differential attacks.
- **Compression safety.** Bound decompressed size and expansion ratio (zip-bomb
  resistance) before allocating from key-31 codecs.
- **User sovereignty.** Accessibility and theme settings override document styling,
  including required-feature bits (e.g. reduced motion disables animated effects).

## 6. IANA / registry considerations

- **Media types:** `application/cbdf` (generic), plus QMail's `application/qmail`
  (see [QMail/1.0]). File extensions: `.cbdf`, `.qmail`, `.qweb`.
- **CBDF Meta Key registry** — keys 0–255; allocation policy *Specification Required*;
  key 34 permanently retired. Machine-readable source in `../registries/`.
- **CBDF Control-Character registry** — the 32 assignments in §4.5.1; changes MUST
  update the plain-text skip table in the same action.
- **CBDF Feature-Bit registry** — bits in §4.3.3 (keys 42/43).
- **CBDF Resource-Type registry** — §4.8.
- **CBDF Compression-Type registry** — §4.9.
- **Layout Catalogue** and **Font Table** — versioned **outside** the format,
  append-only, jointly governed (CloudCoin Consortium, Perfect Money Foundation, RAIDA
  Group); referenced here by ID + table version.

> **TODO:** add the Extension-Section-ID registry and the Styles sub-table / LayoutID
> registries when §4.4 is ported in full.

## 7. References

**Normative**
- [RFC 2119] Key words for Requirement Levels.
- [RFC 1950] ZLIB / [RFC 1951] DEFLATE — mandatory-to-implement codec (key 31 = 1).
- [RFC 3629] UTF-8.
- [BCP 47] Tags for Identifying Languages (Meta key 44).
- [QMail/1.0] — `./qmail-1.0.md` (Tell manifest, mailbox attestation, transport BE↔LE).

**Informative**
- [RFC 8949] CBOR, MessagePack — prior art for compact binary encodings.
- Original CloudCoin CBDF specification, documents `00`–`10` (revision 1.1, 2026-07-13).

## 8. Appendix: test vectors

Concrete input→output vectors live in [`../test-vectors/cbdf/`](../test-vectors/cbdf/).
Every normative rule above SHOULD have at least one vector. Priority set for the first
pass:

1. **Meta-only document** (SMS-class): pair count + required keys → exact bytes.
2. **Phase I body** (`FS FS STX … EOF`) round-trip.
3. **Phase II uncompressed** minimal document: Meta + empty Styles + Text (STX/ETX) +
   empty Resources + empty Logic, verifying the `FS 00000000` empty tails.
4. **R5G6B5** reference colors (Black `0x0000`, White `0xFFFF`, Pure Red `0xF800`,
   Pure Green `0x07E0`, Pure Blue `0x001F`) and each transparency code → alpha.
5. **Resource record** framing (e.g. a 1024-byte JPEG, ID=1 → section length 1030).
6. **Plain-text extraction** over a styled body with links, an image, and a table.

A second, independent implementation passing these vectors is the interop bar.
