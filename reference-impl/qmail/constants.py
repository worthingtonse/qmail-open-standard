"""QMail/1.0 (RAIDA Group 6) constants.

QMail is the umbrella standard: RAIDA store-and-forward messaging that composes
[CBDF/1.0] (message encoding), [DRD/1.0] (anti-spam gating), and [RKE/1.0] (the shared
preamble). QMail-layer bytes are big-endian; the message payload is a little-endian CBDF
document — convert at the boundary (§1 note).
"""

# RAIDA command group and the Group 6 command codes (§4.2).
COMMAND_GROUP = 6
CMD_UPLOAD = 70
CMD_TELL = 71
CMD_PING = 72
CMD_PEEK = 73
CMD_DOWNLOAD = 74
CMD_UPLOAD_LARGE_PAGE = 75
# 76–84: Object Transfer v1 (resumable byte-range transfer / info / capability / delete).
OBJECT_TRANSFER_RANGE = range(76, 85)

# CloudCoin coin type / network id (§2), shared with CBDF, RKE, DRD.
CLOUDCOIN_COIN_TYPE = 0x0006

# download page size — the server hard-codes 256 KB (§4.6).
PAGE_SIZE = 256 * 1024

# Default Tell fee charged to a recipient with no DRD record (§4.5), 10 CC in 10^-8 units.
DEFAULT_TELL_FEE_CC = "10"
DEFAULT_TELL_FEE_UNITS = 10 * 100_000_000

# --- file_type registry (§4.4) -------------------------------------------------------
FT_META = 0            # .meta      private CBDF Meta (subject/preview/display) — required
FT_BODY = 1            # .qmail     body/content object (CBDF body) — required
FT_STYLE = 2           # .style     CBDF Styles section
FT_TEXT = 3            # .text      CBDF Text section
FT_RESOURCE = 4        # .resource  CBDF Resources section
FT_LOGIC = 5           # .logic     CBDF Logic section (Phase III)
FT_ATTACHMENT_BASE = 10  # 10 -> .0.bin, 11 -> .1.bin, ...

# --- Status codes (RAIDA protocol.h enum, QMail subset, §4.8) ------------------------
STATUS_SUCCESS = 250
ERROR_COIN_NOT_FOUND = 8
ERROR_INVALID_PACKET_LENGTH = 16
ERROR_WRONG_RAIDA = 18                 # tell: zero deliveries
ERROR_INVALID_ENCRYPTION = 34          # wire decryption failed (often a zero-AN preamble)
ERROR_INVALID_SN_OR_DENOMINATION = 40
ERROR_FILESYSTEM = 194
ERROR_INVALID_PARAMETER = 198
ERROR_INVALID_AN = 200
ERROR_FILE_NOT_EXIST = 202             # download of an absent object
ERROR_MEMORY_ALLOC = 254

# DRD-gate (tell) status codes (§4.5 / §4.8).
ERROR_PAYMENT_PROCESSING = 167         # retryable fee-lookup failure
ERROR_PAYMENT_INSUFFICIENT = 168
ERROR_PAYMENT_REQUIRED = 169           # fee owed, no locker
ERROR_SENDER_BLACKLISTED = 236
ERROR_SENDER_CLASS_REJECTED = 237
