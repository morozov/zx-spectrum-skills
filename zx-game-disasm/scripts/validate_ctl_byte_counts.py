#!/usr/bin/env python3
"""
Validate that an instruction comment does not recite a byte count the listing
already carries.

For example:

    LD HL,tile_map   ; Clear 163 bytes of the tile map (tile_map).

The parenthetical is the operand said twice, which `lint_comments.py` catches as
OPERAND_ECHO. The 163 is the byte count the listing already shows, and this
check catches it.

BYTE_SPAN - an instruction comment stating the size of the span it works on.

  The number is already on the page. It is in the `LD BC,n` beside it, in the
  block's own directive, in the `LDIR` the reader can see. Copying it into prose
  buys the reader nothing and rots on the first resize or split: the count is a
  fact about the current annotation, so a block that gains a byte leaves the
  sentence lying, and nothing arithmetic can check it. What earns the line is
  the half the listing cannot show - *which* map, and *why* it is cleared here.

  A rate is the opposite case and stays. "9 bytes per slot", "8 bytes per tile",
  "a 22-byte record stride" state the arithmetic that turns an index into an
  address, which a reader would otherwise recover by counting rows by hand. That
  is a fact about the data's shape, not about this instruction's span.

  The check cannot read intent: "the 9-byte record" and "the 2848-byte working
  table" are one grammar, and only the second is a span. So the author declares
  which it is by writing a rate as a rate - `N bytes per <unit>`, `N bytes
  each`, `N bytes/<unit>`, or an `N-byte <...> stride`. Anything else reads as a
  span and is a finding. That is the whole rule, and it is the reason it is
  applicable: the fix is either to delete the number or to say what it is the
  size *of*. A ROM or hardware size is not a second exemption: "the ROM keyboard
  state (KSTATE, 8 bytes)" stands over the `LD BC,$0008` that copies it.

Scoped to instruction comments, not to block prose. A `D` or `N` note is where a
structure's shape belongs - "each pool entry is 9 bytes: +0/+1 the position,
+6/+7 the sprite pointer, +8 the active flag" is that note doing its job, stated
once for the block. The defect is the same sentence copied down onto a row that
already shows the number.

Usage: validate_ctl_byte_counts.py CTL [--baseline FILE] [--write-baseline]
Exit 0 when clean, 1 when a comment recites a length.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'byte-counts'

# An instruction comment in a .ctl: two spaces, the address, an optional
# instruction count, then the text. Block prose (`D`, `N`, a title, a `.`
# continuation) starts with a directive letter instead and is out of scope.
INSTRUCTION_COMMENT_RE = re.compile(r'^  \$?[0-9A-Fa-f]+(?:,\d+)? (?P<text>.*)$')

# A byte count: a number attached to the word "byte". The leading lookbehind
# keeps the digit from being the tail of a hyphenated word, so "a bit-7 byte" is
# not read as seven bytes. A leading '+' marks a signed field offset within a
# record ("(+1 bytes)"), which names a position, not a length.
BYTE_COUNT_RE = re.compile(r'(?<![\w+-])\d+[\s-]bytes?\b', re.IGNORECASE)

# The rate forms, which state bytes *per unit* and are therefore not this span's
# length. Two or three words of slack lets the unit carry a qualifier: "22-byte
# record stride", "64-byte row stride", "4 bytes per level".
RATE_RE = re.compile(
    r'(?<![\w-])\d+[\s-]bytes?(?:\s+\w+){0,2}\s+(?:per|each|apiece|stride)\b'
    r'|(?<![\w-])\d+[\s-]bytes?/',
    re.IGNORECASE)

DETAIL = ("'{}' recites a length the listing already carries - the `LD BC,n` "
          'beside it, the block\'s own directive - and it rots on the next '
          'resize or split. Say why the span is touched, not how big it is; '
          'for a genuine stride, write it as a rate ("N bytes per record")')


def scan(path):
    """Return the byte-span findings in one .ctl, as (lineno, kind, message)."""
    findings = []
    with open(path, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            match = INSTRUCTION_COMMENT_RE.match(raw.rstrip('\n'))
            if not match:
                continue
            text = match.group('text')
            rates = [r.span() for r in RATE_RE.finditer(text)]
            for count in BYTE_COUNT_RE.finditer(text):
                if any(s <= count.start() and count.end() <= e for s, e in rates):
                    continue
                findings.append((lineno, 'BYTE_SPAN', DETAIL.format(count.group(0))))
    return findings


def main():
    parser = argparse.ArgumentParser(
        description='Validate that an instruction comment does not recite a byte '
                    'count the listing already carries.')
    parser.add_argument('ctl', help='the .ctl file to check')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    findings = scan(args.ctl)

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, findings, lines))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, findings, lines,
                                              report_stale=not args.ignore_stale)

    if new:
        print(f'Found {len(new)} recited byte count(s):')
        print()
        for lineno, kind, message in new:
            print(f'  {os.path.basename(args.ctl)}:{lineno}: {kind} — {message}')
            print(f'    {lines[lineno - 1].strip()[:120]}')
            print()
    elif not held and not stale:
        print('byte counts: no instruction comment recites a length')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
