#!/usr/bin/env python3
"""
Validate that an underscore in a label means what a reader takes it to mean.

`move_player_down` tells a reader that these bytes are part of `move_player`.
That is a claim about the code, not a decoration, and it is checkable: the address
must sit inside the thing it names, and `move_player` must be the nearest named
thing it sits inside. When the claim is false the name misdirects exactly the
reader who trusted it, and no other check in the build can see it - the label
round-trips, fits the length cap, and counts as documented under `coverage`.

Containment for a routine is dominance: every path that reaches this address
passes through the one the prefix names. So the check builds each `c` entry's
control-flow graph from the generated .skool and asks the dominator tree.

Four kinds:

  UNREACHED       the stem names a label that does not dominate this address at
                  all. Control arrives without passing through it, so these bytes
                  are not inside it - the two are siblings, or the containment
                  runs the other way, and the prefix simply asserts something the
                  flow refuses.
  MISPARENTED     the stem names a label that does dominate, but a narrated
                  behavior lies between them. The prefix skips a level: it claims
                  the outer behavior while the bytes sit inside an inner one, so
                  a family that should read as one set is spread across two
                  depths.
  PRIVATE_HELPER  the stem names a label in another entry, and every reference to
                  this address comes from inside that entry. So it is not a
                  sibling a caller may pick, it is that entry's own helper wearing
                  its name - two addresses that read as alternatives, one
                  qualified and one not, where only the unqualified one is ever
                  invoked. A public sibling passes: `print_string_wide` beside
                  `print_string`, called from a dozen places, offers a choice
                  that exists.
  SUBSUMED        the label carries its own `N` narrative - it is a behavior a
                  reader looks up as a unit, not a branch position - while its
                  prefix claims it as part of another label. A behavior with its
                  own story earns a name of its own, outside the other's
                  namespace.

Two things it deliberately does not report:

- A prefix on a data label. `hit_door_addr` names the variable `hit_door` works
  on; the prefix associates, it does not claim containment, and there is no
  control flow to falsify it with. Only code is checked, on both sides.
- A sequence of branch positions. `slide_down`, `slide_down_dir`,
  `slide_down_step`, `slide_down_done` run in order, so each dominates the
  next and a naive rule would nest a straight-line sequence into
  `slide_down_dir_step_done`. They are stages of one behavior, and what makes
  something a behavior rather than a stage is that a reader looks it up: the `N`
  narrative. So only a narrated label can be the *inner* behavior a prefix skips.

## Why the graph is global and the roots are plural

An address jumped into from another entry is not dominated by anything in its own
entry, and a CFG built per entry cannot see that: the outside predecessor is
invisible, the address looks dominated by whatever local path also reaches it, and
the check hands out a restem that writes a fresh lie into the tree. So the graph
is built once across every `c` entry, and each entry's dominator tree is rooted at
its start *and* at every address something outside reaches - which leaves such an
address dominated by nothing but itself, which is the truth about it.

A `CALL` to an address inside the same entry is an edge for the same reason. A
subroutine reached only that way is inside the routine that calls it; modeling
`CALL` as fall-through alone would leave it unreachable and silently dropped.

## What it refuses to judge

An entry whose flow cannot be followed is skipped and named in the output, never
guessed at. Dominance computed around an indirect jump is not conservative, it is
wrong, and a wrong dominator tree reports confident nonsense. Two things trigger
the refusal: an explicit `JP (HL)`, and a labeled address inside the entry that
no path reaches - which is what a jump table, a `PUSH`/`RET` computed jump, or
self-modified flow looks like from here.
"""

import argparse
import collections
import re
import sys

import ctl_baseline

CHECK = 'label-namespace'

# Addresses are `$`-hex or plain decimal, in both files - `parse_address` decides.
# Every sibling .ctl linter accepts both, and a check that reads only one form
# reports a decimal project as clean rather than as unread.
ADDRESS = r'(\$?[0-9A-Fa-f]+)'

CTL_LABEL_RE = re.compile(r'^@ ' + ADDRESS + r' label=(\S+)')
CTL_ENTRY_RE = re.compile(r'^([cbgistuw]) ' + ADDRESS)
CTL_NARRATIVE_RE = re.compile(r'^N ' + ADDRESS)

# A .skool instruction line: the entry-type column (a type letter, a space, or the
# `*` of a sub-entry), the address, then the operation.
SKOOL_INSTRUCTION_RE = re.compile(r'^([cbgistuw*@ ])' + ADDRESS + r'\s+(\S.*)$')

# A jump's destination is its last operand.
TARGET_RE = re.compile(r'(?:^|[,\s(])' + ADDRESS + r'\)?\s*$')

TERMINAL = ('RET', 'RETI', 'RETN')

# Flow the check cannot follow. Matched case-insensitively: `sna2skool.py --lower`
# writes `jp (hl)`, and a check that misses it skips the entry for the wrong
# reason - or worse, does not skip it.
INDIRECT = re.compile(r'^JP\s+\((?:HL|IX|IY)\)', re.IGNORECASE)

# Data directives carry no flow, but they do carry references: a routine reached
# through a `DEFW` dispatch table has a caller this check must see, or it reads as
# somebody's private helper.
DATA_DIRECTIVE = re.compile(r'^DEF[BWMS]\b', re.IGNORECASE)


def parse_address(text):
    """Return the integer value of an address, `$`-hex or plain decimal."""
    return int(text[1:], 16) if text.startswith('$') else int(text, 10)


def instruction_body(text):
    """Return the operation with its comment removed, respecting quoted strings."""
    quoted = False
    for index, character in enumerate(text):
        if character == '"':
            quoted = not quoted
        elif character == ';' and not quoted:
            return text[:index].strip()
    return text.strip()


def parse_ctl(lines):
    """Return the .ctl's labels, entry starts, and the addresses carrying an `N`."""
    labels = {}
    entries = []
    narrated = set()
    for line_number, line in enumerate(lines, 1):
        match = CTL_LABEL_RE.match(line)
        if match:
            labels[parse_address(match.group(1))] = (match.group(2), line_number)
            continue
        match = CTL_ENTRY_RE.match(line)
        if match:
            entries.append((parse_address(match.group(2)), match.group(1)))
            continue
        match = CTL_NARRATIVE_RE.match(line)
        if match:
            narrated.add(parse_address(match.group(1)))
    entries.sort()
    return labels, entries, narrated


def parse_skool(path):
    """
    Return ({entry: {address: operation}}, {entry: type}) for every entry.

    Data entries are read too - not for their flow, which they have none of, but
    for the references their `DEFW` tables hold.
    """
    instructions = {}
    kinds = {}
    current = None
    with open(path, encoding='utf-8') as f:
        for line in f:
            match = SKOOL_INSTRUCTION_RE.match(line.rstrip('\n'))
            if not match:
                continue
            try:
                column, address = match.group(1), parse_address(match.group(2))
            except ValueError:
                continue
            if column in 'cbgistuw':
                current = address
                instructions[current] = {}
                kinds[current] = column
            if current is None:
                continue
            instructions[current][address] = instruction_body(match.group(3))
    if not instructions:
        raise ValueError(f'{path}: no instruction line parsed — the check cannot '
                         f'read this file, and reporting it clean would be a lie')
    return instructions, kinds


def successors(address, operation, ordered, index):
    """
    Return the addresses control can reach from one instruction, or None.

    None means the flow is indirect and the entry cannot be analyzed. A `CALL`
    yields its target as well as the fall-through: a subroutine reached only by a
    call from inside its own entry is inside it, and dropping that edge would
    leave it unreachable and silently unjudged.
    """
    if INDIRECT.match(operation):
        return None
    words = operation.split()
    mnemonic = words[0].upper() if words else ''
    following = ordered[index + 1] if index + 1 < len(ordered) else None
    fallthrough = [following] if following is not None else []

    if mnemonic in TERMINAL:
        # `RET cc` falls through; a bare `RET` ends the path.
        return fallthrough if len(words) > 1 else []
    if mnemonic in ('JP', 'JR', 'DJNZ', 'CALL'):
        match = TARGET_RE.search(operation)
        if not match:
            return None
        target = [parse_address(match.group(1))]
        conditional = ',' in operation or mnemonic in ('DJNZ', 'CALL')
        return target + fallthrough if conditional else target
    return fallthrough


def build_graph(code):
    """Return ({address: successors}, {address: predecessors}, unfollowable entries)."""
    graph = {}
    unfollowable = set()
    for entry, instructions in code.items():
        ordered = sorted(instructions)
        for index, address in enumerate(ordered):
            following = successors(address, instructions[address], ordered, index)
            if following is None:
                unfollowable.add(entry)
                following = []
            graph[address] = following
    predecessors = collections.defaultdict(set)
    for address, targets in graph.items():
        for target in targets:
            predecessors[target].add(address)
    return graph, predecessors, unfollowable


# The virtual root every entry's dominator tree hangs from. Its children are the
# entry's start and every address something outside the entry reaches, so an
# address entered from elsewhere is dominated by nothing but itself.
ROOT = -1


def dominators(entry, instructions, graph, predecessors):
    """Return {address: its dominators}, or None if some labeled byte is unreached."""
    inside = set(instructions)
    roots = {entry}
    for address in inside:
        if any(p not in inside for p in predecessors.get(address, ())):
            roots.add(address)

    edges = {ROOT: sorted(roots)}
    for address in inside:
        edges[address] = [t for t in graph.get(address, ()) if t in inside]

    reachable = {ROOT}
    queue = [ROOT]
    while queue:
        for target in edges[queue.pop()]:
            if target not in reachable:
                reachable.add(target)
                queue.append(target)

    if len(reachable) - 1 < len(inside):
        # Something reaches these bytes that the model cannot see - a jump table,
        # a computed jump, self-modified flow. Refuse the whole entry.
        return None

    incoming = collections.defaultdict(set)
    for address, targets in edges.items():
        for target in targets:
            incoming[target].add(address)

    dominated = {address: set(reachable) for address in reachable}
    dominated[ROOT] = {ROOT}
    changed = True
    while changed:
        changed = False
        for address in sorted(inside):
            sources = [dominated[p] for p in incoming[address] if p in reachable]
            if not sources:
                continue
            new = {address}.union(set.intersection(*sources))
            if new != dominated[address]:
                dominated[address] = new
                changed = True
    return dominated


def inbound(code):
    """Return {target address: the entries referencing it}, data tables included."""
    callers = collections.defaultdict(set)
    for entry, instructions in code.items():
        for operation in instructions.values():
            words = operation.split()
            mnemonic = words[0].upper() if words else ''
            if mnemonic not in ('CALL', 'JP', 'JR', 'DJNZ') \
                    and not DATA_DIRECTIVE.match(operation):
                continue
            for token in re.findall(ADDRESS, operation):
                try:
                    callers[parse_address(token)].add(entry)
                except ValueError:
                    continue
    return callers


def claimed_stem(label, labels_by_name):
    """Return the longest `_`-delimited prefix of `label` that is itself a label."""
    parts = label.split('_')
    for cut in range(len(parts) - 1, 0, -1):
        candidate = '_'.join(parts[:cut])
        if candidate in labels_by_name:
            return candidate
    return None


def entry_of(address, entries):
    """Return (start, type) of the entry containing `address`."""
    found = None
    for start, kind in entries:
        if start > address:
            break
        found = (start, kind)
    return found


def check(labels, entries, narrated, code):
    """Return the findings, plus the entries whose flow could not be followed."""
    labels_by_name = {name: address for address, (name, _) in labels.items()}
    code_only = {a: i for a, i in code.items() if entry_of(a, entries)
                 and entry_of(a, entries)[1] == 'c'}
    graph, predecessors, unfollowable = build_graph(code_only)
    callers = inbound(code)

    trees = {}
    for entry, instructions in code_only.items():
        tree = None if entry in unfollowable else \
            dominators(entry, instructions, graph, predecessors)
        if tree is None:
            unfollowable.add(entry)
        trees[entry] = tree

    findings = []
    for address, (label, line_number) in sorted(labels.items()):
        stem = claimed_stem(label, labels_by_name)
        if stem is None:
            continue
        parent = labels_by_name[stem]
        if parent == address:
            continue

        here = entry_of(address, entries)
        there = entry_of(parent, entries)
        # Containment is a claim about control flow, so both sides must be code.
        # A prefix shared by two data labels associates and asserts nothing.
        if here is None or there is None or here[1] != 'c' or there[1] != 'c':
            continue

        if here[0] != there[0]:
            outside = callers.get(address, set()) - {here[0]}
            if outside and outside <= {there[0]}:
                findings.append((
                    line_number, 'PRIVATE_HELPER',
                    f'{label} (${address:04X}) is reached only from ${there[0]:04X}, the '
                    f'entry that labels its prefix `{stem}` — it is that routine\'s helper '
                    f'wearing its name, not a sibling a caller may pick. Name it for what '
                    f'it does, outside {stem}\'s namespace'))
            continue

        if address in narrated:
            findings.append((
                line_number, 'SUBSUMED',
                f'{label} carries its own `N` narrative, so it is a behavior a reader '
                f'looks up, not a branch position — yet its prefix claims it as part of '
                f'{stem} (${parent:04X}). Give it a name of its own'))
            continue

        tree = trees.get(here[0])
        if tree is None or address not in tree:
            continue

        if parent not in tree[address]:
            findings.append((
                line_number, 'UNREACHED',
                f'{label} is prefixed `{stem}` (${parent:04X}), which does not contain '
                f'${address:04X} — control reaches these bytes without passing through '
                f'{stem}. The prefix claims a containment the flow refuses'))
            continue

        between = [a for a in tree[address]
                   if a not in (address, parent, ROOT) and a in narrated and a in labels
                   and parent in tree[a]]
        if between:
            inner = max(between, key=lambda a: len(tree[a]))
            findings.append((
                line_number, 'MISPARENTED',
                f'{label} is prefixed `{stem}` (${parent:04X}), but these bytes are inside '
                f'{labels[inner][0]} (${inner:04X}), which lies between them and has a '
                f'narrative of its own. The prefix skips a level — stem it on '
                f'{labels[inner][0]}'))

    findings.sort(key=lambda f: f[0])
    return findings, sorted(unfollowable)


def report_families(labels, narrated):
    """
    Print every prefix family for review, which is what a naming sweep walks.

    A family is the longest `_`-prefix two or more labels share, so `move_bat_*`
    and `move_ball_*` are two families rather than one `move`. Grouping on the
    first token instead buries the sets a reviewer has to judge inside whichever
    verb they happen to start with.

    The gate decides containment, which is a fact. What a suffix set encodes is a
    judgment no check can make: a family reads well when every member answers the
    same question - which direction, which stage, which control type - and badly
    when the suffixes turn out to be four different kinds of thing.
    """
    names = {name: address for address, (name, _) in labels.items()}
    shared = collections.Counter()
    for name in names:
        parts = name.split('_')
        for cut in range(1, len(parts)):
            shared['_'.join(parts[:cut])] += 1

    families = collections.defaultdict(list)
    for name, address in names.items():
        parts = name.split('_')
        stems = [s for s in ('_'.join(parts[:cut]) for cut in range(1, len(parts)))
                 if shared[s] > 1]
        if stems:
            families[max(stems, key=len)].append((name, address))

    ordered = sorted(families.items(), key=lambda f: (-len(f[1]), f[0]))
    print(f'{len(ordered)} prefix families, largest first. For each, ask what the '
          f'suffix encodes — and whether every member answers that.')
    print()
    for stem, members in ordered:
        anchor = ' (a label itself)' if stem in names else ''
        print(f'  {stem}{anchor} — {len(members)}')
        for name, address in sorted(members, key=lambda m: m[1]):
            print(f'    ${address:04X}{" N" if address in narrated else "  "}  {name}')
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Validate that a label prefix names something that contains it.')
    parser.add_argument('ctl', help='the .ctl file to validate')
    parser.add_argument('--skool', required=True,
                        help='the generated .skool, read for the control flow')
    parser.add_argument('--report-families', action='store_true',
                        help='print every prefix family and its members for review, '
                             'rather than gating; the worklist for a naming sweep')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    labels, entries, narrated = parse_ctl(lines)

    if args.report_families:
        report_families(labels, narrated)
        return 0

    try:
        code, _ = parse_skool(args.skool)
    except FileNotFoundError:
        print(f'Error: File not found: {args.skool}')
        return 1
    except ValueError as error:
        print(f'Error: {error}')
        return 1

    findings, skipped = check(labels, entries, narrated, code)

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
        print(f'Found {len(new)} label prefix(es) that name something else:')
        print()
        for line_number, kind, message in new:
            print(f'  Line {line_number}: {kind} — {message}')
            print()
    elif not held and not stale:
        print('label namespace: every prefix names a behavior that contains it')

    if skipped:
        print(f'{CHECK}: {len(skipped)} entry(ies) not judged — flow the check cannot '
              f'follow: ' + ', '.join(f'${a:04X}' for a in skipped))

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
