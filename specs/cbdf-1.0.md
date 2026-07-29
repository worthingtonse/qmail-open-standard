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

### 4.4 Styles section

Framing (after the FS that ends Meta):

```
[Length: 4 bytes LE]        ; counts section content only
[LayoutID: 2 bytes LE]      ; §4.4.6
[Page background: optional BG record | omitted if next byte is GS]   ; §4.4.5
GS [sub-table] GS [sub-table] ...   ; 12 sub-tables in fixed order, §4.4.2
```

If Meta key 32 (Default Style Set) ≥ 1, the section may carry no records (LayoutID +
empty GS markers, or delta overrides only). Minimum styles section: `Length = 14`,
`LayoutID = 0x0000`, then GS × 12 (empty sub-tables).

#### 4.4.1 Sub-table header byte and packed records

Each sub-table begins with one header byte: bits 0–1 = **tier** (00 base, 01 extended,
10 rare, 11 reserved → reject in Phase II); bits 2–7 = **count** 0–63 records. All
records in a sub-table share one tier (fixed size). Records are **packed** — no RS
between them; `record_ptr(i) = table_start + 1 + i × record_size(tier)`. An empty
sub-table is a bare GS (a header with count 0 is also accepted). Optional style-index
reference fields use **255 = no reference** (valid record indices are 0–62).

#### 4.4.2 Sub-table order (fixed, GS-separated)

| # | Sub-table | Tiered? | Record size (base / ext / rare) |
|---|----|----|----|
| 1 | Container Background | Yes | 6 / 12 / 20 B |
| 2 | Container Border | No | 9 B |
| 3 | Container Spacing | No | 4 B |
| 4 | Container Shadow | No | 4 B |
| 5 | Container Composite | No | 5 B |
| 6 | Text Styles | Yes | 8 / 12 / 16 B |
| 7 | Font Effects | No | 4 B |
| 8 | Nav Bar Styles | No | 12 B |
| 9 | Table Styles | No | 6 B |
| 10 | Image Definitions | No | 8 B |
| 11 | Frame Definitions | No | 8 B |
| 12 | Forms | — | reserved (Phase III) |

Conventions for all record layouts below: multi-byte integers are LE; colors are
R5G6B5 or transparency codes (§4.6); extended/rare tiers extend the smaller tier
without moving its fields; reserved bytes MUST be written 0 and ignored on read
(decoders MUST accept non-zero reserved bytes — they are per-record compatibility
headroom).

#### 4.4.3 Record byte layouts (normative)

**Text Style (6, tiers 8/12/16 B).** 0–1 FontID (§4.7); 2 font size pt (0 = inherit);
3 flags (bit0 bold, 1 italic, 2 underline, 3 strike, 4 subscript, 5 superscript, 6–7
alignment 0 left/1 center/2 right/3 justify); 4–5 foreground color; 6–7 background
color. *Extended:* 8–9 text shadow packed u16 (bits0–5 signed X, 6–11 signed Y, 12–15
blur; 0 = none); 10 letter spacing signed int8 in 0.1 em; 11 line height (0 auto, else
÷10). *Rare:* 12 low nibble effect ID / high nibble intensity; 13 bits0–1 transform
(0 none/1 UPPER/2 lower/3 Capitalize), bits2–3 direction (0 auto/1 LTR/2 RTL), bits4–7
word spacing 0–15 in 0.1 em; 14–15 effect color.

**Background (1, tiers 6/12/20 B).** 0–1 background color (gradient color 1 when a
gradient is set); 2–3 background image ID u16 (0 none); 4 color opacity 0–255; 5 image
flags (bit0 repeat-x, 1 repeat-y, 2 fixed, 3 cover, 4 contain). *Extended:* 6–7
gradient color 2 (present iff gradient type ≠ 0); 8 gradient type (0 none/1 linear/2
radial); 9 linear angle (value × 360/256°); 10 color-2 stop position 0–255 = 0–100%;
11 reserved. *Rare:* 12–13 gradient color 3; 14–15 gradient color 4; 16 color-3 stop;
17 color-4 stop; 18–19 reserved.

**Border (2, 9 B).** 0–1 border color; 2–3 thickness nibbles px (byte2 top|right,
byte3 bottom|left, 0–15 each); 4–5 outside-of-border color (or transparency); 6–8 four
6-bit corner radii packed LSB-first (TL, TR, BR, BL; percent ≈ round(value × 50/63)).
Line style is solid in Phase II.

**Spacing (3, 4 B).** 0–1 margins (byte0 top|right, byte1 bottom|left); 2–3 padding,
same packing. Nibble: 0 = explicit zero; 15 = inherit-from-left; 1–14 = value × 4 px.

**Shadow (4, 4 B).** 0–1 shadow color; 2–3 packed u16 (bits0–5 signed X px, 6–11
signed Y px, 12–15 blur 0–15) — same packing as Text extended 8–9.

**Composite (5, 5 B).** 0 background style index (255 none); 1 border index; 2 spacing
index; 3 shadow index; 4 bits0–1 overflow (0 visible/1 hidden/2 scroll), bits2–7
layer_id (§4.4.4).

**Font Effect (7, 4 B).** 0 effect ID; 1 intensity 0–255; 2 parameter A; 3 parameter B
(0 = default). Effect IDs 0–15 per §4.7 (15 = custom, deterministic parameters — never
AI). The sub-table is **keyed by Effect ID**: at most one record per ID; a duplicate ID
makes the Styles section invalid.

**Nav Bar (8, 12 B).** 0 item text style index; 1 active-item index (255 = items); 2
hover-item index (255 = items); 3 bar background index (255 none); 4 bar border index;
5 bar spacing index; 6 collapse breakpoint (0 never, else value × 8 px); 7 flags (bit0
orientation 0 horiz/1 vert, bits1–2 item mode 0 text+icon/1 text/2 icon, bits3–4 align
0 start/1 center/2 end/3 space-between); 8–11 reserved.

**Table (9, 6 B).** 0 header-row text style index (255 = body); 1 body text style
index; 2 grid border index (255 none); 3 alternate-row background index (255 = no
stripes); 4 cell spacing index (255 = default); 5 flags (bit0 first row is header, bit1
row stripes, bit2 column rules, bit3 row rules).

**Image Definition (10, 8 B).** 0 source type (0 document resource, 1 built-in, 2
AI-generated reserved); 1 source ID (ResourceID for type 0); 2–3 display width u16 px
(0 natural); 4–5 display height u16 px (0 natural — always present so a client that
skipped Resources can reserve placeholder space); 6 fit (0 contain/1 cover/2 stretch/3
tile); 7 border style index (255 none).

**Frame Definition (11, 8 B).** 0 source type (0 embedded CBDF resource, 1 QWeb ID
reserved Phase III); 1 source ID; 2–3 width u16 px (0 auto); 4–5 height u16 px (0
auto); 6 sandbox bits (default 0 = fully sandboxed: bit0 internal scrolling, bit1
links, bit2 framed resources, bit3 nested frames — framed content can never execute
Logic in Phase II); 7 border style index (255 none).

Hover/event fields are declarative appearance only in Phase II (actions are Phase III
Logic).

#### 4.4.4 Layer registry (Composite `layer_id`)

0 Background (behind everything); 1 Content (default flow); 2–7 Overlays (stack by ID);
8 Disclaimer (pinned after content); 9 Debug (client-only); 10 Modal / 11 Alert
(parsed but not auto-shown until Logic); 12–62 reserved (treat as content overlays); 63
HTML/foreign (reserved Phase III).

#### 4.4.5 Page background

Immediately after LayoutID and before the first GS, an optional single BG record sets
the page background (layer 0). If the next byte is GS, the page background is
default/transparent.

#### 4.4.6 LayoutID and the layout catalogue

The Styles payload opens with a 2-byte LE **LayoutID**. Geometry and pane tables live
in a client-side **layout catalogue** (like the font table); the wire carries only the
ID. Each catalogue entry declares a **pane index table** and a **mobile pair** ID.

| Range | Meaning |
|----|----|
| `0x0000`–`0x00FF` | **Compatibility page:** low byte = legacy 1-byte bitfield (bit0 header, 1 footer, 2 left, 3 right; bits4–5 main cols 1–4; bits6–7 main rows 1–4; main always implied) |
| `0x0100`–`0x7FFF` | Standard catalogue (registry-governed) |
| `0x8000`–`0xEFFF` | Domain / application profiles |
| `0xF000`–`0xFFFE` | Experimental / private — not for interoperable mail |
| `0xFFFF` | Invalid / unknown sentinel |

**Canonical pane index order:** Header, Left aside, Main cells row-major (left→right,
top→bottom), Right aside, Footer, then a centered Overlay/island pane last. Only
existing panes consume indices; encoders open `STYLE_CONTAINER` for indices `0 ..
pane_count−1` in ascending order.

**Unknown LayoutID policy (clients MUST implement exactly this pair — no silent
fallback, no invented geometry):** if Required-Features **bit 11** (catalog layout) is
set → **fail closed**: show labeled plain-text extraction with a "needs newer layout
catalogue" notice. If bit 11 is not set → render as `LayoutID 0x0000` (single main flow
in stream order) with a notice that the intended layout is unavailable.

**Starter catalogue** (`cbdf-layout-catalog-v1.json`, shipped with clients): 612 layout
records — `0x0000`–`0x00FF` legacy (256) + `0x0100`–`0x0131` named desktop starters
(50, e.g. `0x0101` `email-header-footer`, `0x0122` `holy-grail`, `0x012D`
`inbox-list-detail`) + `0x0200`–`0x02FF` mobile stacks for legacy + `0x0300`–`0x0331`
mobile stacks for named. Every desktop layout has `pair.mobile_layout_id`; mobile
re-stacks to one column (`header → main cells → left → right → footer → overlay`);
default breakpoint **768 CSS px**. A client MAY keep the desktop ID on the wire and
switch rendering to the paired mobile ID at the breakpoint. Nav is content inside a
pane (an `ITEM_BLOCK` of type 2 in the `nav_host` pane), never a layout bit. The
registry is append-only; new IDs take the next free `0x0100+` (desktop) / `0x0300+`
(mobile) slot. New layouts may be submitted to the standard catalogue (the source
notes a $45 listing fee) and, in Phase III, resolved on demand via [DRD/1.0] when not
in a client's local cache.

#### 4.4.7 Logic section (Phase III)

The fifth section is reserved for executable code (planned: BEAM/Elixir bytecode,
actor/supervisor model, element CRUD via stable Element IDs, events, modal/layer
control, form validation). In Phase II its length is always 0 and a non-zero length is
a hard failure. Control codes `0x05`–`0x08`, `0x18`, and `0x1B` (ESCAPE) are reserved
for Phase III (§4.5.1).

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
- **CBDF Style Sub-table registry** — the 12 sub-tables and their record layouts/tiers
  (§4.4.2–§4.4.3); **Font-Effect-ID registry** (§4.7 / §4.4.3); **Layer-ID registry**
  (§4.4.4); allocation policy *Specification Required*.
- **CBDF LayoutID registry** and **Layout Catalogue** (`cbdf-layout-catalog-v1.json`),
  plus the **Font Table** — versioned **outside** the format, append-only, jointly
  governed (CloudCoin Consortium, Perfect Money Foundation, RAIDA Group); referenced by
  ID + table version. LayoutIDs `0xF000`–`0xFFFE` are private/experimental (never
  interoperable mail). In Phase III, unknown LayoutIDs may be resolved via [DRD/1.0].
- **CBDF Extension-Section-ID registry** — §4.10; ID 1 reserved (Phase III Parse Index).

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
