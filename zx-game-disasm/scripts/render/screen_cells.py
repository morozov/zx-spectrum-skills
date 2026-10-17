#!/usr/bin/env python3
"""
Render a rectangle of character cells from the screen in a program image.

Each cell's ink is drawn in its attribute's ink color and its paper is left
transparent, so the picture sits on any page background. The image must hold
the display file and the attribute file at $4000.

Usage:
    screen_cells.py IMAGE OUT --org ORG --cells COL,ROW,WIDTH,HEIGHT [--trim]
"""

import argparse

from PIL import Image

NORMAL, BRIGHT = 0xCD, 0xFF


def zx_rgb(index, bright):
    """RGB for a 3-bit ZX color index (bit0=blue, bit1=red, bit2=green)."""
    level = BRIGHT if bright else NORMAL
    return (
        level if index & 2 else 0,   # red
        level if index & 4 else 0,   # green
        level if index & 1 else 0,   # blue
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('image', help='the program image')
    parser.add_argument('out', help='the PNG to write')
    parser.add_argument('--org', required=True, type=lambda s: int(s, 0),
                        help='the address of the image\'s first byte')
    parser.add_argument('--cells', required=True,
                        help='COL,ROW,WIDTH,HEIGHT of the rectangle, in character cells')
    parser.add_argument('--trim', action='store_true',
                        help='crop the result to its ink')
    args = parser.parse_args()

    col0, row0, width, height = (int(v) for v in args.cells.split(','))
    data = open(args.image, "rb").read()
    img = Image.new("RGBA", (8 * width, 8 * height), (0, 0, 0, 0))
    px = img.load()
    for cy in range(height):
        row = row0 + cy
        for cx in range(width):
            col = col0 + cx
            attr = data[0x5800 - args.org + row * 32 + col]
            ink = zx_rgb(attr & 7, attr & 0x40) + (255,)
            for line in range(8):
                y = row * 8 + line
                # Display-file address of pixel row y, column byte col.
                addr = (0x4000 | (y & 0xC0) << 5 | (y & 7) << 8
                        | (y & 0x38) << 2 | col)
                byte = data[addr - args.org]
                for bit in range(8):
                    if byte & (0x80 >> bit):
                        px[cx * 8 + bit, cy * 8 + line] = ink
    if args.trim:
        img = img.crop(img.getchannel("A").getbbox())
    img.save(args.out)
    print(f"Wrote {args.out}: {img.width}x{img.height} px")


if __name__ == "__main__":
    main()
