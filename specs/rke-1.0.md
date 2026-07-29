# RKE/1.0 — Raida Key Exchange

- **Standard ID:** RKE
- **Version:** 1.0
- **Status:** Draft (skeleton — not stable)
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on:** `CBDF/1.0` (all RKE messages are CBDF-encoded).

## 1. Abstract

RKE is the key-exchange and trust-establishment protocol for the QMail family.
*(One paragraph: what RKE establishes, between whom, and its relationship to the
Raida.)*

## 2. Status & terminology

This document is a Draft and is not stable.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

All wire structures in this document are encoded with [CBDF/1.0].

## 3. Scope / non-goals

**In scope:** the key-exchange handshake, message formats, state machine, and the
cryptographic requirements for establishing keys.

**Non-goals:** the byte encoding itself (see CBDF), resource/endpoint discovery
(see DRD), and message/mail semantics (see QMail).

## 4. Normative definitions

### 4.1 Cryptographic primitives
- TODO: named suites (KEM/DH, hash, AEAD), identifiers, and negotiation.

### 4.2 Messages (CBDF-encoded)
- TODO: each handshake message, field by field, referencing CBDF types.

### 4.3 State machine
- TODO: states, transitions, timeouts, retransmission, and error handling.

### 4.4 Key schedule
- TODO: how exchanged material is turned into working keys; forward secrecy.

## 5. Security considerations

**Mandatory.**
- Threat model: TODO (active MITM, replay, downgrade, identity misbinding).
- Forward secrecy / post-compromise properties: TODO.
- Downgrade protection across negotiated suites: TODO.
- Dependence on CBDF canonical form for anything signed/MAC'd: TODO (see CBDF §4.5).

## 6. IANA / registry considerations

- **RKE cipher-suite registry** — TODO: define registry + allocation policy
  (default *Specification Required*); source in `../registries/`.
- Any RKE-specific identifiers or ports (if RKE has its own transport): TODO.

## 7. References

**Normative**
- [RFC 2119]; [CBDF/1.0]; TODO: the specific cryptographic RFCs for chosen suites.

**Informative**
- TODO: Noise Protocol Framework, TLS 1.3 handshake — for comparison/rationale.

## 8. Appendix: test vectors

Handshake and key-schedule test vectors live in
[`../test-vectors/rke/`](../test-vectors/rke/): given inputs and randomness,
the exact CBDF-encoded messages and derived keys.
