#!/usr/bin/env python3
"""
Hold every label to the address range its family owns.

A project declares its label families in its `AGENTS.md`, as data:

    <!-- label-families
    spr_ $F000-$F7FF
    slot_ $C000-$C7FF
    -->

Each line is a prefix and the inclusive address range that prefix owns. A prefix
may own several ranges, one line each. A prefix's stem is the prefix without its
trailing `_`, and a title names a family when one of its words starts with that
stem: `spr` names "sprite", `slot` names "slots".

Kinds:

  LABEL_FAMILY  a label at an address inside a declared range that lacks that
                range's prefix; a label carrying a declared prefix at an address
                outside every range of that prefix; or an entry title in one
                family's range that names another declared family and not its
                own, such as a title in the `slot_` range calling its contents
                sprites without calling them slots.

A label's prefix states what the bytes are. A copy slot labeled as the source
bitmap, or a source bitmap labeled as a slot, sends the reader to the wrong
bank, and no other check reads the prefix against the address.

Usage: validate_label_family.py CTL --agents AGENTS.md [--baseline FILE]
Exit 0 when clean, 1 when a label or title sits outside its family.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'label-family'

BLOCK_OPEN_RE = re.compile(r'<!--\s*label-families\b')
BLOCK_CLOSE_RE = re.compile(r'-->')
FAMILY_RE = re.compile(r'^\s*(\S+)\s+\$([0-9A-Fa-f]{1,4})\s*[-–]\s*\$([0-9A-Fa-f]{1,4})\s*$')

LABEL_RE = re.compile(r'^@ +(\$?[0-9A-Fa-f]+) +label=(\S+)')
ENTRY_RE = re.compile(r'^([bcgistuw]) +(\$?[0-9A-Fa-f]+)(?: +(\S.*))?$')



def stem(prefix):
    """Return a family prefix without its trailing separator: `slot_` is `slot`."""
    return prefix.rstrip('_-')


def stem_re(prefix):
    """Return a pattern matching a word that starts with a prefix's stem."""
    return re.compile(r'(?i)\b' + re.escape(stem(prefix)) + r'\w*')


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def read_families(path):
    """
    Return [(prefix, start, end)] from the `label-families` block of a file.

    None when the file holds no block, so a caller can say the project declares
    nothing rather than report it clean.
    """
    if not path or not os.path.exists(path):
        return None
    families, inside, found = [], False, False
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            if not inside:
                match = BLOCK_OPEN_RE.search(line)
                if match:
                    inside = found = True
                    line = line[match.end():]
                else:
                    continue
            closing = BLOCK_CLOSE_RE.search(line)
            body = line[:closing.start()] if closing else line
            row = FAMILY_RE.match(body)
            if row:
                families.append((row.group(1), int(row.group(2), 16),
                                 int(row.group(3), 16)))
            if closing:
                inside = False
    return families if found else None


def region_of(address, families):
    """Return the (prefix, start, end) whose range holds an address, or None."""
    for family in families:
        if family[1] <= address <= family[2]:
            return family
    return None


def check(lines, families):
    """Return (line_number, kind, message) findings for a .ctl's lines."""
    findings = []
    prefixes = sorted({prefix for prefix, _, _ in families}, key=len, reverse=True)
    for number, line in enumerate(lines, 1):
        match = LABEL_RE.match(line)
        if match:
            address, label = parse_address(match.group(1)), match.group(2)
            region = region_of(address, families)
            if region and not label.startswith(region[0]):
                findings.append((number, 'LABEL_FAMILY',
                                 f'{label} at ${address:04X} sits in the {region[0]} '
                                 f'range ${region[1]:04X}–${region[2]:04X} and lacks its '
                                 f'prefix: name it {region[0]}…'))
                continue
            for prefix in prefixes:
                if not label.startswith(prefix):
                    continue
                if not any(p == prefix and s <= address <= e for p, s, e in families):
                    ranges = ', '.join(f'${s:04X}–${e:04X}'
                                       for p, s, e in families if p == prefix)
                    findings.append((number, 'LABEL_FAMILY',
                                     f'{label} at ${address:04X} carries the {prefix} '
                                     f'prefix outside its range ({ranges}): the prefix '
                                     f'names a family these bytes are outside'))
                break
            continue
        entry = ENTRY_RE.match(line.rstrip())
        if entry and entry.group(3):
            address = parse_address(entry.group(2))
            region = region_of(address, families)
            if not region:
                continue
            title = entry.group(3)
            if stem_re(region[0]).search(title):
                continue
            for other in prefixes:
                if other != region[0] and stem_re(other).search(title):
                    findings.append((number, 'LABEL_FAMILY',
                                     f'the title "{title}" at ${address:04X} names the '
                                     f'{other} family and sits in the {region[0]} range: '
                                     f'say what the bytes hold, and that they are '
                                     f'{stem(region[0])}s'))
                    break
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('ctl', help='the .ctl file to validate')
    parser.add_argument('--agents', required=True,
                        help="the project's AGENTS.md, holding the label-families block")
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    families = read_families(args.agents)
    if families is None:
        print(f'{CHECK}: {os.path.basename(args.agents)} declares no '
              f'`<!-- label-families … -->` block, so no family is held to a range')
        return 0

    findings = check(lines, families)

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
        print(f'Found {len(new)} label(s) or title(s) outside their family:')
        print()
        for line_number, kind, message in new:
            print(f'  Line {line_number}: {kind} – {message}')
        print()
    elif not held and not stale:
        print(f'{CHECK}: {len(families)} family range(s) held, every label inside its own')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
