# Governance

This document states how the QMail Open Standard is governed: who decides, how
changes are made, how errata are handled, and the compatibility promise. It is
intentionally short. Its purpose is to signal that this is a real open standard
with a process — not a single-vendor spec.

## Scope

Governs the four specifications in `specs/` (QMail, RKE, DRD, CBDF), their test
vectors, registries, and the reference implementation.

## Roles

- **Editors** — maintain the specification text, merge accepted changes, publish
  versions and errata. Listed in this file.
- **Contributors** — anyone who proposes changes via issues or pull requests (see
  [CONTRIBUTING.md](CONTRIBUTING.md)).
- **Maintainer / BDFL** — Sean Worthington holds final decision authority during
  the pre-1.0 phase. This concentrates decision-making now for speed and is
  expected to broaden into a small editors' group before, or shortly after, 1.0.

> TODO: list editors here (name / handle / which specs).

## Decision process

- Changes are proposed as issues or pull requests and discussed in the open.
- **Rough consensus** among editors is the goal; the maintainer resolves
  deadlocks during pre-1.0.
- Substantive normative changes SHOULD reference a real-world need (an
  implementer problem, an interop failure, a security finding).

## Versioning & the compatibility promise

Each document has a stable ID and version (`CBDF/1.0`, `QMail/1.0`, …).

- A **wire-incompatible** change is a **MAJOR** version bump.
- A backward-compatible addition is a **MINOR** bump.
- Editorial/clarifying fixes that do not change conforming behavior are **errata**
  (see below) or a PATCH bump.
- **Published versions are immutable.** Once a version is tagged and published, its
  normative content is never silently edited. Mistakes are corrected by publishing
  errata and, if they change conforming behavior, a new version.
- Because QMail references RKE/DRD/CBDF by ID+version, a bump in one sub-standard
  does not force a bump in QMail unless QMail chooses to adopt it.

## Errata

- Errata are filed as issues labeled `erratum` and, once accepted, recorded in
  [CHANGELOG.md](CHANGELOG.md) and in the affected document's status section.
- An erratum clarifies or corrects without changing intended conforming behavior.
  If behavior must change, that is a new version, not an erratum.

## Publishing path

Self-publish here first (with running code + test vectors + independent
implementers), then submit to the IETF as an Internet-Draft once stable. Governance
may transfer to an SDO or foundation at that point; this file will be updated to
reflect any such change.
