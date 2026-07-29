# Contributing

Thanks for helping build the QMail Open Standard. This document explains how to
propose changes and how contributions are licensed.

## Before you start

- Read the relevant spec in [`specs/`](specs/) and [GOVERNANCE.md](GOVERNANCE.md).
- Remember the layering rule: QMail references RKE/DRD/CBDF by **ID + version** and
  does not inline them. Changes should respect that boundary.

## How to propose a change

1. **Open an issue first** for anything substantive (a normative change, a new
   registry entry, a wire-format change). Describe the problem before the fix.
2. Discuss and reach rough consensus with the editors.
3. **Open a pull request** referencing the issue. For normative changes, include:
   - The exact spec text change.
   - Updated or new **test vectors** under `test-vectors/<standard>/` when behavior
     changes. A normative change without test-vector coverage will not be merged.
   - A note on **security considerations** if the change touches them.

## Types of change

- **Editorial** (typos, clarifications that don't change conforming behavior) —
  lightweight; may be handled as errata.
- **Erratum** — corrects/clarifies a published version without changing intended
  behavior. Label the issue `erratum`. Recorded in [CHANGELOG.md](CHANGELOG.md).
- **Normative** — changes what a conforming implementation must do. Requires an
  issue, consensus, test vectors, and (if wire-incompatible) a major version bump.

## Licensing of contributions (Developer Certificate of Origin)

By contributing, you agree that:

- Your contributions to **document text** are licensed under **CC BY 4.0**
  (see [`LICENSE-DOC`](LICENSE-DOC)).
- You make the **royalty-free patent grant** in [`PATENTS`](PATENTS) for any
  Essential Claims your contribution introduces.
- Your contributions to **code** in `reference-impl/` are licensed under
  **Apache-2.0** (see [`reference-impl/LICENSE`](reference-impl/LICENSE)).

Sign off each commit with the [Developer Certificate of Origin](https://developercertificate.org/)
using `git commit -s`, which appends a `Signed-off-by:` line.

> DECISION PENDING (before 1.0): confirm whether a DCO is sufficient or whether a
> lightweight CLA is required to make the PATENTS grant robustly binding on
> contributors. Resolve with the same review that finalizes PATENTS.

## Style

- One sentence per line is welcome in spec prose (cleaner diffs).
- Use RFC 2119 keywords (MUST/SHOULD/MAY) deliberately and only in normative text.
