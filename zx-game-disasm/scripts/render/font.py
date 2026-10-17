#!/usr/bin/env python3
"""
Write a game's 8x8 character font as a TrueType font and a WOFF2 web font.

The glyph for character code c is the 8 bytes at BASE + c*8, top row first, the
layout of the Spectrum ROM font and of every font a game sets through CHARS.
Each set pixel becomes one square of the outline, so the font draws the game's
characters pixel for pixel at any multiple of 8 px.

Both files are byte-identical across runs.

Usage:
    font.py IMAGE --org ORG --base BASE --first CODE --last CODE
                  --family NAME --out STEM
"""

import argparse

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import WOFF2FlavorData

PIXEL = 128                 # font units per glyph pixel
UNITS_PER_EM = 8 * PIXEL    # 1024: an 8x8 cell fills the em square


def read_glyphs(image, org, base, first, last):
    """Return {code: 8 bytes} for first..last from the program image."""
    data = open(image, "rb").read()
    glyphs = {}
    for code in range(first, last + 1):
        off = base - org + code * 8
        glyphs[code] = data[off:off + 8]
        if len(glyphs[code]) != 8:
            raise SystemExit(f"font: glyph {code:#04x} runs past {image}")
    return glyphs


def glyph_name(code):
    return f"u{code:04X}"


def build_outline(rows):
    """Return a TrueType glyph with one clockwise square per set bit of ``rows``,
    8 bytes with the top row first."""
    pen = TTGlyphPen(None)
    for r, byte in enumerate(rows):
        y_top = (8 - r) * PIXEL
        y_bot = (8 - r - 1) * PIXEL
        for col in range(8):
            if byte & (1 << (7 - col)):
                x0 = col * PIXEL
                x1 = (col + 1) * PIXEL
                pen.moveTo((x0, y_top))
                pen.lineTo((x1, y_top))
                pen.lineTo((x1, y_bot))
                pen.lineTo((x0, y_bot))
                pen.closePath()
    return pen.glyph()


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('image', help='the program image')
    parser.add_argument('--org', required=True, type=lambda s: int(s, 0),
                        help='the address of the image\'s first byte')
    parser.add_argument('--base', required=True, type=lambda s: int(s, 0),
                        help='the address the glyph of code 0 would sit at')
    parser.add_argument('--first', required=True, type=lambda s: int(s, 0),
                        help='the first character code to emit')
    parser.add_argument('--last', required=True, type=lambda s: int(s, 0),
                        help='the last character code to emit')
    parser.add_argument('--family', required=True, help='the font family name')
    parser.add_argument('--id', default=None,
                        help='the unique font identifier (default: FAMILY)')
    parser.add_argument('--out', required=True,
                        help='output stem; writes STEM.ttf and STEM.woff2')
    args = parser.parse_args()

    src_glyphs = read_glyphs(args.image, args.org, args.base, args.first, args.last)

    fb = FontBuilder(UNITS_PER_EM, isTTF=True)

    names = [glyph_name(c) for c in sorted(src_glyphs)]
    glyph_order = [".notdef"] + names
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({c: glyph_name(c) for c in src_glyphs})

    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    for code, rows in src_glyphs.items():
        glyphs[glyph_name(code)] = build_outline(rows)
    fb.setupGlyf(glyphs)

    advance = UNITS_PER_EM
    metrics = {name: (advance, 0) for name in glyph_order}
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=UNITS_PER_EM, descent=0)

    # Fixed timestamps keep the output byte-identical across runs.
    fb.setupHead(created=0, modified=0, unitsPerEm=UNITS_PER_EM)

    family = args.family
    fb.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": args.id or family,
        "fullName": family,
        "psName": family.replace(" ", "") + "-Regular",
        "version": "1.0",
    })
    fb.setupOS2(sTypoAscender=UNITS_PER_EM, sTypoDescender=0,
                usWinAscent=UNITS_PER_EM, usWinDescent=0)
    fb.setupPost(keepGlyphNames=False)

    ttf_path = args.out + ".ttf"
    fb.save(ttf_path)

    # recalcTimestamp=False: saving would otherwise set head.modified to the current time.
    ttf = TTFont(ttf_path, recalcTimestamp=False)
    ttf.flavor = "woff2"
    # Untransformed: the glyf transform's output depends on PYTHONHASHSEED.
    ttf.flavorData = WOFF2FlavorData(transformedTables=[])
    ttf.save(args.out + ".woff2")

    print(f"Emitted {len(src_glyphs)} glyphs, "
          f"codes {args.first}..{args.last} "
          f"(${args.first:02X}..${args.last:02X})")


if __name__ == "__main__":
    main()
