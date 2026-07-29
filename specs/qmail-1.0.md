# QMail/1.0 — QMail Email System

- **Standard ID:** QMail
- **Version:** 1.0
- **Status:** Draft (skeleton — not stable)
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on (by ID + version):** `CBDF/1.0`, `RKE/1.0`, `DRD/1.0`.

> **Layering rule:** QMail references the three sub-standards by ID + version and
> does NOT inline them. Each versions independently. If QMail needs behavior from a
> newer sub-standard version, QMail bumps its own dependency reference.

## 1. Abstract

QMail is an open email system: how messages are addressed, secured, transported,
and delivered. It composes three lower-layer standards — CBDF (encoding), RKE (key
exchange), and DRD (directory) — into a complete mail system. *(One paragraph.)*

## 2. Status & terminology

This document is a Draft and is not stable.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

Message structures are encoded with [CBDF/1.0]; security associations use
[RKE/1.0]; resource resolution uses [DRD/1.0].

## 3. Scope / non-goals

**In scope:** the mail message model, addressing, the submission/delivery
protocol, and how QMail invokes RKE and DRD.

**Non-goals:** re-specifying encoding, key exchange, or directory behavior — those
are CBDF, RKE, and DRD respectively. QMail only defines how it *uses* them.

## 4. Normative definitions

### 4.1 Message model (CBDF-encoded)
- TODO: envelope, headers, body/parts, attachments — as CBDF structures.

### 4.2 Addressing
- TODO: address syntax and how it resolves via DRD.

### 4.3 Security associations
- TODO: how QMail establishes keys via RKE; what is signed/encrypted.

### 4.4 Submission & delivery protocol
- TODO: the transport-level exchange, states, acknowledgements, error handling.

### 4.5 Use of sub-standards (version binding)
- TODO: state exactly which versions are required and how a QMail endpoint
  advertises/negotiates sub-standard versions.

## 5. Security considerations

**Mandatory.**
- Threat model: TODO (spoofing, interception, replay, metadata privacy, spam/abuse).
- End-to-end vs. hop-by-hop guarantees: TODO.
- Inherited considerations: this section MUST reference the security
  considerations of CBDF, RKE, and DRD and state any QMail-specific composition
  risks. TODO.

## 6. IANA / registry considerations

- URI scheme: **`qmail:`** — TODO: register (template in `../registries/`).
- Media type: **`application/qmail`** — TODO: register.
- TCP/UDP port (if QMail has its own transport): TODO: request allocation.
- Any QMail-defined registries (header fields, etc.): TODO, with allocation policy.

## 7. References

**Normative**
- [RFC 2119]
- [CBDF/1.0] — `./cbdf-1.0.md`
- [RKE/1.0] — `./rke-1.0.md`
- [DRD/1.0] — `./drd-1.0.md`

**Informative**
- TODO: Internet Message Format (RFC 5322), SMTP (RFC 5321) — for comparison.

## 8. Appendix: test vectors

End-to-end message encodings and protocol exchanges live in
[`../test-vectors/qmail/`](../test-vectors/qmail/).
