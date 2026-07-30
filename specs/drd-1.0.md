# DRD/1.0 — Distributed Resource Directory (RAIDA Group 16)

- **Standard ID:** DRD
- **Version:** 1.0
- **Status:** Draft
- **Source:** Ported from the CloudCoin DRD documentation (`drd-overview` and the seven
  per-command pages), authored from the RAIDA server implementation (`cmd_drd.c`).
  Where this document and the source disagree, that is a porting bug to fix.
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on:** the **RAIDA protocol** request/response framing and coin
  authentication (big-endian wire). DRD does **not** use CBDF encoding.

> Like [RKE/1.0], DRD is a RAIDA protocol command group on the RAIDA **big-endian**
> wire, not a CBDF-encoded format. CBDF (little-endian document encoding) and DRD are
> independent; QMail composes both.

## 1. Abstract

DRD (Distributed Resource Directory) is the RAIDA protocol command group — **Group 16**
— that hosts a directory of QMail users. Each user publishes a small **public record**
(name, inbox fee, two avatar symbols, a class-rejection byte, and server-stamped
timestamps) keyed by their coin's denomination and serial number, and privately manages
a **white/black list** of other users. QMail consults the DRD to decide whether mail may
be sent and what inbox fee applies. Every RAIDA hosts its own independent copy of the
directory; there is no server-to-server synchronization, so clients write to all
servers and reconcile reads. (Server self-registration is a planned future use.)

## 2. Status & terminology

This document is a Draft and is not stable.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

**Byte order.** DRD bodies use the RAIDA convention: multi-byte integers are
**big-endian** (contrast [CBDF/1.0], little-endian).

**Identity (PQ).** A DRD identity is a coin, addressed by its **PQ**: a 1-byte signed
denomination (−8…+6) followed by a 4-byte big-endian serial number — the standard
5-byte RAIDA coin address. (Note: this omits the 2-byte coin-group present in the
[CBDF/1.0] 7-byte mailbox and the [RKE/1.0] preamble; the coin group is implied.)

**Authentication (AN).** Commands that change a record, and the private list read,
carry the owner's 16-byte Authenticity Number; the server verifies it against the
stored AN for that PQ in the coin database — the same check `detect` (Group 1, cmd 10)
performs. Read commands `get_user`/`search_users` carry no AN.

**RAIDA trailer.** Every request body ends with the two-byte trailer `3E 3E`.

## 3. Scope / non-goals

**In scope:** the Group 16 command set (codes 140–146), their request/response body
byte layouts, the user and list-entry record formats, the fee / class-rejection /
symbol / timestamp encodings, status codes, and the client-driven distribution model.

**Non-goals:** the RAIDA request/response **header** and **encryption** envelopes
(defined by the RAIDA protocol, referenced here); the coin-authentication mechanism
itself (`detect`, referenced); document encoding (see [CBDF/1.0]); mail transport and
the Tell gate that *enforces* fees and class rejection (see [QMail/1.0]).

## 4. Normative definitions

### 4.1 Data model and distribution

Each RAIDA keeps its own copy of two tables:

- **Users** — one public record per identity coin (§4.4.1).
- **White/black lists** — private per-owner entries naming other users. A whitelisted
  sender may send QMail with no inbox fee; a blacklisted sender is denied.

Records are retrievable three ways: exact key lookup by PQ (`get_user`), and
case-insensitive **prefix** search by first and/or last name (`search_users`).

**Distribution is client-driven** — there is no server-to-server sync:
- **Writes:** send the same command to all 25 RAIDAs in parallel.
- **Reads:** query one or a few; compare if it matters.
- **Repair:** if servers disagree, re-post to the servers that are behind.

A `get_user`/`search_users` miss on one RAIDA (`ERROR_NO_ENTRY` / empty) does not prove
a user is unregistered — a client SHOULD query several servers before concluding.

### 4.2 Identity, authentication, and the request challenge

Every request body begins with a **16-byte challenge**: 12 client-random bytes followed
by their **4-byte big-endian CRC32** (bytes 0–11 hashed → bytes 12–15). This provides
per-request freshness/integrity.

Write commands (140, 143, 144, 145) and the private read (146) then carry the owner's
PQ (DN + SN) and 16-byte AN. An AN mismatch returns `ERROR_INVALID_AN` (200) and nothing
is written; a PQ the RAIDA does not hold returns `ERROR_INVALID_SN_OR_DENOMINATION`
(40). `get_user` (141) and `search_users` (142) carry no AN and are open to everyone.

### 4.3 Common field encodings

- **Inbox fee** — 8-byte big-endian **signed** int64 counting 10⁻⁸ CC units
  (`fee_units = fee_CC × 100 000 000`); no floating point. Examples: `10992.934002 CC →
  00 00 00 FF F2 FE 1C 88`; `0.00000001 CC → …01`; free `= 0`. Negative fees are
  rejected (`ERROR_INVALID_PARAMETER`); more than 8 fractional digits cannot be
  represented and MUST NOT be sent. A recipient with **no DRD record** is charged a
  server-configured **default Tell fee** (default 10 CC) — posting any explicit fee,
  including 0, overrides it (enforced at the QMail Tell gate, see [QMail/1.0]).
- **Class rejection (CR)** — 1 signed byte: the minimum sender-address denomination the
  user will accept. `0x00` = accept all (default, filtering disabled); otherwise a
  denomination in −8…+6, rejecting senders **below** it by signed comparison (`0xFF` =
  −1 = 0.1 CC ranks *below* `0x00`). Enforced at the Tell gate →
  `ERROR_SENDER_CLASS_REJECTED` (237); a whitelist entry bypasses the check.
- **Avatar symbols** — two 1-byte indices into a client-shipped 256-entry SVG symbol
  table. Stored/returned verbatim; the server never validates them (any 0–255 legal).
- **Timestamps** — `created_at` / `updated_at`, 8-byte big-endian Unix seconds.
  `created_at` is stamped on first post and **never changed** by later updates (an
  anti-scam account-age signal); `updated_at` refreshes on every post. Only delete +
  re-post resets `created_at`.
- **Names** — UTF-8, length-prefixed (1-byte length 0–63), no NUL terminator.

### 4.4 Record formats

#### 4.4.1 User record (34 + name bytes) — returned by `get_user` / `search_users`

| Offset | Size | Field |
|----|----|----|
| 0 | 1 | Denomination (signed) |
| 1 | 4 | Serial Number (BE) |
| 5 | 8 | Inbox fee (BE signed, 10⁻⁸ CC) |
| 13 | 1 | First symbol |
| 14 | 1 | Second symbol |
| 15 | 1 | Class rejection |
| 16 | 8 | `created_at` (BE Unix seconds) |
| 24 | 8 | `updated_at` (BE Unix seconds) |
| 32 | 1 | First-name length (FL, 0–63) |
| 33 | FL | First name (UTF-8) |
| 33+FL | 1 | Last-name length (LL, 0–63) |
| 34+FL | LL | Last name (UTF-8) |

#### 4.4.2 List entry

6 bytes in storage / `list_get` / `list_set`: `[Listed DN:1][Listed SN:4 BE][List
Type:1]`, where List Type `0x00` = whitelist, `0x01` = blacklist. `list_remove` entries
are **5 bytes** (no type byte — removal ignores type). A user cannot be on both lists;
setting an existing entry with a different type moves them.

### 4.5 Commands (Group 16)

Command codes 140–146 are unique across all RAIDA groups. Each command's body follows
the RAIDA header and ends with `3E 3E`. `challenge(16)` is per §4.2.

| Code | Hex | Command | Auth | Request body | Success response |
|----|----|----|----|----|----|
| 140 | 0x8C | `post_user` | Owner AN | `challenge(16)` DN(1) SN(4) AN(16) fee(8) S1(1) S2(1) CR(1) FL(1) first LL(1) last `3E3E` — 52…178 B | 250, no payload |
| 141 | 0x8D | `get_user` | none | `challenge(16)` DN(1) SN(4) `3E3E` — exactly 23 B | 250 + one user record (§4.4.1); 193 if absent |
| 142 | 0x8E | `search_users` | none | `challenge(16)` flags(1) limit(1) [FL(1) first] [LL(1) last] `3E3E` — ≥22 B | 250 + count(1) + records |
| 143 | 0x8F | `delete_user` | Owner AN | `challenge(16)` DN(1) SN(4) AN(16) `3E3E` — exactly 39 B | 250; 193 if absent |
| 144 | 0x90 | `list_set` | Owner AN | `challenge(16)` DN(1) SN(4) AN(16) N×`[LDN(1) LSN(4) TY(1)]` `3E3E` — 39+6N B | 250, no payload |
| 145 | 0x91 | `list_remove` | Owner AN | `challenge(16)` DN(1) SN(4) AN(16) N×`[LDN(1) LSN(4)]` `3E3E` — 39+5N B | 250, no payload |
| 146 | 0x92 | `list_get` | Owner AN | `challenge(16)` DN(1) SN(4) AN(16) `3E3E` — exactly 39 B | 250 + count(2 BE) + N×6-byte entries |

Per-command notes:

- **`post_user`** — upsert keyed by PQ: creates the record or replaces every field
  **except `created_at`**. Fields at body offsets: fee@37, S1@45, S2@46, CR@47, FL@48.
  Min 52 bytes (both names empty); max 178 (52 + 63 + 63). No create/update distinction
  in the response.
- **`search_users`** — flags bit 0 = first-name field present, bit 1 = last-name
  present; at least one MUST be set (`0x00` → `ERROR_INVALID_PARAMETER`). `limit` 0 or
  >50 is clamped to the server cap of **50**. Matching is case-insensitive **prefix**
  (no substring, no wildcards — `%` `_` `\` are literal). With both names, a record must
  match both. Response count is **1 byte**; records are variable-length (parse FL/LL).
- **`list_set`** — the entry region MUST be a whole multiple of 6 bytes
  (`ERROR_COINS_NOT_DIV` / 39 otherwise); all entries are validated before any write (a
  bad `TY` rejects the whole batch). Listed users are **not** validated — you may list a
  coin with no directory record.
- **`list_remove`** — 5-byte entries (multiple of 5); idempotent (removing an absent
  entry is not an error); does not report which entries existed.
- **`list_get`** — private; requires owner AN (no public form). Count is **2-byte
  big-endian** (list cap **1000**); entries sorted by listed DN then SN.

### 4.6 Status codes (RAIDA `protocol.h` enum)

| Dec | Hex | Symbol | Meaning |
|----|----|----|----|
| 250 | 0xFA | `STATUS_SUCCESS` | Command completed. |
| 16 | 0x10 | `ERROR_INVALID_PACKET_LENGTH` | Body too short, or trailing bytes after the last defined field. |
| 36 | 0x24 | `ERROR_EMPTY_REQUEST` | No body at all. |
| 39 | 0x27 | `ERROR_COINS_NOT_DIV` | Batch region not a whole number of entries (144: 6 B; 145: 5 B). |
| 40 | 0x28 | `ERROR_INVALID_SN_OR_DENOMINATION` | Authenticating PQ is not a coin this RAIDA holds. |
| 193 | 0xC1 | `ERROR_NO_ENTRY` | Requested record/entry does not exist. |
| 198 | 0xC6 | `ERROR_INVALID_PARAMETER` | Field validation failed (negative fee, bad CR, name >63, bad list type, empty search). |
| 200 | 0xC8 | `ERROR_INVALID_AN` | Presented AN does not match the stored AN; nothing written. |
| 252 | 0xFC | `ERROR_INTERNAL` | Server-side database failure. |
| 254 | 0xFE | `ERROR_MEMORY_ALLOC` | Server allocation failure. |

## 5. Security considerations

**Mandatory.**

- **Ownership authentication.** Writes and the private list read require the owner's AN,
  verified against the coin database like `detect`. A mismatch MUST write/reveal nothing
  and return `ERROR_INVALID_AN` — including for `list_get`, which MUST NOT even disclose
  whether a list exists to a non-owner.
- **Request freshness/integrity.** The 16-byte challenge (12 random + BE CRC32) provides
  per-request integrity; servers SHOULD reject a malformed CRC. (The source does not
  specify server-side replay caching — deployments SHOULD define anti-replay handling.)
- **Privacy of the social graph.** White/black lists are private because they expose a
  user's relationships and disputes. Note the DRD still leaks *indirectly* whether a
  specific sender is allowed via observable QMail behavior (accepted / fee-waived /
  denied); it only refuses to *enumerate* a list to third parties.
- **Anti-scam account age.** `created_at` MUST be preserved across updates; clients
  SHOULD surface account age so users can spot freshly minted look-alike accounts.
  Delete + re-post resets it — a client SHOULD warn before deleting.
- **Anti-spam gating.** The inbox fee, the default Tell fee for unregistered users, and
  the class-rejection floor are the spam controls; a whitelist bypasses fee and class
  checks. Enforcement is at the QMail Tell gate (see [QMail/1.0]), not in the DRD itself.
- **Signed comparisons.** Denomination and class-rejection bytes are **signed** (−8…+6);
  `0xFF` is −1, below `0x00`. Implementations MUST use signed comparison or they will
  mis-rank low denominations.
- **Distribution consistency.** Because each RAIDA is independent and unsynchronized, a
  client MUST NOT treat a single server's answer as authoritative for security decisions
  (e.g. "user is unregistered"); query a quorum.
- **Byte-order boundary.** DRD is big-endian; CBDF is little-endian — convert at the
  QMail boundary and never reinterpret one as the other.
- **Input validation.** Reject bodies whose declared name/entry lengths do not exactly
  fill the body (`ERROR_INVALID_PACKET_LENGTH` / `ERROR_COINS_NOT_DIV`) to avoid
  over-read.

## 6. IANA / registry considerations

- **RAIDA Command-Group registry** — DRD is **Group 16**; command codes **140–146**
  (`post_user`, `get_user`, `search_users`, `delete_user`, `list_set`, `list_remove`,
  `list_get`). This is the RAIDA `COMMAND_GROUP` enum; DRD reserves group 16 and these
  codes. New DRD command codes: allocation policy *Specification Required*.
- **RAIDA status-code enum** (`protocol.h`) — DRD uses the shared status codes in §4.6;
  the QMail Tell gate adds `ERROR_SENDER_CLASS_REJECTED` (237). Not DRD-private.
- **Avatar symbol table** — the 256-entry client SVG symbol set is versioned **outside**
  the format (shipped with clients), append-only; referenced by index.
- **Coin identification** — DRD's 5-byte PQ (denomination + serial) reuses the CloudCoin
  coin address shared with [CBDF/1.0] and [RKE/1.0]; not an DRD-private registry.
- No URI scheme, media type, or port is defined by DRD itself (it rides on the RAIDA
  transport).

## 7. References

**Normative**
- [RFC 2119] Key words for Requirement Levels.
- **RAIDA protocol** — request/response header (command-group/command bytes) and
  encryption envelopes; the `detect` coin-authentication check (Group 1, cmd 10); the
  status-code enum (`protocol.h`). *(CloudCoin RAIDA protocol documentation.)*
- [QMail/1.0] — `./qmail-1.0.md` (the Tell DRD gate that enforces inbox fee, default
  Tell fee, and class rejection; `ERROR_SENDER_CLASS_REJECTED`).
- [CBDF/1.0] — `./cbdf-1.0.md` (shared coin identity; opposite byte order).

**Informative**
- Original CloudCoin DRD pages: `drd-overview`, `drd-post-user`, `drd-get-user`,
  `drd-search-users`, `drd-delete-user`, `drd-list-set`, `drd-list-remove`,
  `drd-list-get`.
- RAIDA server implementation: `cmd_drd.c` (`cmd_drd_post_user`, … `cmd_drd_list_get`).

## 8. Appendix: test vectors

Vectors will live in [`../test-vectors/drd/`](../test-vectors/drd/) (currently empty),
following the [CBDF/1.0] vector format (JSON, one object per vector, `bytes_hex` +
annotated breakdown), all **big-endian**. Priority set:

1. **Fee encoding** — `10992.934002 CC`, `0.00000001 CC`, `0 CC`, and a rejected
   negative fee → exact 8-byte big-endian units.
2. **Challenge** — 12 fixed "random" bytes + their big-endian CRC32 → the 16-byte block.
3. **`get_user` request** (23 B) and a **user record** response (34 + names) with sample
   name/fee/symbols/CR/timestamps → exact bytes and offsets.
4. **`post_user` request** — minimal (empty names, 52 B) and a named example.
5. **`list_set` / `list_remove`** — a 2-entry batch each (6-byte vs 5-byte entries),
   exercising the multiple-of-N length rule.
6. **`list_get` response** — 2-byte big-endian count + entries, including the empty list.
7. **Class-rejection signed comparison** — `0x00`, `0x01`, `0xFF` (−1), `0xF8` (−8) →
   which sender denominations pass/fail.

Each vector MUST note the RAIDA envelope/encryption type it assumes; the RAIDA header is
out of scope (supplied by the RAIDA protocol layer).
