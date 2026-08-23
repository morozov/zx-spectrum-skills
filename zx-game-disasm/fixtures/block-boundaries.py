#!/usr/bin/env python3
"""Print the span splice_ctl.py gives each block of a fixture .ctl.

Each block in the fixture is a boundary that, read wrong, silently destroys a
line: a `u` block is a header, so a fragment for the block above stops at it; a
non-`label=` directive at the next header's address belongs to that header, not
to the previous block; a span may start with more than one directive line; and
the pre-flight `--check-only` window must agree with the write path on all of
it. A wrong boundary reports nothing — the splice just comes out short.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import splice_ctl as S                                        # noqa: E402

lines = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'block-boundaries.ctl')).read().splitlines()
for index, line in enumerate(lines):
    header = S.HEADER.match(line)
    if not header:
        continue
    start, end = S.block_span(lines, index)
    print('%s span %d..%d' % (header.group(0), start + 1, end))
    for offset in range(start, end):
        print('    %s' % lines[offset])
