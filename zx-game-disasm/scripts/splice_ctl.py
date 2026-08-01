#!/usr/bin/env python3
"""
Splice a per-routine .ctl fragment into the canonical .ctl by address — the
mechanical merge that makes a parallel Worker fan-out safe.

A depth Worker owns one or more code routines and returns a *fragment*: the `.ctl`
directives for those routines' address ranges only (entry label, `c` title, `D`,
`N`, `R`, and the per-instruction comment lines), and nothing outside them. This
tool replaces each `c ADDR` block in the base `.ctl` with the fragment's version
of that block, in place. Because the `.ctl` is address-ordered and fragments are
address-disjoint, the result is deterministic and order-preserving — no
hand-merging, no re-derivation.

Two invariants are enforced, and a violation is a hard error (the fragment is not
cleanly splice-able and the Worker overstepped its range):

  - every `c ADDR` block in the fragment must exist in the base (same address);
  - the fragment must contain *only* lines whose address lies inside one of its
    own `c` blocks — no stray directive in a shared region (e.g. a label added to
    the low-RAM variable block, which is a separate single-owner task).

After splicing, run the `.ctl` linters and `make verify`: the splice is structural;
byte-identity and correctness are still proven by the build.

Usage: splice_ctl.py <base.ctl> <fragment.ctl> [-o out.ctl]   (default: in place)
"""

import argparse
import re
import sys

# Addresses in a .ctl are either `$HEX` (the recommended form, matching the hex
# skool) or bare decimal — accept both.
_A = r'(\$?[0-9A-Fa-f]+)'
HEADER = re.compile(r'^([bcwtsgi]) ' + _A + r'\b')     # a block-entry line
CLINE = re.compile(r'^c ' + _A + r'\b')                # a code-block entry
LABEL = re.compile(r'^@ ' + _A + r' label=')
ADDR_LINE = re.compile(r'^(?:[@ ]?[A-Za-z*]?\s*)?' + _A + r'\b')


def paddr(s):
    """Parse a .ctl address token: `$HEX` as hex, bare digits as decimal."""
    return int(s[1:], 16) if s.startswith('$') else int(s)


def load(path):
    with open(path, encoding='utf-8') as f:
        return f.read().splitlines()


def block_span(lines, ci):
    """Span (start, end) of the block whose `c`/`b`/... entry is at index ci,
    pulling in an immediately-preceding `@ ADDR label=` line for the same address."""
    addr = paddr(HEADER.match(lines[ci]).group(2))
    start = ci
    if ci > 0 and LABEL.match(lines[ci - 1]) and paddr(LABEL.match(lines[ci - 1]).group(1)) == addr:
        start = ci - 1
    end = len(lines)
    for k in range(ci + 1, len(lines)):
        if HEADER.match(lines[k]):
            end = k
            # a label line immediately before the next header belongs to it
            if k > 0 and LABEL.match(lines[k - 1]) and \
               paddr(LABEL.match(lines[k - 1]).group(1)) == paddr(HEADER.match(lines[k]).group(2)):
                end = k - 1
            break
    return start, end


def code_blocks(lines):
    """Map addr -> (start, end) for every `c ADDR` block."""
    out = {}
    for k, ln in enumerate(lines):
        m = CLINE.match(ln)
        if m:
            out[paddr(m.group(1))] = block_span(lines, k)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('fragment')
    ap.add_argument('-o', '--out')
    args = ap.parse_args()

    base = load(args.base)
    frag = load(args.fragment)
    base_blocks = code_blocks(base)
    frag_blocks = code_blocks(frag)

    if not frag_blocks:
        sys.exit("fragment contains no `c ADDR` block")

    # Invariant 2: every fragment line must fall inside one of the fragment's own
    # c-block address ranges (computed from the base's block extents).
    owned = []
    for addr in frag_blocks:
        if addr not in base_blocks:
            sys.exit(f"fragment block c {addr} not present in base — not splice-able")
        bs, be = base_blocks[addr]
        lo = paddr(HEADER.match(base[bs] if not LABEL.match(base[bs]) else base[bs + 1]).group(2))
        hi = (paddr(HEADER.match(base[be]).group(2)) if be < len(base) and HEADER.match(base[be])
              else 10 ** 9)
        owned.append((lo, hi))
    for ln in frag:
        m = ADDR_LINE.match(ln)
        if not m:
            continue
        a = paddr(m.group(1))
        if not any(lo <= a < hi for lo, hi in owned):
            sys.exit(f"fragment touches address {a} outside its own routine ranges "
                     f"(a shared region — make it a separate task): {ln.strip()[:70]}")

    # Replace each owned block, working high address to low so indices stay valid.
    result = list(base)
    for addr in sorted(frag_blocks, reverse=True):
        bs, be = base_blocks[addr]
        fs, fe = frag_blocks[addr]
        result[bs:be] = frag[fs:fe]

    out = args.out or args.base
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result) + '\n')
    print(f"spliced {len(frag_blocks)} block(s) into {out}: "
          f"{', '.join(str(a) for a in sorted(frag_blocks))}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
