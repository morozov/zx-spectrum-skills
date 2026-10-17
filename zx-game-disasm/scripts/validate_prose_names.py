#!/usr/bin/env python3
"""
Validate that prose names a labeled slot by its label, not by its position.

`references/agents.md` states the rule: one canonical term per concept, anchored
to the `@label` identifiers, and never a synonym for something a label already
names. Unchecked, prose drifts into three names for two car slots - "car A",
"first/second car", "the leading car" - against labels `car_a` and `car_b`.
Every page reads fine on its own; a reader crossing pages has to work out that
all three are the same two addresses.

Most of that class is not machine-findable: no tool can know that "the leading
car" means `car_a` rather than a third car. One form of it is, and it is the
form that produces the aliases in the first place.

ALIAS - a positional word applied to a labeled slot family.

  A slot family is a set of labels that differ only in one slot token - an
  enumeration index - at the same place in the name: `car_a` and `car_b`, or
  `car_a_x_accum` and `car_b_x_accum`, give the family `car` with slots `a` and
  `b`. The family is the project saying, in code, that these addresses are
  the members of one set and that each member has a name.

  Prose that then calls a member "the first car", "the second car" or "the
  other car" has named it a second way, and by its position rather than by its
  name. Position is the worst of the available names: it is not in the listing,
  it is not searchable, and which member is "first" is a fact about the .ctl's
  ordering rather than about the game. The fix is to write the slot's own name -
  "car A" for `car_a` - or, where the prose really means an unlabeled thing,
  to give that thing a label.

  Three restrictions keep the check on that class and off ordinary English.

  Only an enumeration is a slot set. An ordinal word presupposes an order with a
  known start, and only two token sets have one: digits, and letters running
  from `a`. `car_a`/`car_b` and `spr_drone_0`..`_3` are enumerations; the
  members of `step_x`/`step_y`, `spr_arrow_l`/`_r` and `work_h`/`_x`/`_y`
  are an axis, a direction and a work register, and no member of those is
  "the first" one. Accepting any single letter would mint families on
  ordinary-English stems and flag "for the first step through 184, 113, 226" as
  an alias for `step_x`.

  Only the family's full stem counts as the noun. `first cell` is ordinary
  English about probe order; `first probe_cell` would be the finding, were the
  family `probe_cell`. Matching a stem's last word alone would flag every such
  ordinary sentence beside the real aliases, which is a check nobody would keep.

  Only a phrase that *refers* to a member is an alias. `the second car` names
  the car; `the second-car bonus` names a bonus, and `second-car` is a
  hyphenated compound modifier - the hyphen is the writer saying so. The head
  noun of that phrase is `bonus`, which is a different entity with a name of its
  own, and substituting the label yields "the car B bonus", which is not English
  and is not the fix this check asks for. A hand pass over this class rewrites
  every referring use to "car B" and leaves every attributive one standing; the
  check draws the line in the same place.

What this does not catch is a name with no positional word in it - "the leading
car". That one is settled by the author and held by the glossary, not by
arithmetic over the label set.

Usage: validate_prose_names.py CTL [PROSE ...] [--baseline FILE] [--write-baseline]
Exit 0 when clean, 1 when prose names a slot by its position.
"""

import argparse
import collections
import os
import re
import sys

import ctl_baseline

CHECK = 'prose-names'

LABEL_RE = re.compile(r'^@ +\$?[0-9A-Fa-f]+ +label=(\S+)')

# A candidate slot token: one letter, or a one/two-digit index. Whether the set
# of them is an enumeration is decided per family, by `is_enumeration`.
SLOT_RE = re.compile(r'^(?:[a-z]|\d{1,2})$')

# Letter slots enumerate from `a`, the way a list does. Anything else is a
# component name - an axis (`_x`/`_y`), a side (`_l`/`_r`), an extent (`_w`/`_h`)
# - and has no first member for a positional word to name.
LETTER_SEQUENCE = 'abcdefghijklmnopqrstuvwxyz'

# Words that name a set member by where it sits rather than by what it is.
# Deliberately short: `next`, `previous` and `last` are about time or traversal
# order - "the next frame", "the previous heading" - and are ordinary English
# even where a slot family shares the noun.
POSITIONAL = ('first', 'second', 'third', 'fourth',
              'other', 'another', 'former', 'latter')

# A stem shorter than this is not a noun a reader would meet in a sentence.
MIN_STEM = 3

# A SkoolKit macro is markup, not prose - `#FRAMES(second_car_0,12)` names a
# frame, it does not call anything "the second car". Macros carry no spaces, so
# the whole token drops out.
MACRO_RE = re.compile(r'#[A-Za-z]+\S*')


def is_enumeration(slots):
    """
    Whether a family's slot tokens enumerate its members, rather than name them.

    Digits enumerate. Letters enumerate only when they run from `a`: a set that
    starts anywhere else - `x`/`y`, `l`/`r`, `w`/`h` - is a set of component
    names, and no member of it is "the first" one.
    """
    if all(slot.isdigit() for slot in slots):
        return True
    if all(slot.isalpha() for slot in slots):
        return sorted(slots) == list(LETTER_SEQUENCE[:len(slots)])
    return False


def slot_families(ctl_lines):
    """
    Return {stem: {slot, ...}} for every slot family the .ctl's labels declare.

    A family needs two members: one label with a slot token proves nothing, and
    `work_1` alone is a name rather than a set. Its tokens must enumerate, so
    that a positional word can be wrong about which member it names.
    """
    families = collections.defaultdict(set)
    for line in ctl_lines:
        match = LABEL_RE.match(line)
        if not match:
            continue
        words = match.group(1).lower().split('_')
        for i in range(1, len(words)):
            if SLOT_RE.match(words[i]):
                families['_'.join(words[:i])].add(words[i])
    return {stem: slots for stem, slots in families.items()
            if len(slots) >= 2 and len(stem) >= MIN_STEM and is_enumeration(slots)}


def alias_pattern(families):
    """Return the regex matching `<positional> <family stem>`, or None if no family."""
    if not families:
        return None
    stems = '|'.join(re.escape(s).replace('_', '[ _-]') for s in sorted(families))
    return re.compile(r'\b(%s)([ -])(%s)s?\b' % ('|'.join(POSITIONAL), stems), re.I)


def is_attributive(match, text):
    """
    Whether a matched phrase modifies the noun after it rather than naming a slot.

    English hyphenates a compound modifier and only a compound modifier, so
    `second-car spawn` is the writer stating that `spawn` is the head noun and
    the phrase is about an event. `the second car`, unhyphenated, refers to the
    car itself, and that is the alias.
    """
    return match.group(2) == '-' and re.match(r'\s+[A-Za-z]', text[match.end():]) is not None


def stem_of(phrase, families):
    """Return the family stem a matched phrase names."""
    tail = re.split(r'[ -]', phrase.lower(), maxsplit=1)[1].rstrip('s')
    normalized = re.sub(r'[ -]', '_', tail)
    return normalized if normalized in families else tail


def scan(path, pattern, families):
    """Report every positional naming of a slot family in one prose file."""
    findings = []
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            lines = f.read().splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, 1):
        if line.startswith('@ '):
            continue                      # an ASM directive, not prose
        prose = MACRO_RE.sub(' ', line)
        for match in pattern.finditer(prose):
            if is_attributive(match, prose):
                continue
            phrase = match.group(0)
            stem = stem_of(phrase, families)
            slots = ', '.join(f'`{stem}_{s}`' for s in sorted(families.get(stem, ())))
            findings.append((
                number, 'ALIAS',
                f'"{phrase}" names a member of the `{stem}` slot family by its position. '
                f'Its members carry names — {slots} — so write the name a reader can find '
                f'in the listing, or label the thing this really means',
                path, phrase))
    return findings


def token(finding):
    """
    The baseline's third field: `<file>:<phrase>`, lowercased and hyphen-joined.

    The file has to be in the key. Without it, an accepted phrase in a `.ref`
    catalog and the same phrase newly written into the .ctl are one key with one
    count, so fixing the catalog pays for the new one and the gate stays green -
    on the exact defect this check exists for. They are also different fixes in
    different files, which is what a key is supposed to distinguish.
    """
    return f'{os.path.basename(finding[3])}:{re.sub(r"[ _-]+", "-", finding[4].lower())}'


def main():
    parser = argparse.ArgumentParser(
        description='Validate that prose names a labeled slot by its label.')
    parser.add_argument('ctl', help='the .ctl file, which declares the labels')
    parser.add_argument('prose', nargs='*',
                        help='further reader-facing files to sweep (.ref, spec/*.md)')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as f:
            ctl_lines = f.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    families = slot_families(ctl_lines)
    pattern = alias_pattern(families)
    findings = []
    if pattern is not None:
        for path in [args.ctl] + args.prose:
            findings += scan(path, pattern, families)

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, findings, ctl_lines,
                                token_of=token))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, findings, ctl_lines,
                                              report_stale=not args.ignore_stale,
                                              token_of=token)

    if new:
        print(f'Found {len(new)} positional name(s) for a labeled slot:')
        print()
        for number, kind, message, path, _ in new:
            print(f'  {os.path.basename(path)}:{number}: {kind} — {message}')
            print()
        if held:
            print('  (The baseline counts occurrences of a phrase in a file, not their '
                  'positions, so the line shown is one occurrence of a phrase that now '
                  'appears in that file more often than the baseline accepts — not '
                  'necessarily the one just written. Every occurrence is the same finding '
                  'and takes the same fix.)')
            print()
    elif not held and not stale:
        print(f'prose names: {len(families)} slot family(ies) declared by the labels, '
              f'each named by them in prose' if families
              else 'prose names: no slot family in the labels, nothing to hold')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
