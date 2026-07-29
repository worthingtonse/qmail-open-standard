# Reference implementation

At least one open-source implementation of the QMail-family standards, used to
demonstrate that the specs are implementable and to run against the conformance
[`../test-vectors/`](../test-vectors/).

- **License:** Apache-2.0 (see [`LICENSE`](LICENSE)) — a code license with its own
  explicit patent grant, distinct from the document license (`../LICENSE-DOC`) and
  the standards' patent grant (`../PATENTS`).
- **Build order:** implement **CBDF first** (everything encodes through it), then
  RKE and DRD, then QMail.
- **Conformance:** the implementation MUST pass the vectors in `../test-vectors/`.

> TODO: choose language/toolchain and lay out the project. Keep it minimal and
> readable — a reference implementation optimizes for clarity and correctness
> against the spec, not for performance.
