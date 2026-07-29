# RKE/1.0 — Raida Key Exchange (RAIDA Group 15)

- **Standard ID:** RKE
- **Version:** 1.0
- **Status:** Draft
- **Source:** Ported from the CloudCoin RKE Services documentation (`rke-overview`,
  `rke-preload-master-key`, `rke-get-key-share`), which are wire-format references
  authored from the RAIDA server implementation (`rke_preload.c`, `rke_keyshare.c`).
  Where this document and the source disagree, that is a porting bug to fix.
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on:** the **RAIDA protocol** request/response framing and coin
  authentication (big-endian wire). RKE does **not** use CBDF encoding.

> **Scope/dependency correction:** an earlier scaffolding note assumed "all RKE
> messages are CBDF-encoded." They are not. RKE is a RAIDA protocol command group with
> its own big-endian binary bodies terminated by the RAIDA `3E 3E` trailer. CBDF
> (little-endian document encoding) and RKE (big-endian RAIDA wire) are independent;
> QMail composes both. Multi-byte integer byte order therefore differs between the two
> standards — convert at the boundary.

## 1. Abstract

RKE (Raida Key Exchange) is the RAIDA protocol command group — **Group 15** in the
audited server dispatch table — for **remote key establishment**. A content server
*preloads* master-key material into the RAIDA network (`preload_master_key`, cmd 01);
clients later *retrieve a key share* from a RAIDA (`get_key_share`, cmd 02). Because
material is distributed across the RAIDA rather than held by any single server, no one
server holds the whole key. RKE is the live, current key-establishment surface; older
public-key-exchange material (Group 4) is dormant and out of scope.

## 2. Status & terminology

This document is a Draft and is not stable.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

**Byte order.** RKE bodies use the RAIDA protocol convention: multi-byte integers are
**big-endian** (contrast [CBDF/1.0], which is little-endian). The get_key_share
timestamp is explicitly big-endian.

**Coin authentication.** RKE requests authenticate the caller by a CloudCoin coin
identified by coin type, denomination, and serial number, proven with a 16-byte
Authenticity Number (AN). This is the standard RAIDA coin-authentication model.

**RAIDA trailer.** Request and response bodies end with the two-byte RAIDA trailer
`3E 3E`.

## 3. Scope / non-goals

**In scope:** the Group 15 command set (`preload_master_key`, `get_key_share`), their
request/response body byte layouts, the authenticated preamble, and how RKE bodies are
framed within the RAIDA protocol.

**Non-goals:** the RAIDA request/response **header** itself (command-group/command
bytes, routing, encryption selection — defined by the RAIDA protocol, referenced
here); RAIDA **encryption types** (referenced); the dormant **Group 4**
public-key-exchange; document encoding (see [CBDF/1.0]); directory/addressing (see
[DRD/1.0]); mail semantics (see [QMail/1.0]).

## 4. Normative definitions

### 4.1 Command group and framing

RKE commands are RAIDA protocol requests. The RAIDA request header carries the
**command group = 15** (the command-group byte, request header byte 4, from the RAIDA
`COMMAND_GROUP` enum) and the **command code** within the group:

| Code | Command | Direction |
|----|----|----|
| 01 | `preload_master_key` | content server → RAIDA (stage material) |
| 02 | `get_key_share` | client → RAIDA (retrieve a share) |

The layouts in §4.3–§4.4 describe the request/response **body** that follows the RAIDA
header. Every body ends with the RAIDA trailer `3E 3E`. Requests are carried in RAIDA
encryption **envelope types** (see §4.5); the RAIDA header and encryption framing are
defined by the RAIDA protocol and are normatively referenced, not redefined here.

### 4.2 Coin-authenticated preamble (48 bytes)

Per the source overview, modern RKE requests begin their body with a 48-byte
authenticated preamble that identifies the coin used for the operation and provides
replay protection:

| Offset | Size | Field | Notes |
|----|----|----|----|
| 0 | 16 | CH — Challenge | replay protection (per-request nonce) |
| 16 | 8 | Session ID | |
| 24 | 2 | CT — Coin type / network id | CloudCoin = `00 06` (cf. [CBDF/1.0] mailbox coin-group) |
| 26 | 1 | DN — Denomination | |
| 27 | 4 | SN — Serial number | coin identity = CT ‖ DN ‖ SN (7 bytes) |
| 31 | 1 | DV | source labels this "DV"; exact meaning not stated in source — **confirm** |
| 32 | 16 | AN — Authenticity Number | 16-byte coin authenticator |

The coin identity `CT‖DN‖SN` (2+1+4 = 7 bytes) matches the 7-byte mailbox form in
[CBDF/1.0] §4.3.5, so RKE and QMail identify coins the same way.

> **Discrepancy to reconcile (do not silently harmonize):** the overview states a
> single 48-byte "universal preamble," but the `get_key_share` body (§4.4) is a
> *different* 46-byte layout (Challenge + Content Server ID + KID + Client SN +
> Timestamp) and `preload_master_key` (§4.3) leads with a length-prefixed Content
> Server ID rather than the preamble. This draft documents each command's body exactly
> as its source page specifies and flags the mismatch for the implementers to resolve
> (either the commands adopt the universal preamble, or the overview is scoped to the
> commands that actually use it).

### 4.3 `preload_master_key` (Group 15, code 01)

Stages master-key material on the RAIDA so that later share-retrieval requests have
something to resolve. Authored from `rke_preload.c`. Request body:

| Offset | Size | Field | Notes |
|----|----|----|----|
| 0 | 4 | CSID Len | length of the Content Server ID, big-endian |
| 4 | var | Content Server ID | scopes the key-material set |
| … | 1 | NS | number of key records that follow (inferred from label — **confirm**) |
| … | — | Key records × NS | packed; each record is `[KID:1][Master Secret:32]` |
| end | 2 | `3E 3E` | RAIDA trailer |

- Each **key record** carries a 1-byte Key ID (KID) and a **32-byte** master secret.
- Accepted in RAIDA envelope **Type 0 or Type 1** (the live handler accepts both).
- The Content Server ID is **variable-length** here (length-prefixed), unlike the
  fixed 16-byte Content Server ID in `get_key_share` (§4.4) — noted, not reconciled.

### 4.4 `get_key_share` (Group 15, code 02)

Returns a key share from the staged material — the retrieval half of the flow.
Authored from `rke_keyshare.c`. Request body (46 bytes + trailer):

| Offset | Size | Field | Notes |
|----|----|----|----|
| 0 | 16 | Challenge | replay protection |
| 16 | 16 | Content Server ID | fixed 16 bytes (cf. variable in §4.3) |
| 32 | 1 | KID — Key ID | which staged key to draw a share of |
| 33 | 5 | Client SN | client serial number (5 bytes) |
| 38 | 8 | Timestamp | **big-endian** |
| 46 | 2 | `3E 3E` | RAIDA trailer |

Response body:

| Offset | Size | Field | Notes |
|----|----|----|----|
| 0 | 1 | SK — key share | the 1-byte key-share value |
| 1 | 2 | `3E 3E` | RAIDA trailer |

- Accepted in RAIDA envelope **Type 0, Type 1, or Type 5**.
- Request maps to the `rke_keyshare_req_t` structure in the implementation.
- On success the RAIDA returns a **1-byte** key share; a client assembles the master
  key from shares collected across RAIDA servers (the "Raida Key Exchange").

### 4.5 Envelope types and encryption

RKE requests are carried in RAIDA encryption envelopes (Type 0 / 1, and Type 5 for
`get_key_share`). The envelope/encryption definitions belong to the RAIDA protocol
(see References) and are not redefined here. The AN in the preamble (§4.2) and the
per-request Challenge / Timestamp provide authentication and replay protection.

## 5. Security considerations

**Mandatory.**

- **Replay protection.** Each request carries a per-request Challenge (and, for
  `get_key_share`, a big-endian Timestamp). Servers MUST reject stale or replayed
  challenges; clients MUST NOT reuse a challenge. Clock-skew tolerance for the
  timestamp MUST be bounded and specified by deployments.
- **Coin authentication.** The 16-byte AN authenticates the caller's coin (§4.2). A
  request whose AN does not authenticate against the identified coin MUST be rejected.
- **Distributed trust.** Master-key material is split across the RAIDA; no single
  server should be able to reconstruct the master key from the shares it holds. The
  threshold/reconstruction rule (how many shares reconstruct the key) is **not stated
  in the source** and MUST be specified before 1.0 — it is the crux of the security
  model.
- **Master-secret handling.** `preload_master_key` transmits 32-byte master secrets;
  they MUST travel only inside an encrypted RAIDA envelope (§4.5) and MUST NOT be
  logged or persisted in the clear.
- **Confidentiality of shares.** `get_key_share` responses (the 1-byte SK) MUST be
  returned only inside an encrypted envelope to the authenticated caller.
- **Byte-order boundary.** RKE is big-endian; CBDF is little-endian. Implementations
  bridging QMail must convert at the boundary and MUST NOT reinterpret one as the other.
- **Dormant surfaces.** Group 4 public-key-exchange is dormant and MUST NOT be exposed
  as if it were the live RKE surface.

## 6. IANA / registry considerations

- **RAIDA Command-Group registry** — RKE is **Group 15**; codes 01 (`preload_master_key`)
  and 02 (`get_key_share`). This registry is the RAIDA `COMMAND_GROUP` enum; RKE
  reserves group 15 and these codes. Allocation policy for new RKE command codes:
  *Specification Required*.
- **Coin identification** — CT/DN/SN reuse the CloudCoin coin-group value (`00 06`),
  shared with [CBDF/1.0] mailboxes and [DRD/1.0]; not an RKE-private registry.
- **RAIDA envelope types** — owned by the RAIDA protocol, referenced here.
- No URI scheme, media type, or port is defined by RKE itself (it rides on the RAIDA
  protocol transport).

> **TODO:** register the DV field's meaning (§4.2) and the NS field (§4.3) once
> confirmed with the implementers; reconcile the preamble discrepancy (§4.2).

## 7. References

**Normative**
- [RFC 2119] Key words for Requirement Levels.
- **RAIDA protocol** — request/response header format (command-group/command bytes,
  routing) and **encryption types** (envelope Types 0/1/5). *(CloudCoin RAIDA protocol
  documentation; candidate to become a normative in-repo standard.)*
- [CBDF/1.0] — `./cbdf-1.0.md` (shared 7-byte coin identity; opposite byte order).

**Informative**
- Original CloudCoin RKE Services pages: `rke-overview`, `rke-preload-master-key`,
  `rke-get-key-share`.
- RAIDA server implementation: `rke_preload.c`, `rke_keyshare.c` (`rke_keyshare_req_t`).

## 8. Appendix: test vectors

Vectors will live in [`../test-vectors/rke/`](../test-vectors/rke/) (currently empty).
Priority set for the first pass, following the [CBDF/1.0] vector format (JSON, one
object per vector, `bytes_hex` + annotated breakdown), all **big-endian**:

1. **48-byte authenticated preamble** — a coin identity (CT=`0006`, DN, SN) + Challenge
   + Session ID + AN → exact bytes and field offsets.
2. **`preload_master_key` request body** — one key record (`[KID][32-byte secret]`)
   with a sample Content Server ID → exact bytes, including CSID length prefix, NS, and
   the `3E 3E` trailer.
3. **`get_key_share` request body** — Challenge + 16-byte Content Server ID + KID +
   5-byte Client SN + big-endian Timestamp + `3E 3E` (46 + 2 bytes).
4. **`get_key_share` response body** — 1-byte SK + `3E 3E`.

Each vector MUST note the RAIDA envelope type it assumes and that the RAIDA header is
out of scope (supplied by the RAIDA protocol layer).
