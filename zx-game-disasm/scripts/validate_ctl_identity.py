#!/usr/bin/env python3
"""
Validate that every published block in a SkoolKit .ctl says what it is.

A reader meets a disassembly one page at a time. A block that names itself only
by its address - a page headed "Data at 5B08", a row of `DEFB` under no words at
all - is a block nobody can identify, and it passes every other check in the
build: it round-trips, it tiles, it can be fully labeled, and `coverage` counts
it documented.

Three kinds, all of them a directive that carries no words:

  UNTITLED        a block directive with no title, following a data entry. Two
                  causes need opposite fixes here - one field split out of the
                  record above (drop the block directive) or a structure that was
                  never titled (write the title) - and which one applies is a
                  judgment about whether these bytes are fields of that record.
                  The message states both fixes and names the record, because the
                  wrong one buries a structure inside an unrelated entry.
  UNTITLED_ENTRY  a block directive with no title following code, or opening the
                  file. There is no record to fold into, so the fold is not
                  available and the only fix is the title.
  UNDESCRIBED     a sub-directive that carries no description anywhere and no
                  label on its address, so nothing in the listing says what those
                  bytes are and nothing outside it can refer to them.

An `i` (ignore) block is exempt from the title rule: it publishes no page, it
marks where the disassembly stops.

## Why UNTITLED does not classify itself

Both causes occur, and no property of the directives tells them apart. A
structure that needs a title can sit contiguously after the entry above it,
carry several labeled fields, and hold from one to three sub-directives - and
so can a field that needs folding. The deciding question is semantic: do these
bytes belong to the record above? A checker that guessed would tell an author to
fold a direction-code array into an attribute ramp. So the message asks the
question and names the record it is about, rather than prescribing a fix it
cannot know.

## What discharges UNDESCRIBED

A sub-directive is identified when either holds:

- it carries a description - trailing text on the directive, or a line comment
  at an address inside its span;
- its address carries an `@ label=`. The label names those exact bytes, renders
  on that row of the listing, and makes the span reachable by name from anywhere
  in the disassembly.
- it is a `W` whose every word, read from the built `.skool` (`--skool`), points
  at an address the .ctl labels. The listing renders that label as the operand,
  so a comment repeating it would echo the operand.

The entry's own title, `D` or `N` does **not** discharge it, however completely
the schema is stated there. That exemption is the one this check exists to
refuse: take `S $C004,2` and `S $C007,1` as anonymous fill inside an object
record whose `N` says, in as many words, "+4/+5 are the X/Y direction signs" and
"+7 is the pass counter". The schema is on the entry, the bytes are still
anonymous, and neither is reachable by absolute address. A rule that accepts
"it is obvious from the record above" accepts exactly that.

Usage: validate_ctl_identity.py CTL [--baseline FILE] [--write-baseline]
Exit 0 when clean, 1 when any block cannot identify itself.
"""

import argparse
import re
import sys

import ctl_baseline

CHECK = 'identity'

# An `i` block publishes no page - it marks where the disassembly stops - so it
# is the one block type with nothing to title.
TITLED_BLOCK_TYPES = 'bcgstuw'

# A field can only be folded back into a record, never into a routine, so the fold
# is on offer only where the entry above is data.
DATA_BLOCK_TYPES = 'bgstuw'

# The page heading an untitled entry publishes, from SkoolKit's default `[Titles]`
# templates (`Asm-<type>` in `skoolkit/defaults.py`). Quoting the entry's own
# heading is what makes the finding checkable against the built site.
DEFAULT_HEADINGS = {
    'b': 'Data at',
    'c': 'Routine at',
    'g': 'Game status buffer entry at',
    's': 'Unused RAM at',
    't': 'Text at',
    'u': 'Unused RAM at',
    'w': 'Data at',
}

ADDR = r'(\$?[0-9A-Fa-f]+)'
ENTRY = re.compile(r'^([bcgistuw]) +%s(?: +(\S.*))?$' % ADDR)
SUB = re.compile(r'^([BCSTWM]) +%s((?:,[^\s]+)*)(?: +(\S.*))?$' % ADDR)
LABEL = re.compile(r'^@ +%s +label=' % ADDR)
DEFW_ROW = re.compile(r'^[ *]?\$([0-9A-Fa-f]{4}) DEFW ([^;]+?)\s*(?:;|$)')
WORD_OPERAND = re.compile(r'^\$[0-9A-Fa-f]{4}$')
COMMENT = re.compile(r'^  %s(?:,[^\s]+)* +(\S.*)$' % ADDR)


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def span_length(args):
    """Byte length a sub-directive covers: the first operand, or 1 when unstated."""
    parts = [p for p in args.split(',') if p]
    if not parts:
        return 1
    try:
        return int(parts[0])
    except ValueError:
        return 1


def parse_ctl(lines):
    """
    Return (entries, labeled) for a .ctl.

    Each entry carries its line number, type, address, title, the entry that
    precedes it, and its sub-directives; each sub-directive carries its line
    number, type, address, length, and whether any description reaches it.

    labeled is every address an `@ label=` names.
    """
    labeled = set()
    for line in lines:
        match = LABEL.match(line)
        if match:
            labeled.add(parse_address(match.group(1)))

    heads = [(i, m) for i, line in enumerate(lines)
             for m in [ENTRY.match(line.rstrip())] if m]

    entries = []
    for k, (i, m) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        subs = []
        for j in range(i + 1, end):
            sub = SUB.match(lines[j].rstrip())
            if not sub:
                continue
            subs.append({
                'line_number': j + 1,
                'type': sub.group(1),
                'address': parse_address(sub.group(2)),
                'length': span_length(sub.group(3)),
                'described': bool(sub.group(4)),
            })
        for j in range(i + 1, end):
            comment = COMMENT.match(lines[j].rstrip())
            if not comment:
                continue
            address = parse_address(comment.group(1))
            for sub in subs:
                if sub['address'] <= address < sub['address'] + sub['length']:
                    sub['described'] = True
        entries.append({
            'line_number': i + 1,
            'type': m.group(1),
            'address': parse_address(m.group(2)),
            'title': (m.group(3) or '').strip(),
            'previous': entries[-1] if entries else None,
            'subs': subs,
        })
    return entries, labeled


def check_title(entry):
    """Report an entry with no title, and offer only the fixes that are available."""
    if entry['title'] or entry['type'] not in TITLED_BLOCK_TYPES:
        return []
    heading = DEFAULT_HEADINGS[entry['type']]
    page = (f"`{entry['type']} ${entry['address']:04X}` has no title and publishes as a "
            f"page headed \"{heading} {entry['address']:04X}\"")
    above = entry['previous']
    if above is None or above['type'] not in DATA_BLOCK_TYPES:
        neighbor = ('it opens the file' if above is None
                     else f"the entry above it is {above['type']} ${above['address']:04X}")
        return [(entry['line_number'], 'UNTITLED_ENTRY',
                 f'{page}. There is no record to fold it into — {neighbor} — so it is an '
                 f'entry in its own right: write the title')]
    record = f"{above['type']} ${above['address']:04X} {above['title']}".rstrip()
    return [(entry['line_number'], 'UNTITLED',
             f'{page}. Either it is one field split out of the record above it '
             f'({record}), and the fix is to drop this block directive so the '
             f'sub-directive stays inside that record; or it starts a structure of its '
             f'own, and the fix is to write the title. Fold only if these bytes are '
             f'fields of that record — folding a structure buries it in an unrelated '
             f'entry')]


def word_targets(path):
    """Return {address: [target addresses]} for the DEFW rows of a built .skool."""
    targets = {}
    if not path:
        return targets
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = DEFW_ROW.match(line)
            if not m:
                continue
            ops = [op.strip() for op in m.group(2).split(',')]
            if all(WORD_OPERAND.match(op) for op in ops):
                targets[int(m.group(1), 16)] = [int(op[1:], 16) for op in ops]
    return targets


def check_descriptions(entry, labeled, targets=None):
    """Report a sub-directive that neither describes nor names its bytes."""
    violations = []
    if entry['type'] == 'u':
        # An unused entry's own description says the one thing there is to say;
        # its sub-blocks are runs of bytes nothing reads, with nothing to name.
        return violations
    for sub in entry['subs']:
        if sub['described'] or sub['address'] in labeled:
            continue
        if sub['type'] == 'W' and targets and all(
                address in targets and all(target in labeled for target in targets[address])
                for address in range(sub['address'], sub['address'] + sub['length'], 2)):
            continue
        violations.append((sub['line_number'], 'UNDESCRIBED',
                           f"{sub['type']} ${sub['address']:04X},{sub['length']} carries no "
                           f"description and no `@ ${sub['address']:04X} label=` — describe "
                           f"it on the directive, or label it; the entry's own schema does "
                           f"not name these bytes"))
    return violations


def main():
    parser = argparse.ArgumentParser(
        description='Validate that every published .ctl block identifies itself.')
    parser.add_argument('ctl', help='the .ctl file to validate')
    parser.add_argument('--skool', help='the built .skool, to see which words point at labels')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    entries, labeled = parse_ctl(lines)
    targets = word_targets(args.skool)

    findings = []
    for entry in entries:
        for line_number, kind, message in check_title(entry) + \
                check_descriptions(entry, labeled, targets):
            findings.append((line_number, kind, message, entry))
    findings.sort(key=lambda f: f[0])

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
        print(f'Found {len(new)} anonymous block(s):')
        print()
        for line_number, kind, message, entry in new:
            print(f'  Line {line_number}: {kind} — {message}')
            print(f"    in {entry['type']} ${entry['address']:04X} {entry['title']}".rstrip())
            print()
    elif not held and not stale:
        print('block identity: every entry titled, every sub-block named')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
