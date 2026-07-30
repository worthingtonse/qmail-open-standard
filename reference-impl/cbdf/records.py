"""Field-level encoders/decoders for the twelve style record layouts (§4.4.3).

Each class packs to and parses from the exact bytes the spec defines, decomposing the
packed bitfields (flags, nibble-packed spacing/thickness, 6-bit corner radii, the
signed-6-bit shadow triple) into named attributes. The two tiered records (Text Style
and Background) carry a `tier` and emit the matching 8/12/16 or 6/12/20-byte form.

Encoders MUST write reserved bytes as 0; decoders MUST accept non-zero reserved bytes
and ignore them (§4.4.3). These classes drop reserved fields on decode and always emit
zeros, which satisfies both rules.

Use with the structural codec in `styles.py`:

    from cbdf import StylesSection, SubTable
    from cbdf.records import TextStyle
    tbl = SubTable.of([TextStyle(font_size=14, bold=True, fg_color=0xF800)])
    ...
    parsed_sub.typed()   # -> [TextStyle(...)]
"""
from dataclasses import dataclass
from ._io import u16, read_u16, CBDFError
from .constants import TIER_BASE, TIER_EXTENDED, TIER_RARE


# --- small packing helpers -----------------------------------------------------------
def _nib(hi: int, lo: int) -> int:
    """Pack two 0-15 nibbles as high|low (the spec's `top|right` byte order)."""
    for v in (hi, lo):
        if not 0 <= v <= 15:
            raise CBDFError(f"nibble out of 0-15 range: {v}")
    return (hi << 4) | lo


def _unnib(b: int):
    return (b >> 4) & 0x0F, b & 0x0F


def _s6_pack(v: int) -> int:
    """Signed 6-bit two's complement (-32..31) into a 6-bit field."""
    if not -32 <= v <= 31:
        raise CBDFError(f"signed 6-bit value out of -32..31: {v}")
    return v & 0x3F


def _s6_unpack(u: int) -> int:
    return u - 64 if (u & 0x20) else u


def _s8_pack(v: int) -> int:
    if not -128 <= v <= 127:
        raise CBDFError(f"signed int8 out of range: {v}")
    return v & 0xFF


def _s8_unpack(u: int) -> int:
    return u - 256 if u >= 128 else u


def pack_shadow(x: int, y: int, blur: int) -> int:
    """Pack (X, Y, blur) as the u16 used by Text extended 8-9 and Shadow 2-3."""
    if not 0 <= blur <= 15:
        raise CBDFError(f"blur out of 0-15 range: {blur}")
    return _s6_pack(x) | (_s6_pack(y) << 6) | (blur << 12)


def unpack_shadow(v: int):
    return _s6_unpack(v & 0x3F), _s6_unpack((v >> 6) & 0x3F), (v >> 12) & 0x0F


def _pack_radii(tl: int, tr: int, br: int, bl: int) -> bytes:
    """Four 6-bit corner radii packed LSB-first across 24 bits -> 3 bytes."""
    for v in (tl, tr, br, bl):
        if not 0 <= v <= 63:
            raise CBDFError(f"corner radius out of 0-63 range: {v}")
    v = (tl & 0x3F) | ((tr & 0x3F) << 6) | ((br & 0x3F) << 12) | ((bl & 0x3F) << 18)
    return v.to_bytes(3, "little")


def _unpack_radii(b: bytes):
    v = b[0] | (b[1] << 8) | (b[2] << 16)
    return (v & 0x3F, (v >> 6) & 0x3F, (v >> 12) & 0x3F, (v >> 18) & 0x3F)


def _need_len(raw: bytes, allowed, name: str) -> None:
    if len(raw) not in allowed:
        raise CBDFError(f"{name} record must be {allowed} bytes, got {len(raw)}")


# --- 6.1 Text Style (tiers 8/12/16) --------------------------------------------------
@dataclass
class TextStyle:
    TABLE_INDEX = 5
    font_id: int = 0
    font_size: int = 0            # points; 0 = inherit
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    subscript: bool = False
    superscript: bool = False
    alignment: int = 0            # 0 left, 1 center, 2 right, 3 justify
    fg_color: int = 0
    bg_color: int = 0
    tier: int = TIER_BASE
    # extended
    shadow: tuple = None          # (x, y, blur) or None
    letter_spacing: int = 0       # signed int8, 0.1 em units
    line_height: int = 0          # 0 auto, else /10
    # rare
    effect_id: int = 0            # 0-15
    effect_intensity: int = 0     # 0-15
    transform: int = 0            # 0 none, 1 UPPER, 2 lower, 3 Capitalize
    direction: int = 0            # 0 auto, 1 LTR, 2 RTL
    word_spacing: int = 0         # 0-15, 0.1 em
    effect_color: int = 0

    def pack(self) -> bytes:
        flags = ((self.bold << 0) | (self.italic << 1) | (self.underline << 2)
                 | (self.strike << 3) | (self.subscript << 4) | (self.superscript << 5)
                 | ((self.alignment & 0x03) << 6))
        out = u16(self.font_id) + bytes([self.font_size & 0xFF, flags]) \
            + u16(self.fg_color) + u16(self.bg_color)
        if self.tier in (TIER_EXTENDED, TIER_RARE):
            sh = 0 if self.shadow is None else pack_shadow(*self.shadow)
            out += u16(sh) + bytes([_s8_pack(self.letter_spacing), self.line_height & 0xFF])
        if self.tier == TIER_RARE:
            b12 = (self.effect_id & 0x0F) | ((self.effect_intensity & 0x0F) << 4)
            b13 = ((self.transform & 0x03) | ((self.direction & 0x03) << 2)
                   | ((self.word_spacing & 0x0F) << 4))
            out += bytes([b12, b13]) + u16(self.effect_color)
        return out

    @classmethod
    def unpack(cls, raw: bytes) -> "TextStyle":
        _need_len(raw, (8, 12, 16), "Text Style")
        flags = raw[3]
        o = cls(
            font_id=read_u16(raw, 0), font_size=raw[2],
            bold=bool(flags & 1), italic=bool(flags & 2), underline=bool(flags & 4),
            strike=bool(flags & 8), subscript=bool(flags & 16),
            superscript=bool(flags & 32), alignment=(flags >> 6) & 3,
            fg_color=read_u16(raw, 4), bg_color=read_u16(raw, 6),
            tier=TIER_BASE,
        )
        if len(raw) >= 12:
            o.tier = TIER_EXTENDED
            sh = read_u16(raw, 8)
            o.shadow = None if sh == 0 else unpack_shadow(sh)
            o.letter_spacing = _s8_unpack(raw[10])
            o.line_height = raw[11]
        if len(raw) == 16:
            o.tier = TIER_RARE
            o.effect_id = raw[12] & 0x0F
            o.effect_intensity = (raw[12] >> 4) & 0x0F
            o.transform = raw[13] & 0x03
            o.direction = (raw[13] >> 2) & 0x03
            o.word_spacing = (raw[13] >> 4) & 0x0F
            o.effect_color = read_u16(raw, 14)
        return o


# --- 6.2 Background (tiers 6/12/20) --------------------------------------------------
@dataclass
class Background:
    TABLE_INDEX = 0
    bg_color: int = 0             # gradient color 1 when a gradient is set
    image_id: int = 0            # 0 = none
    opacity: int = 255           # 0-255
    repeat_x: bool = False
    repeat_y: bool = False
    fixed: bool = False
    cover: bool = False
    contain: bool = False
    tier: int = TIER_BASE
    # extended
    grad_color2: int = 0
    grad_type: int = 0            # 0 none, 1 linear, 2 radial
    grad_angle: int = 0          # value * 360/256 deg
    color2_stop: int = 0         # 0-255 = 0-100%
    # rare
    grad_color3: int = 0
    grad_color4: int = 0
    color3_stop: int = 0
    color4_stop: int = 0

    def _image_flags(self) -> int:
        return ((self.repeat_x << 0) | (self.repeat_y << 1) | (self.fixed << 2)
                | (self.cover << 3) | (self.contain << 4))

    def pack(self) -> bytes:
        out = u16(self.bg_color) + u16(self.image_id) \
            + bytes([self.opacity & 0xFF, self._image_flags()])
        if self.tier in (TIER_EXTENDED, TIER_RARE):
            out += u16(self.grad_color2) + bytes([
                self.grad_type & 0xFF, self.grad_angle & 0xFF,
                self.color2_stop & 0xFF, 0])  # byte 11 reserved
        if self.tier == TIER_RARE:
            out += u16(self.grad_color3) + u16(self.grad_color4) \
                + bytes([self.color3_stop & 0xFF, self.color4_stop & 0xFF, 0, 0])  # 18-19 rsv
        return out

    @classmethod
    def unpack(cls, raw: bytes) -> "Background":
        _need_len(raw, (6, 12, 20), "Background")
        f = raw[5]
        o = cls(
            bg_color=read_u16(raw, 0), image_id=read_u16(raw, 2), opacity=raw[4],
            repeat_x=bool(f & 1), repeat_y=bool(f & 2), fixed=bool(f & 4),
            cover=bool(f & 8), contain=bool(f & 16), tier=TIER_BASE,
        )
        if len(raw) >= 12:
            o.tier = TIER_EXTENDED
            o.grad_color2 = read_u16(raw, 6)
            o.grad_type = raw[8]
            o.grad_angle = raw[9]
            o.color2_stop = raw[10]
        if len(raw) == 20:
            o.tier = TIER_RARE
            o.grad_color3 = read_u16(raw, 12)
            o.grad_color4 = read_u16(raw, 14)
            o.color3_stop = raw[16]
            o.color4_stop = raw[17]
        return o


# --- 6.3 Border (9) ------------------------------------------------------------------
@dataclass
class Border:
    TABLE_INDEX = 1
    border_color: int = 0
    thickness_top: int = 0        # nibbles, 0-15 px each
    thickness_right: int = 0
    thickness_bottom: int = 0
    thickness_left: int = 0
    outside_color: int = 0
    radius_tl: int = 0            # 0-63 (percent ~= round(v*50/63))
    radius_tr: int = 0
    radius_br: int = 0
    radius_bl: int = 0

    def pack(self) -> bytes:
        return (u16(self.border_color)
                + bytes([_nib(self.thickness_top, self.thickness_right),
                         _nib(self.thickness_bottom, self.thickness_left)])
                + u16(self.outside_color)
                + _pack_radii(self.radius_tl, self.radius_tr, self.radius_br, self.radius_bl))

    @classmethod
    def unpack(cls, raw: bytes) -> "Border":
        _need_len(raw, (9,), "Border")
        t_top, t_right = _unnib(raw[2])
        t_bottom, t_left = _unnib(raw[3])
        tl, tr, br, bl = _unpack_radii(raw[6:9])
        return cls(border_color=read_u16(raw, 0),
                   thickness_top=t_top, thickness_right=t_right,
                   thickness_bottom=t_bottom, thickness_left=t_left,
                   outside_color=read_u16(raw, 4),
                   radius_tl=tl, radius_tr=tr, radius_br=br, radius_bl=bl)


# --- 6.4 Spacing (4) -----------------------------------------------------------------
@dataclass
class Spacing:
    """Nibble semantics (§4.4.3): 0 = explicit zero, 15 = inherit-from-left,
    1-14 = value x 4 px. Fields hold the raw 0-15 nibble."""
    TABLE_INDEX = 2
    margin_top: int = 0
    margin_right: int = 0
    margin_bottom: int = 0
    margin_left: int = 0
    padding_top: int = 0
    padding_right: int = 0
    padding_bottom: int = 0
    padding_left: int = 0

    def pack(self) -> bytes:
        return bytes([_nib(self.margin_top, self.margin_right),
                      _nib(self.margin_bottom, self.margin_left),
                      _nib(self.padding_top, self.padding_right),
                      _nib(self.padding_bottom, self.padding_left)])

    @classmethod
    def unpack(cls, raw: bytes) -> "Spacing":
        _need_len(raw, (4,), "Spacing")
        mt, mr = _unnib(raw[0]); mb, ml = _unnib(raw[1])
        pt, pr = _unnib(raw[2]); pb, pl = _unnib(raw[3])
        return cls(mt, mr, mb, ml, pt, pr, pb, pl)


# --- 6.5 Shadow (4) ------------------------------------------------------------------
@dataclass
class Shadow:
    TABLE_INDEX = 3
    shadow_color: int = 0
    x: int = 0                    # signed 6-bit px
    y: int = 0
    blur: int = 0                 # 0-15

    def pack(self) -> bytes:
        return u16(self.shadow_color) + u16(pack_shadow(self.x, self.y, self.blur))

    @classmethod
    def unpack(cls, raw: bytes) -> "Shadow":
        _need_len(raw, (4,), "Shadow")
        x, y, blur = unpack_shadow(read_u16(raw, 2))
        return cls(shadow_color=read_u16(raw, 0), x=x, y=y, blur=blur)


# --- 6.6 Composite (5) ---------------------------------------------------------------
@dataclass
class Composite:
    TABLE_INDEX = 4
    background_index: int = 255   # 255 = none
    border_index: int = 255
    spacing_index: int = 255
    shadow_index: int = 255
    overflow: int = 0             # 0 visible, 1 hidden, 2 scroll
    layer_id: int = 1             # §4.4.4 (default Content)

    def pack(self) -> bytes:
        if not 0 <= self.layer_id <= 63:
            raise CBDFError(f"layer_id out of 0-63 range: {self.layer_id}")
        b4 = (self.overflow & 0x03) | ((self.layer_id & 0x3F) << 2)
        return bytes([self.background_index & 0xFF, self.border_index & 0xFF,
                      self.spacing_index & 0xFF, self.shadow_index & 0xFF, b4])

    @classmethod
    def unpack(cls, raw: bytes) -> "Composite":
        _need_len(raw, (5,), "Composite")
        return cls(background_index=raw[0], border_index=raw[1], spacing_index=raw[2],
                   shadow_index=raw[3], overflow=raw[4] & 0x03, layer_id=(raw[4] >> 2) & 0x3F)


# --- 6.7 Font Effect (4) -------------------------------------------------------------
@dataclass
class FontEffect:
    TABLE_INDEX = 6
    effect_id: int = 0
    intensity: int = 0            # 0-255
    param_a: int = 0
    param_b: int = 0

    def pack(self) -> bytes:
        return bytes([self.effect_id & 0xFF, self.intensity & 0xFF,
                      self.param_a & 0xFF, self.param_b & 0xFF])

    @classmethod
    def unpack(cls, raw: bytes) -> "FontEffect":
        _need_len(raw, (4,), "Font Effect")
        return cls(effect_id=raw[0], intensity=raw[1], param_a=raw[2], param_b=raw[3])


# --- 6.8 Nav Bar (12) ----------------------------------------------------------------
@dataclass
class NavBar:
    TABLE_INDEX = 7
    item_style_index: int = 0
    active_index: int = 255       # 255 = same as items
    hover_index: int = 255
    bar_background_index: int = 255
    bar_border_index: int = 255
    bar_spacing_index: int = 255
    collapse_breakpoint: int = 0  # 0 never, else value x 8 px
    orientation: int = 0          # 0 horizontal, 1 vertical
    item_mode: int = 0            # 0 text+icon, 1 text, 2 icon
    alignment: int = 0            # 0 start, 1 center, 2 end, 3 space-between

    def pack(self) -> bytes:
        flags = ((self.orientation & 0x01) | ((self.item_mode & 0x03) << 1)
                 | ((self.alignment & 0x03) << 3))
        return bytes([self.item_style_index & 0xFF, self.active_index & 0xFF,
                      self.hover_index & 0xFF, self.bar_background_index & 0xFF,
                      self.bar_border_index & 0xFF, self.bar_spacing_index & 0xFF,
                      self.collapse_breakpoint & 0xFF, flags]) + bytes(4)  # 8-11 reserved

    @classmethod
    def unpack(cls, raw: bytes) -> "NavBar":
        _need_len(raw, (12,), "Nav Bar")
        f = raw[7]
        return cls(item_style_index=raw[0], active_index=raw[1], hover_index=raw[2],
                   bar_background_index=raw[3], bar_border_index=raw[4],
                   bar_spacing_index=raw[5], collapse_breakpoint=raw[6],
                   orientation=f & 1, item_mode=(f >> 1) & 3, alignment=(f >> 3) & 3)


# --- 6.9 Table (6) -------------------------------------------------------------------
@dataclass
class Table:
    TABLE_INDEX = 8
    header_style_index: int = 255  # 255 = body style
    body_style_index: int = 0
    grid_border_index: int = 255
    alt_row_background_index: int = 255  # 255 = no striping
    cell_spacing_index: int = 255
    first_row_header: bool = False
    row_stripes: bool = False
    column_rules: bool = False
    row_rules: bool = False

    def pack(self) -> bytes:
        flags = ((self.first_row_header << 0) | (self.row_stripes << 1)
                 | (self.column_rules << 2) | (self.row_rules << 3))
        return bytes([self.header_style_index & 0xFF, self.body_style_index & 0xFF,
                      self.grid_border_index & 0xFF, self.alt_row_background_index & 0xFF,
                      self.cell_spacing_index & 0xFF, flags])

    @classmethod
    def unpack(cls, raw: bytes) -> "Table":
        _need_len(raw, (6,), "Table")
        f = raw[5]
        return cls(header_style_index=raw[0], body_style_index=raw[1],
                   grid_border_index=raw[2], alt_row_background_index=raw[3],
                   cell_spacing_index=raw[4], first_row_header=bool(f & 1),
                   row_stripes=bool(f & 2), column_rules=bool(f & 4), row_rules=bool(f & 8))


# --- 6.10 Image Definition (8) -------------------------------------------------------
@dataclass
class ImageDef:
    TABLE_INDEX = 9
    source_type: int = 0          # 0 document resource, 1 built-in, 2 AI (reserved)
    source_id: int = 0
    width: int = 0                # u16 px, 0 = natural
    height: int = 0
    fit: int = 0                  # 0 contain, 1 cover, 2 stretch, 3 tile
    border_index: int = 255       # 255 = none

    def pack(self) -> bytes:
        return (bytes([self.source_type & 0xFF, self.source_id & 0xFF])
                + u16(self.width) + u16(self.height)
                + bytes([self.fit & 0xFF, self.border_index & 0xFF]))

    @classmethod
    def unpack(cls, raw: bytes) -> "ImageDef":
        _need_len(raw, (8,), "Image Definition")
        return cls(source_type=raw[0], source_id=raw[1], width=read_u16(raw, 2),
                   height=read_u16(raw, 4), fit=raw[6], border_index=raw[7])


# --- 6.11 Frame Definition (8) -------------------------------------------------------
@dataclass
class FrameDef:
    TABLE_INDEX = 10
    source_type: int = 0          # 0 embedded CBDF, 1 QWeb ID (reserved III)
    source_id: int = 0
    width: int = 0                # u16 px, 0 = auto
    height: int = 0
    allow_scrolling: bool = False
    allow_links: bool = False
    allow_framed_resources: bool = False
    allow_nested_frames: bool = False
    border_index: int = 255       # 255 = none

    def pack(self) -> bytes:
        sandbox = ((self.allow_scrolling << 0) | (self.allow_links << 1)
                   | (self.allow_framed_resources << 2) | (self.allow_nested_frames << 3))
        return (bytes([self.source_type & 0xFF, self.source_id & 0xFF])
                + u16(self.width) + u16(self.height)
                + bytes([sandbox, self.border_index & 0xFF]))

    @classmethod
    def unpack(cls, raw: bytes) -> "FrameDef":
        _need_len(raw, (8,), "Frame Definition")
        s = raw[6]
        return cls(source_type=raw[0], source_id=raw[1], width=read_u16(raw, 2),
                   height=read_u16(raw, 4), allow_scrolling=bool(s & 1),
                   allow_links=bool(s & 2), allow_framed_resources=bool(s & 4),
                   allow_nested_frames=bool(s & 8), border_index=raw[7])


# Sub-table index -> record class (Forms, index 11, is reserved for Phase III).
RECORD_CLASSES = {
    0: Background, 1: Border, 2: Spacing, 3: Shadow, 4: Composite, 5: TextStyle,
    6: FontEffect, 7: NavBar, 8: Table, 9: ImageDef, 10: FrameDef,
}


def decode_record(table_index: int, raw: bytes):
    cls = RECORD_CLASSES.get(table_index)
    if cls is None:
        raise CBDFError(f"no field-level record type for sub-table index {table_index}")
    return cls.unpack(raw)
