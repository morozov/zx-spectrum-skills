#!/usr/bin/env python3
"""Every element of an array of records must be annotated individually.

An array laid out as one directive - or as no directive at all - documents the
span, not the contents. The reader gets "6400 bytes, 64 per level" and no way to
find level 12; nothing states where a record starts or what it is. This flags the
two forms:

  UNINDEXED  one sub-directive stands in for >= MIN records
             (B $9000,6400,64 -> 100 records, one line)
  UNDECLARED an array-sized span with no sub-directive at all, so the record
             size lives only in prose

Both are fixed the same way: one annotated sub-line per record, naming it -
"Level 1", "Level 2".

Usage: validate_ctl_array_elements.py CTL [--min-records N] [--min-span N]
Exit 0 when clean, 1 when any array is unannotated.
"""
import argparse
import re
import sys

# Addresses take the same forms the sibling linters accept - `$HEX` or plain
# decimal - so a .ctl that has not been through ctl_to_hex.py gets reported on
# rather than matching nothing and reading clean.
ADDR = r'(\$?[0-9A-Fa-f]+)'
ENTRY = re.compile(r'^([bcgistuw]) +%s(?: +(\S.*))?$' % ADDR)
SUB = re.compile(r'^([BCSTWM]) +%s((?:,[^\s]+)*)(?: +(\S.*))?$' % ADDR)


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def records(args):
    """Record count a sub-directive stands for: len//stride, else 1."""
    parts = [p for p in args.split(',') if p]
    if len(parts) < 2:
        return 1
    try:
        length, stride = int(parts[0], 0), int(parts[1].split(':')[0], 0)
    except ValueError:
        return 1
    return length // stride if stride else 1


def blocks(lines):
    """Yield (line_no, type, address, title, next_address, [sub-directive lines])."""
    heads = [(i, m) for i, l in enumerate(lines) for m in [ENTRY.match(l.rstrip())] if m]
    for k, (i, m) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        nxt = parse_address(heads[k + 1][1].group(2)) if k + 1 < len(heads) else None
        subs = [(j, SUB.match(lines[j].rstrip())) for j in range(i + 1, end)]
        yield i, m.group(1), parse_address(m.group(2)), m.group(3) or '', nxt, \
            [(j, s) for j, s in subs if s]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ctl')
    ap.add_argument('--min-records', type=int, default=10)
    ap.add_argument('--min-span', type=int, default=40)
    a = ap.parse_args()

    with open(a.ctl, encoding='utf-8') as f:
        lines = f.read().splitlines()

    findings = []
    for i, typ, addr, title, nxt, subs in blocks(lines):
        if typ not in 'bgwt':
            continue
        if not subs:
            span = (nxt - addr) if nxt else 0
            if span >= a.min_span:
                findings.append((i + 1, 'UNDECLARED',
                                 f'{span} bytes with no sub-directive - the record size is '
                                 f'stated in prose only, so no element is annotated',
                                 typ, addr, title))
            continue
        for j, s in subs:
            r = records(s.group(3))
            if r >= a.min_records:
                findings.append((j + 1, 'UNINDEXED',
                                 f'one directive stands in for {r} records - give each its '
                                 f'own annotated sub-line',
                                 typ, addr, title))

    if not findings:
        print('array elements: all annotated')
        return 0

    print(f'Found {len(findings)} unannotated array(s):')
    print()
    for ln, kind, msg, typ, addr, title in findings:
        print(f'  Line {ln}: {kind} — {msg}')
        print(f'    in {typ} ${addr:04X} {title}'.rstrip())
        print()
    return 1


if __name__ == '__main__':
    sys.exit(main())
