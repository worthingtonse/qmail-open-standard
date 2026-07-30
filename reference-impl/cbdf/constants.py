"""CBDF/1.0 (Phase II) on-wire constants.

Every value here is fixed by specs/cbdf-1.0.md; the section reference is noted inline.
Names mirror the spec so the codec reads like the document it implements.
"""

# --- Control characters, 0x00-0x1F (§4.5.1) ------------------------------------------
NOP = 0x00
SUBJECT_START = 0x01  # SOH
TEXT_START = 0x02     # STX
TEXT_END = 0x03       # ETX
DOC_END = 0x04
TAB = 0x09
LINE_BREAK = 0x0A     # LF
PARA_BREAK = 0x0B
PAGE_BREAK = 0x0C
HORIZ_RULE = 0x0D
LINK_START = 0x0E
LINK_END = 0x0F
DATA_ESCAPE = 0x10
STYLE_TEXT = 0x11
STYLE_CONTAINER = 0x12
STYLE_TABLE = 0x13
STYLE_END = 0x14
ELEMENT_ID = 0x15
IMAGE = 0x16
BLOCK_END = 0x17
RESERVED_HIDE = 0x18
ITEM_BLOCK = 0x19
AI_PROMPT = 0x1A
FS = 0x1C  # SECTION_SEP
GS = 0x1D  # GROUP_SEP
RS = 0x1E  # RECORD_SEP
US = 0x1F  # UNIT_SEP

# Aliases used throughout the spec text.
SOH, STX, ETX = SUBJECT_START, TEXT_START, TEXT_END
LF = LINE_BREAK

# --- Meta key registry (§4.3.1 Phase I, §4.3.2 Phase II) -----------------------------
class Meta:
    FILE_TYPE = 0
    QMAIL_ID = 1
    SUBJECT = 2
    ATTACHMENT_NAME = 3
    ATTACHMENT_TOTAL_PAGES = 4
    PAGE_HASH = 5
    ATTACHMENT_COUNT = 12
    TO = 13
    CC = 14
    FROM = 19
    TIMESTAMP = 25
    # Phase II
    VERSION = 30
    COMPRESSION = 31
    DEFAULT_STYLE_SET = 32
    EOF_FLAG = 33
    # 34 RETIRED — never emit, never reassign
    AI_SUMMARY = 35
    PREVIEW_TEXT = 36
    SUBJECT_STYLE_ID = 37
    SEMANTIC_MODEL = 38
    SEMANTIC_FLAGS = 39
    TEXT_OFFSET = 40
    TIMESTAMP64 = 41
    REQUIRED_FEATURES = 42
    OPTIONAL_FEATURES = 43
    CONTENT_LANGUAGE = 44
    CONTENT_HASH = 45


# Meta File Type values (key 0).
FILE_TYPE_GENERIC = 0
FILE_TYPE_QMAIL = 1
FILE_TYPE_SMS = 2
FILE_TYPE_QWEB = 3

# Wire version (key 30): absent => Phase I; 1 => Phase II.
VERSION_PHASE_II = 1

# Keys forbidden in a meta-only document (§4.3.2): key 33 = 1.
META_ONLY_FORBIDDEN_KEYS = frozenset({31, 32, 37, 40, 42, 43})

# Key 34 is permanently retired (§4.3.1/§4.3.2).
RETIRED_META_KEY = 34

# --- CloudCoin mailbox (§4.3.5) ------------------------------------------------------
# Mailbox is 7 bytes: [CoinGroup:2][Denomination:1][Serial:4 LE].
# CloudCoin mailboxes MUST encode the coin-group field as the literal bytes 00 06.
CLOUDCOIN_COIN_GROUP = 0x0006

# --- Resource types (§4.8) -----------------------------------------------------------
RES_PNG = 0
RES_JPEG = 1
RES_WEBP = 2
RES_SVG = 3
RES_FONT = 4
RES_AUDIO = 5
RES_VIDEO = 6
RES_EMBEDDED_CBDF = 7

# --- Compression codecs (key 31, §4.9) -----------------------------------------------
COMPRESS_NONE = 0
COMPRESS_ZLIB = 1  # DEFLATE/zlib — mandatory to implement
COMPRESS_LZ4 = 2
COMPRESS_ZSTD = 3
COMPRESS_BROTLI = 4
COMPRESS_SEMANTIC = 5

# --- Style sub-tables, fixed order (§4.4.2) ------------------------------------------
# (name, (base, extended, rare) record sizes). Non-tiered tables repeat one size.
# The 12th table (Forms) is reserved for Phase III and carries no records in v1.
SUBTABLE_ORDER = (
    ("container_background", (6, 12, 20)),  # tiered
    ("container_border", (9, 9, 9)),
    ("container_spacing", (4, 4, 4)),
    ("container_shadow", (4, 4, 4)),
    ("container_composite", (5, 5, 5)),
    ("text_styles", (8, 12, 16)),           # tiered
    ("font_effects", (4, 4, 4)),
    ("nav_bar", (12, 12, 12)),
    ("table", (6, 6, 6)),
    ("image_def", (8, 8, 8)),
    ("frame_def", (8, 8, 8)),
    ("forms", None),                        # reserved (Phase III)
)

SUBTABLE_COUNT = len(SUBTABLE_ORDER)
assert SUBTABLE_COUNT == 12

# Tier codes in a sub-table header byte (bits 0-1); tier 3 is reserved -> reject.
TIER_BASE, TIER_EXTENDED, TIER_RARE, TIER_RESERVED = 0, 1, 2, 3

# "No reference" sentinel for optional style-index fields (§4.4.1); valid indices 0-62.
NO_STYLE_REF = 255

# Maximum style-stack depth for the Text control language (§4.5).
MAX_STYLE_STACK_DEPTH = 32
