"""The 48-byte universal preamble that begins every Group 6 request body (§4.3).

QMail and RKE share one preamble structure — the QMail spec §4.3 states it is "the same
shared preamble structure used by RKE/1.0," and the conformance vectors assert the two
are byte-identical for the same coin identity. Rather than duplicate the layout (and risk
the two drifting), QMail reuses RKE's implementation directly. QMail declares RKE/1.0 as
a dependency, so this code-level reuse mirrors the standard's dependency graph.

(Architecturally the preamble is a RAIDA-protocol primitive both groups share; a future
in-repo `raida` module could own it, at which point both RKE and QMail would import it
from there instead.)
"""
from rke.preamble import Preamble, challenge, challenge_is_valid

__all__ = ["Preamble", "challenge", "challenge_is_valid"]
