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

## Vector format

Settled with the first CBDF set: **JSON, one object per vector**, with a continuous
lowercase `bytes_hex` string plus an `annotated` byte-by-byte breakdown (and
purpose-specific fields where a raw byte string doesn't fit). Each standard's
subdirectory documents its own files and ships a `generate.py` that emits the JSON and
`assert`s the non-trivial values, so regenerating doubles as a conformance smoke test.
See [`cbdf/README.md`](cbdf/README.md) for the worked example.
