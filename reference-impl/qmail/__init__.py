"""QMail/1.0 (RAIDA Group 6) reference codec — the umbrella email system.

QMail composes [CBDF/1.0] (message encoding), [DRD/1.0] (anti-spam gating), and
[RKE/1.0] (the shared 48-byte preamble). This package implements the QMail-specific
surface: the universal preamble (reused from RKE), the file_type object model, the Tell
DRD-gate decision logic, and the Group 6 command/status constants. It reuses the sibling
packages directly, mirroring the standard's dependency graph — a QMail implementation
converts between the big-endian RAIDA wire and the little-endian CBDF payload at the
boundary and never reinterprets one as the other.

    from qmail import Preamble, challenge, gate, filetype

    outcome = gate.evaluate_recipient(gate.Recipient(sender_denomination=0))
"""
from . import constants
from . import filetype
from . import gate
from ._errors import QMailError
from .preamble import Preamble, challenge, challenge_is_valid
from .filetype import suffix, role, manifest_order, is_attachment
from .gate import Recipient, GateOutcome, evaluate_recipient, evaluate_tell

__all__ = [
    "constants", "filetype", "gate", "QMailError",
    "Preamble", "challenge", "challenge_is_valid",
    "suffix", "role", "manifest_order", "is_attachment",
    "Recipient", "GateOutcome", "evaluate_recipient", "evaluate_tell",
]

__version__ = "0.1.0"
