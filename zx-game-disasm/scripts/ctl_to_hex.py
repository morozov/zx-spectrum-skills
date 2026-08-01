#!/usr/bin/env python3
"""
Convert a .ctl's addresses from decimal to `$HEX`, to match the hex `.skool`.

The `.ctl` is what you hand-edit while reading the hex `--hex` skool, so decimal
addresses there force a dec<->hex conversion in your head on every cross-reference
— an error-prone step the skill bans. This rewrites every directive's leading
*address* to upper-case `$HEX` and leaves everything else untouched: sub-block
lengths, `@equ` values, numbers in comment text, and addresses already in hex.

It is purely notational — `sna2skool` produces the identical `.skool` from the
converted file (verify with a diff). Idempotent: hex addresses are left as-is.

Usage: ctl_to_hex.py <file.ctl> [-o out.ctl]   (default: in place)
"""

import argparse
import re
import sys

# A directive line carrying a leading address: either a directive char (block
# type, sub-block type, comment directive, or @) followed by space(s), or an
# instruction-comment line indented with two or more spaces. The address is the
# first decimal run; a hex address ($...) does not match \d and is skipped.
LINE = re.compile(r'^(?P<pre>[@bcgistwzBCSTWZDNRMEL] +|  +)(?P<addr>\d{1,7})(?P<post>\b.*)$')


def convert_line(line):
    m = LINE.match(line)
    if not m:
        return line
    return f"{m.group('pre')}${int(m.group('addr')):04X}{m.group('post')}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ctl')
    ap.add_argument('-o', '--out')
    args = ap.parse_args()

    with open(args.ctl, encoding='utf-8') as f:
        lines = f.read().splitlines()
    converted = [convert_line(ln) for ln in lines]
    n = sum(1 for a, b in zip(lines, converted) if a != b)

    out = args.out or args.ctl
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(converted) + '\n')
    print(f"converted {n} address(es) to hex in {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
