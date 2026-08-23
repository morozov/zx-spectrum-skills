#!/usr/bin/env python3
"""
Splice a per-routine .ctl fragment into the canonical .ctl by address — the
mechanical merge that makes a parallel Worker fan-out safe.

A depth Worker owns one or more code routines and returns a *fragment*: the `.ctl`
directives for those routines' address ranges only (entry label, `c` title, `D`,
`N`, `R`, and the per-instruction comment lines), and nothing outside them. This
tool replaces each block entry in the base `.ctl` with the fragment's version
of that block, in place. Because the `.ctl` is address-ordered and fragments are
address-disjoint, the result is deterministic and order-preserving — no
hand-merging, no re-derivation.

Two invariants are enforced, and a violation is a hard error (the fragment is not
cleanly splice-able and the Worker overstepped its range):

  - every block entry in the fragment must exist in the base (same address);
  - the fragment must contain *only* lines whose address lies inside one of its
    own blocks — no stray directive in a shared region (e.g. a label added to
    the low-RAM variable block, which is a separate single-owner task).

A third condition is reported but does not fail: an `@` directive that sits in the
replaced range and that the fragment does not carry forward is deleted by the
splice, and each one is named on stderr. It is a warning rather than an error
because the two cases are indistinguishable in the fragment — a Worker who
re-typed a block and lost an `@ label=` and a Worker whose task was to remove a
now-unnecessary `@ keep` hand in the same bytes. Only the author knows which, so
the tool reports and the author judges. Making it fatal would also leave a
deliberate removal with no way through `make verify-frag`, which takes the
fragment path and nothing else.

A directive whose *value* changed is not a drop: the comparison keys on address
plus directive name, so re-pointing an `@ label=` is silent and removing it is
not. Sub-block comment lines are not compared — re-annotating a routine rewrites
every one of them, so their absence carries no signal.

After splicing, run `make`: the splice is structural; byte-identity, the linters
and correctness are still proven by the build.

Usage: splice_ctl.py <base.ctl> <fragment.ctl> [-o out.ctl]   (default: in place)
       splice_ctl.py --check-only <base.ctl> <fragment.ctl>
"""

import argparse
import re
import sys

# Addresses in a .ctl are either `$HEX` (the recommended form, matching the hex
# skool) or bare decimal — accept both.
_A = r'(\$?[0-9A-Fa-f]+)'
HEADER = re.compile(r'^([bcgistuw]) ' + _A + r'\b')   # a block-entry line, `u` included
ADDR_LINE = re.compile(r'^(?:[@ ]?[A-Za-z*]?\s*)?' + _A + r'\b')
DIRECTIVE = re.compile(r'^@ ' + _A + r' ([A-Za-z][-\w]*)')  # any `@ ADDR name…` line


def paddr(s):
    """Parse a .ctl address token: `$HEX` as hex, bare digits as decimal."""
    return int(s[1:], 16) if s.startswith('$') else int(s)


def load(path):
    with open(path, encoding='utf-8') as f:
        return f.read().splitlines()


def directives_above(lines, index, addr):
    """The first index of the run of `@ ADDR …` lines directly above `index`
    that carry `addr`.

    Backing up over `label=` alone would leave every other directive at the
    next header's address inside the *previous* block's span, so a splice would
    delete it and the fixed asm would then warn about an unreplaced address — a
    red gate two steps from the edit, naming the wrong file. Every directive at
    an address belongs to the block that address starts, and there can be more
    than one.
    """
    first = index
    while first > 0:
        above = DIRECTIVE.match(lines[first - 1])
        if not above or paddr(above.group(1)) != addr:
            break
        first -= 1
    return first


def block_span(lines, ci):
    """Span (start, end) of the block whose `c`/`b`/... entry is at index ci,
    pulling in the preceding `@ ADDR …` directives for the same address."""
    addr = paddr(HEADER.match(lines[ci]).group(2))
    start = directives_above(lines, ci, addr)
    end = len(lines)
    for k in range(ci + 1, len(lines)):
        if HEADER.match(lines[k]):
            # every directive at the next header's address belongs to it
            end = directives_above(lines, k, paddr(HEADER.match(lines[k]).group(2)))
            break
    return start, end


def entry_blocks(lines):
    """Map addr -> (start, end) for every block entry, whatever its type.

    Data entries are spliced exactly as code entries are, so this must not be
    restricted to `c`. Gating on a code block would refuse every
    `b`/`g`/`u`/`i` fragment outright."""
    out = {}
    for k, ln in enumerate(lines):
        m = HEADER.match(ln)
        if m:
            out[paddr(m.group(2))] = block_span(lines, k)
    return out


def directives(lines):
    """Map (address, directive-name) -> the line, for every `@ ADDR name…` line."""
    out = {}
    for ln in lines:
        m = DIRECTIVE.match(ln)
        if m:
            out[(paddr(m.group(1)), m.group(2))] = ln.strip()
    return out


def report_drops(base_lines, frag_lines):
    """Name on stderr every `@` directive in base_lines that frag_lines does not
    carry forward at the same address, and return how many there were.

    base_lines are the lines a splice replaces, frag_lines the ones it puts in
    their place. Reporting only: the caller decides what a drop means."""
    kept = directives(frag_lines)
    dropped = [ln for key, ln in sorted(directives(base_lines).items()) if key not in kept]
    for ln in dropped:
        print(f"splice_ctl: WARNING: the fragment drops `{ln}`", file=sys.stderr)
    return len(dropped)


def drop_advice(n):
    """The one-line trailer for n>0 dropped directives, or None for none."""
    if not n:
        return None
    return (f"splice_ctl: {n} directive(s) in the replaced range are absent from the "
            f"fragment and the splice deletes them. Carry each one forward in the "
            f"fragment unless removing it was the task.")


def span_drops(base, frag):
    """Report drops over the address span a fragment replaces, rather than
    block-for-block: from its lowest block address up to the next base block that
    starts above its highest. Returns how many were reported.

    This is the view a caller that splices by span has — a fragment may retype a
    block (`b` -> `c`), which block-for-block matching cannot pair up and would
    silently skip."""
    fa = [paddr(HEADER.match(ln).group(2)) for ln in frag if HEADER.match(ln)]
    if not fa:
        sys.exit("fragment contains no block-entry line")
    lo, top = min(fa), max(fa)
    above = sorted(a for a in (paddr(HEADER.match(ln).group(2)) for ln in base
                              if HEADER.match(ln)) if a > top)
    hi = above[0] if above else 10 ** 9
    covered = [ln for ln in base
               if DIRECTIVE.match(ln) and lo <= paddr(DIRECTIVE.match(ln).group(1)) < hi]
    return report_drops(covered, frag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('fragment')
    ap.add_argument('-o', '--out')
    ap.add_argument('--check-only', action='store_true',
                    help='report the directives the fragment drops and write nothing; '
                         'for a caller that performs its own splice')
    args = ap.parse_args()

    base = load(args.base)
    frag = load(args.fragment)

    # The invariants below are about splicing, so --check-only skips them: it must
    # still speak for a fragment this tool would refuse to splice itself.
    if args.check_only:
        advice = drop_advice(span_drops(base, frag))
        if advice:
            print(advice, file=sys.stderr)
        return 0

    base_blocks = entry_blocks(base)
    frag_blocks = entry_blocks(frag)

    if not frag_blocks:
        sys.exit("fragment contains no block-entry line")

    # Invariant 2: every fragment line must fall inside one of the fragment's own
    # block address ranges (computed from the base's block extents).
    owned = []
    for addr in frag_blocks:
        if addr not in base_blocks:
            sys.exit(f"fragment block at {addr} not present in base — not splice-able")
        bs, be = base_blocks[addr]
        # `bs` may sit above a run of `@ ADDR …` directives, not just one
        # `label=` line, so find the header rather than assuming its offset.
        head = next(i for i in range(bs, be) if HEADER.match(base[i]))
        lo = paddr(HEADER.match(base[head]).group(2))
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
    dropped = 0
    for addr in sorted(frag_blocks, reverse=True):
        bs, be = base_blocks[addr]
        fs, fe = frag_blocks[addr]
        dropped += report_drops(base[bs:be], frag[fs:fe])
        result[bs:be] = frag[fs:fe]

    out = args.out or args.base
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result) + '\n')
    print(f"spliced {len(frag_blocks)} block(s) into {out}: "
          f"{', '.join(str(a) for a in sorted(frag_blocks))}")
    advice = drop_advice(dropped)
    if advice:
        print(advice, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
