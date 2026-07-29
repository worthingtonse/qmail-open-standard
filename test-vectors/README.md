# Test vectors

Concrete input→output examples that let a second, independent implementation prove
interoperability. Two independent interoperating implementations is the bar
("running code").

One subdirectory per standard:

- [`cbdf/`](cbdf/) — encoding vectors (draft these first; everything encodes via CBDF)
- [`rke/`](rke/) — handshake and key-schedule vectors
- [`drd/`](drd/) — record encodings and query/response exchanges
- [`qmail/`](qmail/) — end-to-end message encodings and protocol exchanges

## Rules

- Every normative rule in a spec SHOULD have at least one vector.
- Vectors are immutable once their spec version is published (add, don't edit).
- Prefer a machine-readable format (e.g. hex input + hex expected output, plus a
  human-readable description) so conformance harnesses can consume them directly.

> TODO: decide the vector file format (e.g. JSON with hex fields, or `.cbdf`
> binary + `.expected` pairs) and document it here before writing the first vector.
