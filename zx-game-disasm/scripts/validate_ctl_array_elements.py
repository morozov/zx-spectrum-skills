#!/usr/bin/env python3
"""Every element of an array of records must be annotated individually.

An array laid out as one directive - or as no directive at all - documents the
span, not the contents. The reader gets "6400 bytes, 64 per level" and no way to
find level 12; nothing states where a record starts or what it is. This flags the
two forms:

  UNINDEXED  one sub-directive stands in for >= MIN records and >= MIN of them
             carry no annotation of their own
             (B $9000,6400,64 -> 100 records, one line)
  UNDECLARED an array-sized span with no sub-directive at all, so the record
             size lives only in prose

Both are fixed the same way: one annotated line per record, naming it - "Level
1", "Level 2". SkoolKit offers two spellings and this check accepts either. One
`B` sub-directive per record carries the name in its own description; one `B`
carrying the stride, with a `  $ADDRESS text` line comment per record, carries it
on the rendered statement. Both put one named row per record in the listing,
which is the whole claim.

Not every byte run is a record array, and demanding per-element annotation of one
that is not would be a false finding - the sort a baseline must never be used to
bury. Four things disqualify a span, each of them the .ctl already saying what
the bytes are:

  RENDER    a render macro reads the span's bytes, from the block's own prose or
            from a code partner the two name each other through. The macro is the
            schema and the render is its proof, exactly as
            `validate_ctl_data_structure.py` reads it; a sprite's pixel rows, a
            screen's cells and a tune's note bytes are not records to index. The
            discharge reaches as far as the macro reads and no further, so a
            block a render covers in part keeps its drawn spans exempt and is
            asked about the rest.
  WORD      the entry is `w`. The entry type declares the element - one `DEFW`
            per word, one element per row - so no record size hides in prose.
  SCALAR    the stride is one byte. A scalar has no fields, so there is no record
            layout to state; the block's `D` states the index rule instead, and
            `lint-data-structure` gates that it does.
  GEOMETRY  a span of a page or more laid out at a power-of-two stride of 16
            bytes or more. A record size is whatever its fields sum to - 3, 4, 9,
            81 - and lands on a power of two by coincidence; a page-sized region
            cut at a power-of-two width is a geometry, not a record: a screen, a
            sprite bank, a tile grid, a work buffer. The cost is that a genuine
            array of 16- or 32-byte records spanning a page goes unasked; the
            schema check still holds it to declaring that stride and tiling.

Two floors sit under all four, and they are thresholds rather than declarations:
a span shorter than `--min-span` bytes or cut into fewer than `--min-records`
records is too small to be asked, and a span is reported only once `--min-records`
of its records are unnamed, so a nearly-complete table is not failed over its
last few rows.

Usage: validate_ctl_array_elements.py CTL [--min-records N] [--min-span N]
Exit 0 when clean, 1 when any array is unannotated.
"""
import argparse
import collections
import re
import sys

import ctl_baseline
import validate_ctl_data_structure as schema

CHECK = 'array-elements'

# The two floors, in one place: `main()` takes them as its argparse defaults and
# `unannotated_arrays` as its keyword defaults, so the gauge that calls the
# function measures what the gate measures without restating a number.
MIN_RECORDS = 10
MIN_SPAN = 40

# Addresses take the same forms the sibling linters accept - `$HEX` or plain
# decimal - so a .ctl that has not been through ctl_to_hex.py gets reported on
# rather than matching nothing and reading clean.
ADDR = r'(\$?[0-9A-Fa-f]+)'
ENTRY = re.compile(r'^([bcgistuw]) +%s(?: +(\S.*))?$' % ADDR)
SUB = re.compile(r'^([BCSTWM]) +%s((?:,[^\s]+)*)(?: +(\S.*))?$' % ADDR)
# A line comment on a rendered statement: an indent, an address, an optional
# length tail, then the text. Text is required - `  $A11E` with nothing after it
# closes a multi-line comment and names nothing. Any indent counts, as
# `validate_ctl_instruction_order.py` reads it: SkoolKit renders a four-space
# comment exactly as it renders a two-space one, and a check in `lint` that
# disagreed would fail a build over a formatting choice SkoolKit accepts. The
# address must be `$hex` or all digits here, unlike ADDR: after an indent a bare
# `B` is a directive letter far more often than it is the address 11.
COMMENT = re.compile(r'^ +(\$[0-9A-Fa-f]+|[0-9]+)((?:,[^\s]+)*) +(\S.*)$')

# The smallest span the GEOMETRY exemption applies to, and the smallest stride.
# Both bounds are load-bearing: a 4-byte stride is a 2x2 cell group in one
# project and a record of four fields in the next, and below a page a
# power-of-two stride is ordinary in real records.
GEOMETRY_SPAN = 256
GEOMETRY_STRIDE = 16


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def layout(args):
    """Return (length, stride) for a sub-directive's operand tail, or None."""
    parts = [p for p in args.split(',') if p]
    if len(parts) < 2:
        return None
    try:
        return int(parts[0], 0), int(parts[1].split(':')[0], 0)
    except ValueError:
        return None


def comment_address(text):
    """Return the address a line comment sits on, or None when the line is not one."""
    match = COMMENT.match(text)
    if not match:
        return None
    return parse_address(match.group(1))


def unannotated(address, length, stride, comments):
    """
    Return how many of a span's records no line comment names.

    One comment annotates one record - the one its address falls in. A length on
    the comment does not widen that: `  $F000,120 The thirty enemy records` is a
    single braced comment spanning thirty `DEFB` rows in the listing, which is
    the shape the check exists to catch, not a fix for it.
    """
    count = 0
    for start in range(address, address + length - length % stride, stride):
        if not any(start <= at < start + stride for at in comments):
            count += 1
    return count


def blocks(lines):
    """Yield (line_no, type, address, next_address, subs, comments) per entry."""
    heads = [(i, m) for i, l in enumerate(lines) for m in [ENTRY.match(l.rstrip())] if m]
    for k, (i, m) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        nxt = parse_address(heads[k + 1][1].group(2)) if k + 1 < len(heads) else None
        subs, comments = [], []
        for j in range(i + 1, end):
            text = lines[j].rstrip()
            sub = SUB.match(text)
            if sub:
                subs.append((j, sub))
                continue
            at = comment_address(text)
            if at is not None:
                comments.append(at)
        yield i, m.group(1), parse_address(m.group(2)), nxt, subs, comments


def is_geometry(length, stride):
    """Whether a span reads as a memory region cut at a width, not as records."""
    return (length >= GEOMETRY_SPAN
            and stride >= GEOMETRY_STRIDE
            and stride & (stride - 1) == 0)


Run = collections.namedtuple('Run', 'kind entry line address records missing span')


def unannotated_arrays(lines, by_address=None,
                       min_records=MIN_RECORDS, min_span=MIN_SPAN):
    """
    Return every array span a .ctl leaves unannotated, in file order.

    This is the one place that decides *which spans qualify*. `main()` turns the
    result into findings and `coverage_report.py` counts it as the ARRAYS metric,
    so the gate and the gauge cannot answer differently about the same file: an
    exemption added here reaches both, and neither can gain one the other lacks.

    `lines` is the .ctl split into lines. `by_address` is the block map from
    `validate_ctl_data_structure.parse_ctl`, which is what the RENDER exemption
    reads; pass `None` to run without it - every other exemption still applies,
    and rendered assets then come back as findings.

    Each item is a `Run`:

      kind     'UNINDEXED' - one sub-directive stands in for `records` records
               and `missing` of them carry no annotation of their own;
               'UNDECLARED' - an array-sized span with no sub-directive at all
      entry    1-based line of the entry head
      line     1-based line the finding sits on: the sub-directive for
               UNINDEXED, the entry head for UNDECLARED
      address  the entry's address
      records  records the directive stands in for; 0 for UNDECLARED
      missing  records carrying no annotation; 0 for UNDECLARED, where nothing
               declares a record at all
      span     bytes the span covers
    """
    runs = []
    for i, typ, addr, nxt, subs, comments in blocks(lines):
        if typ not in 'bgwt':
            continue
        block = (by_address or {}).get(addr)
        covered = set()
        if block is not None:
            covered = schema.rendered_coverage(block, by_address)
            if schema.render_discharges(block, covered):
                # Drawn whole, or drawn by a macro whose extent the text does not
                # state. `lint-data-structure` asks such a block nothing further,
                # and asking it here would be the same exemption at two
                # granularities: one definition, one verdict, both checks.
                continue

        if not subs:
            # `w` answers the question in the entry type: one `DEFW` per word is
            # one element per row, so nothing about the element size is left in
            # prose. Whether those words carry names is `lint-identity`'s.
            if typ == 'w':
                continue
            span = (nxt - addr) if nxt else 0
            if covered:
                span = sum(end - start
                           for start, end in schema.uncovered_runs(addr, span, covered))
            if span >= min_span:
                runs.append(Run('UNDECLARED', i + 1, i + 1, addr, 0, 0, span))
            continue

        for j, s in subs:
            shape = layout(s.group(3))
            if shape is None:
                continue
            length, stride = shape
            start = parse_address(s.group(2))
            if covered.issuperset(range(start, start + length)):
                # Drawn: the macro is this span's schema and the render is its
                # proof, which is what `lint-data-structure` discharges here too.
                continue
            if stride <= 1 or length < min_span or is_geometry(length, stride):
                continue
            if length // stride < min_records:
                continue
            missing = unannotated(start, length, stride, comments)
            if missing >= min_records:
                runs.append(Run('UNINDEXED', i + 1, j + 1, addr,
                                length // stride, missing, length))
    return runs


def main():
    ap = argparse.ArgumentParser(
        description='Validate that every record of an array in a .ctl is annotated.')
    ap.add_argument('ctl')
    ap.add_argument('--min-records', type=int, default=MIN_RECORDS)
    ap.add_argument('--min-span', type=int, default=MIN_SPAN)
    ctl_baseline.add_arguments(ap)
    a = ap.parse_args()

    try:
        with open(a.ctl, encoding='utf-8') as f:
            lines = f.read().splitlines()
        _, _, by_address = schema.parse_ctl(a.ctl)
    except FileNotFoundError:
        print(f'Error: File not found: {a.ctl}')
        return 1

    findings = []
    for run in unannotated_arrays(lines, by_address,
                                  min_records=a.min_records, min_span=a.min_span):
        if run.kind == 'UNDECLARED':
            findings.append((run.line, run.kind,
                             f'{run.span} bytes with no sub-directive - the record size is '
                             f'stated in prose only, so no element is annotated'))
        else:
            findings.append((run.line, run.kind,
                             f'one directive stands in for {run.records} records, '
                             f'{run.missing} of them unannotated - give each record its '
                             f'own named line'))

    if a.write_baseline:
        if not a.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            a.baseline, CHECK,
            *ctl_baseline.write(a.baseline, CHECK, findings, lines))
        return 0

    new, held, stale = ctl_baseline.partition(a.baseline, CHECK, findings, lines,
                                              report_stale=not a.ignore_stale)

    if new:
        print(f'Found {len(new)} unannotated array(s):')
        print()
        for ln, kind, msg in new:
            print(f'  Line {ln}: {kind} - {msg}')
            print(f'    {lines[ln - 1].strip()}')
            print()
    elif not held:
        print('array elements: all annotated')

    ctl_baseline.report(a.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
