# CBDF/1.0 — Compact Binary Data Format

- **Standard ID:** CBDF
- **Version:** 1.0
- **Status:** Draft (skeleton — not stable)
- **License:** Document text under CC BY 4.0 (see `../LICENSE-DOC`); implementation
  rights under the royalty-free grant in `../PATENTS`.

> **Draft everything in CBDF first.** RKE, DRD, and QMail all encode through CBDF,
> so this document is the foundation of the entire standard.

## 1. Abstract

CBDF is a compact, self-describing binary encoding used by all QMail-family
standards to represent structured data on the wire and at rest. *(One paragraph:
state what CBDF is, why binary/compact, and that RKE/DRD/QMail build on it.)*

## 2. Status & terminology

This document is a Draft and is not stable; conforming implementations MUST NOT
rely on its current content.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this
document are to be interpreted as described in [RFC 2119].

Byte order, bit numbering, and the primitive value model used throughout are
defined in §4.

## 3. Scope / non-goals

**In scope:** the octet-level encoding of primitive and composite values; the
type/tag system; length framing; the versioning of the format itself.

**Non-goals:** transport, encryption, key exchange (see RKE), resource
addressing (see DRD), and message semantics (see QMail). CBDF encodes bytes; it
does not interpret them.

## 4. Normative definitions

*(This is the bulk of the document. Define precisely and give byte-level detail.)*

### 4.1 Conventions
- Byte order: TODO (define endianness).
- Bit numbering and diagrams: TODO.

### 4.2 Primitive types
- TODO: integers (widths, signedness, var-int?), booleans, floats, byte strings,
  UTF-8 text, null/absent.

### 4.3 Type tags / framing
- TODO: how each value is tagged and length-framed; the tag registry (see §6).

### 4.4 Composite types
- TODO: arrays/lists, maps/records, nested structures, ordering rules.

### 4.5 Canonical form
- TODO: is there a single canonical encoding for a given value? (Matters for
  signatures in RKE and for deterministic hashing.)

### 4.6 Format versioning
- TODO: how a CBDF stream/document signals the CBDF version it uses.

## 5. Security considerations

**Mandatory.** *(Reviewers judge the spec on this section.)*

- Decoder hardening: bounds on nesting depth, total size, and per-field length to
  resist decompression/allocation attacks. TODO.
- Non-canonical / malformed input handling: reject vs. tolerate; must be
  deterministic. TODO.
- Aliasing/duplicate keys in maps: define behavior to avoid parser-differential
  attacks. TODO.

## 6. IANA / registry considerations

- Media type: **`application/cbdf`** — TODO: register (template in `../registries/`).
- **CBDF type-tag registry** — TODO: define the registry and its allocation policy
  (default: *Specification Required*). Machine-readable source in `../registries/`.

## 7. References

**Normative**
- [RFC 2119] Key words for use in RFCs to Indicate Requirement Levels.
- TODO: UTF-8 (RFC 3629), IEEE 754 if floats are used, etc.

**Informative**
- TODO: prior art (CBOR/RFC 8949, MessagePack, Protocol Buffers) — cite for
  comparison and rationale.

## 8. Appendix: test vectors

Concrete input→output encodings live in [`../test-vectors/cbdf/`](../test-vectors/cbdf/).
Every normative encoding rule in §4 MUST have at least one vector. A second,
independent implementation passing these vectors is the interop bar.
