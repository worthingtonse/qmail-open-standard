"""R5G6B5 color system and the reserved transparency codes (§4.6).

A CBDF color is a 16-bit little-endian value: bits 15-11 Red (5), 10-5 Green (6),
4-0 Blue (5). Five low code points are reserved to mean transparency and never appear
in the Text stream — only inside style records.
"""
from ._io import CBDFError

# Reserved transparency codes -> alpha (§4.6). These are NOT colors.
TRANSPARENCY = {
    0x000C: 0.0,   # 100% transparent
    0x000D: 0.2,   # 80% transparent
    0x000E: 0.4,   # 60% transparent
    0x000F: 0.6,   # 40% transparent
    0x0010: 0.8,   # 20% transparent
}

# An RGB->565 result landing in the reserved band MUST be diverted here (§4.6).
RESERVED_SAFE_CODE = 0x0011


def rgb_to_565(r: int, g: int, b: int) -> int:
    """Pack 8-bit R,G,B into a 16-bit R5G6B5 code.

    Uses the truncating conversion the reference vectors are built with, so the pure
    reference colors (Black 0x0000, White 0xFFFF, Red 0xF800, ...) round-trip exactly.
    """
    for name, v in (("r", r), ("g", g), ("b", b)):
        if not 0 <= v <= 255:
            raise CBDFError(f"{name} out of 0-255 range: {v}")
    return ((r * 31 // 255) << 11) | ((g * 63 // 255) << 5) | (b * 31 // 255)


def c565_to_rgb(code: int) -> tuple:
    """Expand a 16-bit R5G6B5 code back to 8-bit (R, G, B) per §4.6 rounding."""
    if not 0 <= code <= 0xFFFF:
        raise CBDFError(f"color code out of range: {code}")
    return (
        round(((code >> 11) & 0x1F) * 255 / 31),
        round(((code >> 5) & 0x3F) * 255 / 63),
        round((code & 0x1F) * 255 / 31),
    )


def divert_reserved(code: int) -> int:
    """Bump a color that collides with the reserved transparency band to a safe code."""
    return RESERVED_SAFE_CODE if code in TRANSPARENCY else code


def encode_rgb(r: int, g: int, b: int) -> int:
    """RGB -> a safe R5G6B5 code (never a reserved transparency value)."""
    return divert_reserved(rgb_to_565(r, g, b))


def is_transparency(code: int) -> bool:
    return code in TRANSPARENCY
