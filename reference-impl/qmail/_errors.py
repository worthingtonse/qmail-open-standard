"""QMail error type. QMail has no wire IO of its own — it composes the CBDF (LE) and
RKE/DRD (BE) codecs — so this module holds only the shared exception class."""


class QMailError(ValueError):
    """A QMail-layer value or decision violates the specification."""
