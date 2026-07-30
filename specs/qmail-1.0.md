# QMail/1.0 — QMail Email System (RAIDA Group 6)

- **Standard ID:** QMail
- **Version:** 1.0
- **Status:** Draft
- **Source:** Ported from the CloudCoin QMail documentation (`protocol/qmail-overview`,
  `qmail-tell`, `qmail-upload`, and the ping/peek/download/object-transfer pages;
  authored from `cmd_qmail.c`). Where this document and the source disagree, that is a
  porting bug to fix.
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on (by ID + version):** [CBDF/1.0] (message encoding), [DRD/1.0] (directory
  / anti-spam gating), [RKE/1.0] (key establishment; see §4.7). QMail is the umbrella
  that composes the three; it references them by ID + version and does not inline them.

> **Two byte-order worlds (see [CBDF/1.0], [DRD/1.0]).** The QMail protocol wire — the
> RAIDA packet header, the 48-byte preamble, and the Tell/manifest structures — is
> **big-endian** (RAIDA convention). The message *payload* is a **CBDF document**, which
> is **little-endian** internally. Convert at the boundary; never reinterpret one as the
> other.

## 1. Abstract

QMail is an open, quantum-safe email system: a RAIDA store-and-forward messaging service
(**command Group 6**) in which a message is encoded as a [CBDF/1.0] document, split into
error-coded stripes across storage RAIDAs, announced to the recipient's *beacon* RAIDA
with a public **Tell**, and later retrieved by the recipient (via *ping*/*peek* +
*download*) and reassembled locally. Human-readable content (subject, body, attachments)
is CBDF; routing, storage locations, sizes/checksums, and the inbox-fee locker travel in
the public Tell. Anti-spam controls (inbox fee, sender class, white/black lists) are
enforced at the beacon's **DRD gate** ([DRD/1.0]). Identities are CloudCoin coins,
authenticated per RAIDA by a 16-byte Authenticity Number (AN).

## 2. Status & terminology

This document is a Draft and is not stable.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

**Byte order.** RAIDA protocol structures are big-endian; CBDF payloads are
little-endian (§1 note).

**Identity.** A QMail mailbox is a coin: coin type (`00 06`) + 1-byte signed
denomination (−8…+6) + 4-byte big-endian serial number — the same coin identity used by
[CBDF/1.0] mailboxes, [RKE/1.0], and [DRD/1.0]. Per-RAIDA authentication uses the coin's
16-byte AN.

**Layering rule (normative).** QMail references [CBDF/1.0], [RKE/1.0], and [DRD/1.0] by
ID + version and MUST NOT inline them. Adopting a newer sub-standard version is a QMail
dependency-version change.

## 3. Scope / non-goals

**In scope:** the QMail RAIDA command group (Group 6) and its lifecycle (upload, tell,
ping, peek, download, resumable object transfer); the 48-byte request preamble; the
object/file-type model and how it maps onto CBDF sections; the Tell manifest and the DRD
gate; wire encryption/authentication; status codes.

**Non-goals:** redefining message encoding (see [CBDF/1.0]), the directory service and
its records (see [DRD/1.0]), or remote key establishment (see [RKE/1.0]); the base RAIDA
packet header and encryption primitives (RAIDA protocol, referenced); and the client
application's local REST/DB API (an implementation surface, not the interop protocol).

## 4. Normative definitions

### 4.1 Architecture and end-to-end flow

QMail is store-and-forward. A message object is split into **stripes** (typically 7 data
+ 1 parity) and one stripe is stored on each of 8 storage RAIDAs. The sender then sends a
**Tell** to the recipient's **beacon** — a single RAIDA agreed in advance with the
recipient — announcing that mail is waiting. The recipient long-polls (*ping*) or
non-blocking-checks (*peek*) the beacon, downloads the private meta object first, then
reassembles body and attachments locally.

```
Sender            Storage RAIDAs (x8)          Beacon RAIDA            Recipient
  |-- upload 70/75 -->| one stripe/page each         |                      |
  |-------------------- tell 71 ---------------------->|                     |
  |                                                    |<-- ping 72 / peek 73 |
  |                                                    |-- 250 + tell blob -->|
  |            <----------------- download 74 (per RAIDA, parallel) ----------|
  |            -- 250 + 256 KB page ------------------------------------------>|
                                                       (reassemble locally)
```

### 4.2 Command group (Group 6)

| Code | Command | Purpose |
|----|----|----|
| 70 | `upload` | One-shot upload of a small object stripe |
| 71 | `tell` | Announce waiting mail to the recipient's beacon (carries routing + manifest + fee locker) |
| 72 | `ping` | Recipient long-poll of the beacon for new Tells |
| 73 | `peek` | Recipient non-blocking check of the beacon |
| 74 | `download` | Fetch stored object pages (256 KB) from a storage RAIDA |
| 75 | `upload_large_page` | Additive page upload for large attachments |
| 76–84 | Object Transfer v1 | Stable resumable byte-range transfer, object info, capability discovery, owner-authorized deletion (see the Object Transfer overview) |

Per-command wire layouts live on their dedicated source pages and are referenced, not
reproduced in full here. Commands 70–75 are preserved for compatibility; 76–84 are the
stable resumable-transfer contract.

### 4.3 Universal preamble (48 bytes)

Every Group 6 request body begins with the same 48-byte preamble (the decrypted body's
first 48 bytes; distinct from the RAIDA packet header). Layout (`qmail_preamble_t`):

| Offset | Size | Field | Notes |
|----|----|----|----|
| 0 | 16 | Challenge | 12 random bytes + 4-byte **big-endian CRC32** of them (replay protection) |
| 16 | 8 | Session ID | all-zero for standard QMail encryption mode |
| 24 | 2 | Coin Type | fixed `00 06` (QMail/CloudCoin network ID) |
| 26 | 1 | Denomination | caller/mailbox coin denomination (signed, −8…+6) |
| 27 | 4 | Serial Number | caller/mailbox serial (big-endian) |
| 31 | 1 | Reserved | formerly Device ID; server reads and ignores; set 0 |
| 32 | 16 | Authenticity (AN) | caller's 16-byte AN for this RAIDA |

This is the same shared preamble structure used by [RKE/1.0]; byte 31 (reserved, formerly
Device ID) is the byte the RKE source labels "DV". `upload`, `tell`, `ping`, and `peek`
compare the preamble AN to the stored AN for the (denomination, serial) and reject a
mismatch with `ERROR_INVALID_AN`.

### 4.4 Object model and CBDF composition

A QMail message is a set of stored objects, each tagged by a **`file_type`** byte that
selects both a storage suffix and a CBDF role. The Tell manifest lists private meta
first, body second, then attachments; the recipient passes `file_type` back in
*download* to fetch a specific object.

| `file_type` | Suffix | Role |
|----|----|----|
| 0 | `.meta` | **Private CBDF Meta** (subject, preview, attachment names, display metadata) — see [CBDF/1.0] §4.3. Required. |
| 1 | `.qmail` | Body/content object (CBDF body: the content tail after the private meta). Required. |
| 2 | `.style` | CBDF Styles section ([CBDF/1.0] §4.4) |
| 3 | `.text` | CBDF Text section ([CBDF/1.0] §4.5) |
| 4 | `.resource` | CBDF Resources section ([CBDF/1.0] §4.8) |
| 5 | `.logic` | CBDF Logic section (Phase III) |
| 6–9 | `.blob` | Reserved |
| 10 | `.0.bin` | First attachment |
| 11+ | `.(N−10).bin` | Subsequent attachments |

**Public Tell vs. private meta (normative).** The Tell is visible to the beacon
operator and carries routing, server locations, object sizes/checksums, and the
inbox-fee locker. Human-readable fields — subject, filenames, labels, preview text —
are private CBDF metadata and MUST be placed in the `file_type=0` object, **not** in the
Tell. This is the privacy boundary between the transport announcement and the message.

### 4.5 Tell and the DRD gate

`tell` (71) delivers a routing header + per-recipient address entries + a file manifest
to the beacon. The sender pays each recipient's inbox fee by attaching a funded locker
key per address entry, mirrored into the routing header's `beacon_payment_locker` so the
beacon can validate the fee before accepting delivery.

Before writing to each recipient's inbox the beacon consults its [DRD/1.0] (Group 16)
data. The sender's identity is the AN-authenticated preamble coin (unspoofable). **Per
recipient, in order:**

1. **Blacklist** — sender on the recipient's list as black (`0x01`) → recipient skipped.
2. **Whitelist** — sender whitelisted (`0x00`) → delivers **free**: no locker, no fee, no
   class-rejection check.
3. **Class rejection** — recipient's DRD class-rejection byte is nonzero and the sender's
   address denomination is below it → refused with `ERROR_SENDER_CLASS_REJECTED` (237);
   paying more does not help (signed denomination comparison).
4. **Inbox fee** — otherwise the fee is the recipient's DRD record fee; a recipient with
   **no** DRD record is charged the beacon's configurable **default Tell fee** (10 CC) to
   stop serial-number spam sweeps. An explicit DRD fee of 0 is a deliberately free inbox.

With multiple recipients, allowed recipients still deliver and the Tell returns `250`.
Only when **zero** recipients deliver does the most specific failure win:
blacklisted > class-rejected > insufficient > payment-required > `ERROR_WRONG_RAIDA`.

### 4.6 Retrieval (ping / peek / download)

`ping` (72) long-polls the beacon (parking the connection until mail arrives); `peek`
(73) is a non-blocking check. Both return the pending Tell blob(s) — a response-array
header followed by 64-byte file headers. The recipient then issues `download` (74) to
each storage RAIDA in parallel, fetching 256 KB pages (the server hard-codes the page
size), and reassembles the CBDF object locally, correcting with the parity stripe if a
storage RAIDA is missing.

### 4.7 Encryption, authentication, and RKE relationship

Group 6 requests are encrypted at the wire level with the RAIDA 32-byte **AES-128**
packet header, keyed by the caller's selected coin AN; the preamble AN (§4.3) then
authenticates the mailbox against the stored per-RAIDA AN. Each RAIDA holds a *different*
AN for the same (denomination, serial) — the preamble MUST carry *this* RAIDA's AN.

**RKE relationship (to confirm).** The Group 6 commands documented here authenticate and
encrypt via the coin AN, not via [RKE/1.0] directly. RKE (remote key establishment,
Group 15) is a related service for staging master-key material across the RAIDA; its
precise integration point with QMail (e.g. content-server or shared-object key
distribution) is **not pinned down in the QMail protocol source** and MUST be specified
before 1.0. QMail lists RKE/1.0 as a dependency on that basis; do not assume Group 6
message encryption uses RKE.

### 4.8 Status codes (RAIDA `protocol.h` enum, QMail subset)

`250` `STATUS_SUCCESS`; `8` `ERROR_COIN_NOT_FOUND`; `16` `ERROR_INVALID_PACKET_LENGTH`;
`18` `ERROR_WRONG_RAIDA` (tell: zero deliveries); `34` `ERROR_INVALID_ENCRYPTION` (wire
decryption failed — often a zero-AN preamble); `40` `ERROR_INVALID_SN_OR_DENOMINATION`;
`194` `ERROR_FILESYSTEM`; `198` `ERROR_INVALID_PARAMETER`; `200` `ERROR_INVALID_AN`;
`202` `ERROR_FILE_NOT_EXIST` (download); `254` `ERROR_MEMORY_ALLOC`. **DRD-gate (tell):**
`167` `ERROR_PAYMENT_PROCESSING` (retryable fee-lookup failure); `168`
`ERROR_PAYMENT_INSUFFICIENT`; `169` `ERROR_PAYMENT_REQUIRED` (fee owed, no locker); `236`
`ERROR_SENDER_BLACKLISTED`; `237` `ERROR_SENDER_CLASS_REJECTED`.

## 5. Security considerations

**Mandatory.**

- **Mailbox authentication.** State-changing commands verify the preamble AN against the
  stored per-RAIDA AN; a mismatch MUST reject (`ERROR_INVALID_AN`). Clients MUST send the
  correct per-RAIDA AN, never a master key or another RAIDA's AN.
- **Replay protection.** The 16-byte challenge (random + BE CRC32) is per request;
  servers SHOULD reject a bad CRC. Deployments SHOULD define anti-replay handling (the
  source does not specify server-side challenge caching).
- **Privacy boundary.** Subject/filenames/preview/labels MUST live in the private
  `file_type=0` CBDF meta, never in the public Tell — the Tell is visible to the beacon
  operator. Violating this leaks message content to the transport.
- **Anti-spam gating.** Delivery is gated by the DRD (blacklist / whitelist / class
  rejection / inbox fee, §4.5). The default Tell fee for unregistered recipients is the
  control that prevents serial-number spam sweeps; disabling it (server config) reopens
  that vector.
- **Content authenticity.** The CBDF **claims vs. attestations** rule ([CBDF/1.0] §4.3.4)
  governs trust: the CBDF Meta is a sender claim; the Tell/RAIDA data is the attestation.
  Trust/"verified" UI MUST derive only from Tell-based attestations, and CBDF
  receiver-annotation keys MUST be stripped on the wire.
- **Signed denomination comparisons.** Class-rejection and denomination bytes are signed
  (`0xFF` = −1 ranks below `0x00`); use signed comparison at the gate.
- **Byte-order boundary.** RAIDA structures are big-endian, CBDF payloads little-endian;
  convert explicitly. Validate that declared object/manifest sizes match body length
  (`ERROR_INVALID_PACKET_LENGTH`).
- **Availability via erasure coding.** The 7+1 stripe layout tolerates one missing
  storage RAIDA; clients MUST verify checksums and reconstruct rather than trust a single
  storage server.

## 6. IANA / registry considerations

- **URI scheme:** `qmail:` — to register (mailbox addressing).
- **Media types:** `application/qmail` (a QMail message object) and `application/cbdf`
  (its CBDF encoding, see [CBDF/1.0]).
- **RAIDA Command-Group registry:** QMail is **Group 6**; command codes 70–84 (this
  document's §4.2). Allocation policy for new QMail command codes: *Specification
  Required*.
- **QMail `file_type` registry:** §4.4 (0 meta, 1 body, 2–5 CBDF sections, 6–9 reserved,
  10+ attachments).
- **RAIDA status-code enum** (`protocol.h`): the QMail subset in §4.8 plus the DRD-gate
  codes 236/237; shared, not QMail-private.
- **Ports:** QMail uses the RAIDA transport; any dedicated QMail/beacon port is a RAIDA
  protocol allocation, referenced here.

> **TODO:** confirm the RKE integration point (§4.7) and reserve any QMail-specific
> beacon port with the RAIDA protocol registry.

## 7. References

**Normative**
- [RFC 2119] Key words for Requirement Levels.
- [CBDF/1.0] — `./cbdf-1.0.md` (message/meta/body encoding; file-type → section mapping;
  claims-vs-attestations).
- [DRD/1.0] — `./drd-1.0.md` (the Tell DRD gate: blacklist/whitelist/class-rejection/fee).
- [RKE/1.0] — `./rke-1.0.md` (remote key establishment; shared 48-byte preamble).
- **RAIDA protocol** — packet header, AES-128 wire encryption, coin authentication
  (`detect`), and the status-code enum (`protocol.h`). *(CloudCoin RAIDA documentation.)*

**Informative**
- [RFC 5322] Internet Message Format, [RFC 5321] SMTP — for comparison.
- Original CloudCoin QMail pages: `qmail-overview`, `qmail-tell`, `qmail-upload`,
  `qmail-ping`, `qmail-peek`, `qmail-download`, the Object Transfer set. Server:
  `cmd_qmail.c`.

## 8. Appendix: test vectors

Vectors will live in [`../test-vectors/qmail/`](../test-vectors/qmail/) (currently
empty), following the [CBDF/1.0] vector format (JSON, one object per vector, `bytes_hex`
+ annotated breakdown). The QMail-layer bytes are **big-endian**; embedded message
payloads are CBDF (little-endian). Priority set:

1. **48-byte preamble** — challenge (12 fixed random + BE CRC32) + zero session + coin
   type `00 06` + denomination + serial + reserved 0 + AN → exact bytes and offsets
   (cross-check against the [RKE/1.0] preamble vector).
2. **`file_type` → object mapping** — a message split into `file_type` 0 (private CBDF
   Meta) and 1 (body), each a valid CBDF object (reuse the CBDF minimal-document vector).
3. **Tell manifest ordering** — private meta first, body second, one attachment
   (`file_type=10`).
4. **DRD-gate decision table** — per-recipient outcomes for blacklisted / whitelisted
   (free) / class-rejected (237) / fee-owed-no-locker (169) / no-DRD-record (default fee)
   → expected status, exercising the "zero delivered → most specific failure" rule.
5. **End-to-end status flow** — upload 250 → tell 250 → ping returns a Tell blob →
   download returns a 256 KB page (status transitions, headers only).

Each vector MUST note the RAIDA envelope/encryption assumptions; the base RAIDA packet
header is out of scope (supplied by the RAIDA protocol layer).
