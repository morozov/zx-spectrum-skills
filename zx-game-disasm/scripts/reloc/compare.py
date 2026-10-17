#!/usr/bin/env python3
"""
Compare two oracle.py dumps field by field.

Each frame's record is the config's `regions` in order, then a 32-byte screen
digest. The report names every sampled address that differs and on how many
frames, and the exit status is 1 when any frame differs.

Usage:
    compare.py A B --config TOML [--exclude=$ADDR:LEN ...]
"""

import argparse
import sys
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('a', help='the baseline dump')
    parser.add_argument('b', help='the dump to compare')
    parser.add_argument('--config', required=True, help='the project\'s relocation TOML')
    parser.add_argument('--exclude', action='append', default=[],
                        help='$ADDR:LEN to leave out of the comparison')
    args = parser.parse_args()

    regions = tomllib.load(open(args.config, 'rb'))['regions']
    rec = sum(n for _, n in regions) + 32

    def addr_of(off):
        for base, n in regions:
            if off < n:
                return base + off
            off -= n
        return None  # screen digest

    excl = set()
    for spec in args.exclude:
        start, length = spec.split(':')
        base = int(start.lstrip('$'), 16)
        excl |= set(range(base, base + int(length)))

    a = open(args.a, 'rb').read()
    b = open(args.b, 'rb').read()
    if len(a) != len(b):
        raise SystemExit(f'compare: dump sizes differ ({len(a)}, {len(b)})')
    frames = len(a) // rec
    diff_fields, diff_frames, scr_frames = {}, set(), set()
    for i in range(len(a)):
        if a[i] == b[i]:
            continue
        f, o = divmod(i, rec)
        ad = addr_of(o)
        if ad is None:
            scr_frames.add(f)
            diff_frames.add(f)
            continue
        if ad in excl:
            continue
        diff_fields[ad] = diff_fields.get(ad, 0) + 1
        diff_frames.add(f)

    print(f'frames: {frames}, record: {rec} bytes ({len(regions)} regions + 32-byte screen digest)')
    print(f"excluded: {' '.join(f'${x:04X}' for x in sorted(excl)) or 'nothing'}")
    print(f'screen digest differs on {len(scr_frames)} frame(s)')
    for ad, n in sorted(diff_fields.items()):
        print(f'  ${ad:04X} differs on {n} frame(s)')
    print('RESULT:', 'IDENTICAL' if not diff_frames else f'DIFFER on {len(diff_frames)} frame(s)')
    sys.exit(0 if not diff_frames else 1)


if __name__ == '__main__':
    main()
