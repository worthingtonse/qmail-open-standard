# DRD/1.0 — Distributed Resource Directory

- **Standard ID:** DRD
- **Version:** 1.0
- **Status:** Draft (skeleton — not stable)
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.
- **Depends on:** `CBDF/1.0` (all DRD records/queries are CBDF-encoded).

## 1. Abstract

DRD is the distributed directory QMail uses to locate resources (users, servers,
keys, endpoints) without a single central authority. *(One paragraph: what it
resolves, the naming model, and the distribution/trust model.)*

## 2. Status & terminology

This document is a Draft and is not stable.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in [RFC 2119].

All records and queries are encoded with [CBDF/1.0].

## 3. Scope / non-goals

**In scope:** the naming/addressing model, record types, the query/response
protocol, and how records are distributed and validated.

**Non-goals:** the byte encoding (see CBDF), key exchange (see RKE), and mail
semantics (see QMail).

## 4. Normative definitions

### 4.1 Naming / addressing model
- TODO: the identifier syntax and resolution semantics.

### 4.2 Record types (CBDF-encoded)
- TODO: each record type, field by field.

### 4.3 Query / response protocol
- TODO: request/response messages, caching, TTLs, negative answers.

### 4.4 Distribution & authenticity
- TODO: how records propagate; how a resolver verifies a record (signatures via
  RKE-established keys?).

## 5. Security considerations

**Mandatory.**
- Threat model: TODO (spoofed records, cache poisoning, eclipse attacks, privacy
  of queries).
- Record authenticity and freshness: TODO.
- Amplification/DoS via queries or responses: TODO.

## 6. IANA / registry considerations

- **DRD record-type registry** — TODO: define registry + allocation policy
  (default *Specification Required*); source in `../registries/`.
- URI scheme / ports if DRD is independently addressable: TODO.

## 7. References

**Normative**
- [RFC 2119]; [CBDF/1.0]; TODO.

**Informative**
- TODO: DNS (RFC 1035), DHT literature — for comparison/rationale.

## 8. Appendix: test vectors

Record encodings and query/response exchanges live in
[`../test-vectors/drd/`](../test-vectors/drd/).
