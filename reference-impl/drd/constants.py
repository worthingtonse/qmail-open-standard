"""DRD/1.0 (RAIDA Group 16) constants.

Values fixed by specs/drd-1.0.md. DRD bodies are big-endian and end with the RAIDA
`3E 3E` trailer. The RAIDA header and encryption envelope are out of scope (RAIDA
protocol layer). Denomination and class-rejection bytes are SIGNED (−8…+6).
"""

# RAIDA command group and the seven Group 16 command codes (§4.5). Codes are unique
# across all RAIDA groups.
COMMAND_GROUP = 16
CMD_POST_USER = 140       # 0x8C  owner AN — upsert public record
CMD_GET_USER = 141        # 0x8D  no auth  — exact PQ lookup
CMD_SEARCH_USERS = 142    # 0x8E  no auth  — case-insensitive prefix search
CMD_DELETE_USER = 143     # 0x8F  owner AN
CMD_LIST_SET = 144        # 0x90  owner AN — add/move white/black entries (6-byte)
CMD_LIST_REMOVE = 145     # 0x91  owner AN — remove entries (5-byte, no type)
CMD_LIST_GET = 146        # 0x92  owner AN — private list read

# Field sizes (§4.2–§4.4).
CHALLENGE_LEN = 16
AN_LEN = 16
MAX_NAME_LEN = 63         # 1-byte length prefix, 0–63
LIST_ENTRY_LEN = 6        # [LDN:1][LSN:4 BE][Type:1] (list_set / list_get)
LIST_REMOVE_ENTRY_LEN = 5  # [LDN:1][LSN:4 BE] (no type byte)

# Denomination / class-rejection are signed and constrained to this range (§4.2/§4.3).
DENOM_MIN, DENOM_MAX = -8, 6

# List types (§4.4.2).
LIST_WHITELIST = 0x00
LIST_BLACKLIST = 0x01

# search_users flag bits (§4.5).
SEARCH_FLAG_FIRST = 0x01
SEARCH_FLAG_LAST = 0x02

# Server caps (§4.5).
SEARCH_LIMIT_CAP = 50
LIST_CAP = 1000

# Fee scale: 8-byte signed int64 counting 10^-8 CC units (§4.3).
FEE_UNITS_PER_CC = 100_000_000
FEE_MAX_FRACTION_DIGITS = 8

# Status codes (RAIDA protocol.h enum, §4.6).
STATUS_SUCCESS = 250                     # 0xFA
ERROR_INVALID_PACKET_LENGTH = 16         # 0x10
ERROR_EMPTY_REQUEST = 36                 # 0x24
ERROR_COINS_NOT_DIV = 39                 # 0x27
ERROR_INVALID_SN_OR_DENOMINATION = 40    # 0x28
ERROR_NO_ENTRY = 193                     # 0xC1
ERROR_INVALID_PARAMETER = 198            # 0xC6
ERROR_INVALID_AN = 200                   # 0xC8
ERROR_INTERNAL = 252                     # 0xFC
ERROR_MEMORY_ALLOC = 254                 # 0xFE
