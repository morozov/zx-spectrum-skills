#!/usr/bin/env python3
"""
Build the relocation proof's permuted image: move one block and reassemble.

The block is a label and the indented lines under it. It is moved to just
before a given line of the assembly, so every block it jumps is displaced by its
size. The build is then checked against the baseline:

- the baseline assembly reassembles to the baseline image;
- the image size holds;
- every byte below the floor is unchanged;
- every label in the jumped span moves by the block's size, the moved block's
  labels move with it, and every other label stays put;
- outside the permuted span, a difference is at most 2 bytes long, an operand
  that resolved to a moved address.

The project's TOML config names each permute under [permute.NAME], with `move`
(the label) and `before` (the line it lands before). [control] holds a `replace`
and a `with` string: --control swaps one operand for a raw address, so the
build's trace must diverge.

Usage:
    permute.py ASM BASELINE OUT --config TOML --permute NAME --floor ADDR --org ORG
               [--control]
"""

import argparse
import os
import re
import subprocess
import tomllib

LABEL = re.compile(r'^([A-Za-z_]\w*):')


def take_block(lines, label):
    """Return (start, end) covering `label:` and the body lines under it."""
    i = lines.index(label + ':')
    j = i + 1
    while j < len(lines) and lines[j].startswith('  '):
        j += 1
    return i, j


def assemble(lines, out_bin):
    """Assemble `lines` to out_bin and return its symbol table."""
    asm = out_bin + '.asm'
    sym = out_bin + '.sym'
    with open(asm, 'w') as handle:
        handle.write('\n'.join(lines) + '\n')
    subprocess.run(['pasmo', '--bin', asm, out_bin, sym], check=True)
    table = {}
    for line in open(sym):
        parts = line.split()
        if len(parts) >= 2:
            table[parts[0].rstrip(':')] = int(parts[-1].rstrip('Hh'), 16)
    return table


def diff_runs(a, b, lo, hi):
    """Yield (offset, length) for each maximal run of differing bytes in [lo,hi)."""
    i = lo
    while i < hi:
        if a[i] != b[i]:
            j = i
            while j < hi and a[j] != b[j]:
                j += 1
            yield i, j - i
            i = j
        else:
            i += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('asm', help='the gated assembly')
    parser.add_argument('baseline', help='the image it reassembles to')
    parser.add_argument('out', help='the permuted image to write')
    parser.add_argument('--config', required=True, help='the project\'s relocation TOML')
    parser.add_argument('--permute', required=True, help='the [permute.NAME] to build')
    parser.add_argument('--floor', required=True, type=lambda s: int(s, 0),
                        help='RELOC_FLOOR: every byte below it must be unchanged')
    parser.add_argument('--org', required=True, type=lambda s: int(s, 0),
                        help='the address of the image\'s first byte')
    parser.add_argument('--control', action='store_true',
                        help='also swap the [control] operand for its raw address')
    args = parser.parse_args()

    config = tomllib.load(open(args.config, 'rb'))
    permute = config['permute'][args.permute]
    move = permute['move']
    lines = open(args.asm).read().splitlines()
    labels = {m.group(1) for m in map(LABEL.match, lines) if m}

    base = open(args.baseline, 'rb').read()
    base_sym = assemble(lines, args.out + '.base')
    if open(args.out + '.base', 'rb').read() != base:
        raise SystemExit(f'permute: {args.asm} does not reassemble to {args.baseline}')

    i, j = take_block(lines, move)
    following = next((m.group(1) for m in map(LABEL.match, lines[j:]) if m), None)
    if following is None:
        raise SystemExit(f'permute: no label follows {move}')
    old = base_sym[move]
    size = base_sym[following] - old
    inside = {name for name in labels if old <= base_sym[name] < old + size}

    block = lines[i:j]
    del lines[i:j]
    d = lines.index(permute['before'])
    lines[d:d] = block
    if args.control:
        control = config['control']
        src = '\n'.join(lines)
        if src.count(control['replace']) != 1:
            raise SystemExit('permute: control operand not found exactly once')
        lines = src.replace(control['replace'], control['with']).split('\n')
    var_sym = assemble(lines, args.out)
    var = open(args.out, 'rb').read()

    new = var_sym[move]
    if new < old:
        lo, hi, jumped, shift = new, old + size, (new, old), size
    else:
        lo, hi, jumped, shift = old, new + size, (old + size, new + size), -size

    if len(var) != len(base):
        raise SystemExit(f'permute: size {len(var)} != {len(base)}')
    floor = args.floor - args.org
    if var[:floor] != base[:floor]:
        raise SystemExit(f'permute: bytes below ${args.floor:04X} changed')
    for name in sorted(labels):
        if name in inside:
            want = base_sym[name] + new - old
        elif jumped[0] <= base_sym[name] < jumped[1]:
            want = base_sym[name] + shift
        else:
            want = base_sym[name]
        if var_sym[name] != want:
            raise SystemExit(f'permute: {name} at ${var_sym[name]:04X}, want ${want:04X}')
    for lo_off, hi_off in ((0, lo - args.org), (hi - args.org, len(base))):
        for a, n in diff_runs(base, var, lo_off, hi_off):
            if n > 2:
                raise SystemExit(f'permute: {n} bytes differ at ${a + args.org:04X}, '
                                 'outside the permuted span')

    span = hi - lo
    diff = sum(1 for a, b in zip(base[lo - args.org:hi - args.org],
                                 var[lo - args.org:hi - args.org]) if a != b)
    os.remove(args.out + '.base')
    print(f'  permute: OK  {len(var)} bytes; {move} ({size} bytes) '
          f'${old:04X} -> ${new:04X}; span ${lo:04X}-${hi - 1:04X} shifted by '
          f'{shift:+d}; {diff}/{span} bytes differ across it')


if __name__ == '__main__':
    main()
