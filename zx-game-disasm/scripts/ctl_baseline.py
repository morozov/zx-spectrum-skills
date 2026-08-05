#!/usr/bin/env python3
"""Known-failing baseline shared by the .ctl linters that gate on findings.

A check worth running is worth running in the gate, and a mature project has
findings the day the check is written. Left advisory, the check is never run and
the defect ships; made blocking with no escape, it is switched off. The baseline
is the third option: the project records what it already fails, the gate holds
that line, and shrinking the file is how the debt clears.

The file lists one accepted finding per line:

    <check> <KIND> <$ADDRESS>  <the message as recorded>

The first three fields are the key; the rest is for the reader and is ignored by
the comparison. Regenerating rewrites the section belonging to the check that
runs and leaves every other check's lines untouched, so a message that has
drifted shows up as a diff without failing anything.

Four rules give the file its shape:

- a finding whose key is absent fails the gate - that is the new defect;
- a key present for a check that ran, which the check no longer reports, fails
  the gate too - a fixed finding must leave the file in the commit that fixes
  it, so the baseline cannot rot into a permanent excuse;
- a key is only ever compared against the check that wrote it, so a project may
  baseline one check and gate another cleanly;
- a key may repeat, and the count is part of the comparison. Two findings of one
  kind at one address are two lines, and a third fails the gate.

The key is the address on the directive the finding points at, never the line
number: line numbers churn on every unrelated edit above them, and message text
changes when a neighboring directive resizes. Counting repeats is what keeps
that from swallowing a second finding at an address already listed - splitting
one undescribed directive into two undescribed directives adds a line, so the
gate sees it - while a directive that merely moves down the file does not.

A check whose findings do not live on a directive supplies its own third field
through `token_of`. A phrase in a `.ref` catalog has no address to key on, and
the address of the `.ctl` line that happens to carry it is not its identity - the
phrase is. Counting repeats then reads as "13 occurrences of this phrase are
accepted", and the fourteenth fails the gate.

Regeneration is routine, which makes a silent regeneration the realistic way a
finding gets buried. So `write` names every key it adds, and every key it drops:
a file that grows is debt taken on, not debt inherited.
"""

import collections
import os
import re

# Every .ctl directive line names its address in one of two shapes: a directive
# letter and the address (`b $F108`, `B $F108,1`, `@ $F108 label=`), or the
# two-space line comment (`  $F108 text`).
ADDRESS_RE = re.compile(r'^(?:[@A-Za-z] +|  )(\$?[0-9A-Fa-f]+)')

HEADER = """\
# Known-failing .ctl lint findings, accepted as this project's baseline.
#
# One accepted finding per line: `<check> <KIND> <$ADDRESS>  <message>`. The
# first three fields are the key; the message is for the reader. A key may
# repeat, and the count counts: two findings at one address are two lines.
#
# The gate fails on a finding that is not listed here, and on a line here that
# its check no longer reports - so a fix must remove its line in the same commit,
# and the file cannot become a permanent excuse. Shrinking it is how it goes away.
#
# Regenerate with `make lint-baseline`. Never add a line by hand to silence a
# finding you introduced: the baseline records debt inherited by the check, not
# debt taken on after it.
"""


def add_arguments(parser):
    """Add the baseline options to a linter's argument parser."""
    parser.add_argument('--baseline',
                        help='file of accepted known-failing findings; findings it '
                             'lists do not fail the gate')
    parser.add_argument('--write-baseline', action='store_true',
                        help='rewrite this check\'s section of --baseline and exit 0, '
                             'rather than gating on them')
    parser.add_argument('--ignore-stale', action='store_true',
                        help='do not fail on baseline entries this run no longer '
                             'reports; for a spliced fragment, whose .ctl is a '
                             'fraction of the one the baseline was written from')


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def finding_key(check, line_number, kind, lines):
    """Return `check KIND $ADDRESS` for a finding reported at a source line."""
    text = lines[line_number - 1] if 0 < line_number <= len(lines) else ''
    match = ADDRESS_RE.match(text)
    if not match:
        return f'{check} {kind} ?'
    return f'{check} {kind} ${parse_address(match.group(1)):04X}'


def key_for(check, finding, lines, token_of=None):
    """
    Return one finding's baseline key.

    `token_of`, when given, maps the finding to the key's third field, for a
    check whose findings are not located by a .ctl directive address.
    """
    if token_of is None:
        return finding_key(check, finding[0], finding[1], lines)
    return f'{check} {finding[1]} {token_of(finding)}'


def read_entries(path):
    """Return the file's finding lines, stripped, without header or blanks."""
    if not path or not os.path.exists(path):
        return []
    entries = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and len(line.split(None, 3)) >= 3:
                entries.append(line)
    return entries


def load(path, check):
    """Return how many times each key is recorded for one check, as a Counter."""
    keys = collections.Counter()
    for entry in read_entries(path):
        fields = entry.split(None, 3)
        if fields[0] == check:
            keys[' '.join(fields[:3])] += 1
    return keys


def write(path, check, findings, lines, token_of=None):
    """
    Rewrite one check's lines in the baseline, leaving every other check's alone.

    `findings` are (line_number, kind, message, ...) tuples. Returns
    (recorded, added, dropped): how many lines this check now owns, and the keys
    that appeared and disappeared since the file was last written.
    """
    previous = load(path, check)
    kept = [e for e in read_entries(path) if e.split(None, 1)[0] != check]

    current = collections.Counter()
    recorded = []
    for finding in findings:
        key = key_for(check, finding, lines, token_of)
        current[key] += 1
        recorded.append(f'{key}  {finding[2]}')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(HEADER)
        for entry in sorted(kept + recorded):
            f.write(entry + '\n')

    return (len(recorded),
            sorted((current - previous).elements()),
            sorted((previous - current).elements()))


def partition(path, check, findings, lines, report_stale=True, token_of=None):
    """
    Split findings against the baseline.

    `findings` are (line_number, kind, ...) tuples. Returns (new, held, stale):
    the findings the baseline does not cover, the ones it does, and the keys it
    records for this check that the check no longer reports. A key recorded N
    times covers the first N findings that carry it; the N+1st is new.
    """
    accepted = load(path, check)
    new, held = [], []
    seen = collections.Counter()
    for finding in findings:
        key = key_for(check, finding, lines, token_of)
        seen[key] += 1
        (held if seen[key] <= accepted[key] else new).append(finding)
    stale = sorted((accepted - seen).elements()) if report_stale else []
    return new, held, stale


def report(path, check, held, stale):
    """Print the baseline's own verdict: what it held, and what it no longer covers."""
    if held:
        print(f'{check}: {len(held)} known finding(s) held by {path}')
    if stale:
        print(f'{check}: {len(stale)} baseline entry(ies) in {path} no longer reported — '
              f'the finding is fixed, so drop the line (`make lint-baseline`):')
        for key, count in sorted(collections.Counter(stale).items()):
            print(f'  {key}' + (f'  (x{count})' if count > 1 else ''))


def report_write(path, check, recorded, added, dropped):
    """
    Print what a regeneration recorded, naming every key it added and dropped.

    The count alone hides the case the file exists to catch: a finding introduced
    at an address the baseline already lists reads as inherited debt unless the
    key is named. A regeneration that adds keys is a regeneration to reject.
    """
    print(f'{check}: recorded {recorded} finding(s) in {path}')
    if added:
        print(f'{check}: {len(added)} key(s) NOT in the previous baseline — a key this '
              f'file gains is debt taken on, not debt inherited:')
        for key in added:
            print(f'  + {key}')
    if dropped:
        print(f'{check}: {len(dropped)} key(s) dropped, now clean:')
        for key in dropped:
            print(f'  - {key}')
