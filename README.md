# QMail Open Standard

QMail is an open email system. This repository holds the QMail specification and
the three sub-standards it depends on, published as a real open standard: versioned
documents, an explicit royalty-free patent grant, conformance test vectors, and a
reference implementation.

> Status: **Draft / pre-1.0.** Nothing here is stable yet. Documents in `specs/`
> are skeletons being filled in. See [CHANGELOG.md](CHANGELOG.md) for version events.

## The standards

QMail is an **umbrella** standard that depends on three **independently-versioned**
sub-standards. QMail references them by ID + version (e.g. `CBDF/1.0`) and does not
inline them, so each versions on its own cadence.

| ID   | Name                           | Spec                              | Role                                |
|------|--------------------------------|-----------------------------------|-------------------------------------|
| QMail| QMail                          | [specs/qmail-1.0.md](specs/qmail-1.0.md) | Umbrella email system        |
| RKE  | Raida Key Exchange             | [specs/rke-1.0.md](specs/rke-1.0.md)     | Key exchange / trust         |
| DRD  | Distributed Resource Directory | [specs/drd-1.0.md](specs/drd-1.0.md)     | Locating / addressing        |
| CBDF | Compact Binary Document Format | [specs/cbdf-1.0.md](specs/cbdf-1.0.md)   | Binary HTML/CSS replacement; encoding foundation |

```
        QMail/1.0
        /   |   \
     RKE   DRD   (all message/wire encoding)
       \    |    /
        CBDF/1.0   ← foundation: everything encodes with this
```

**CBDF is the foundation** — RKE, DRD, and QMail all encode through it, so it is
drafted first.

## Repository layout

```
qmail-open-standard/
├── README.md              This file
├── LICENSE-DOC            CC BY 4.0 — governs all document text (specs/, *.md)
├── PATENTS               Royalty-free (RAND-Z) patent grant — anyone may implement
├── GOVERNANCE.md          Who decides, change process, compatibility promise
├── CONTRIBUTING.md        How to propose changes; how errata are handled
├── CHANGELOG.md           Cross-cutting log of version / errata events
├── specs/                 The normative specification documents
├── test-vectors/          Concrete input→output vectors (interop proof), per standard
├── registries/            Machine-readable source for self-defined registries
└── reference-impl/        Apache-2.0 reference implementation
```

## Licensing (two grants + impl)

A genuinely open standard needs two separate grants on the documents plus a normal
OSS license on the code:

- **Document text** → [`LICENSE-DOC`](LICENSE-DOC) — **CC BY 4.0**. Quote and redistribute freely.
- **Implementation rights** → [`PATENTS`](PATENTS) — **royalty-free (RAND-Z) patent grant**. Anyone may implement without a license fee.
- **Reference implementation** → [`reference-impl/LICENSE`](reference-impl/LICENSE) — **Apache-2.0** (carries its own patent grant).

## Versioning

- Stable IDs + versions: `QMail/1.0`, `RKE/1.0`, `DRD/1.0`, `CBDF/1.0`.
- A **wire-incompatible** change is a **major** bump; compatible additions are minor.
- **Published versions are immutable** — fix mistakes via **errata**, never by editing
  a released version.

## Governance & contributing

See [GOVERNANCE.md](GOVERNANCE.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Publishing path

Self-publish here on GitHub first (running code + test vectors + independent
implementers), then take it to the IETF as an Internet-Draft once stable.
