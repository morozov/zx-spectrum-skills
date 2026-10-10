#!/usr/bin/env python3
"""
Hold the rulebook and the checks to each other.

`references/rules.md` states every rule as a table row:

    | ID | Rule | Enforcer | Question |

The Enforcer cell is a comma-separated list. Each item is one of:

- an upper-case check kind, such as `DATA_ECHO`, reported by a linter;
- a `lint-…` make target of the mechanical gate;
- `review-record`, the review record the Challenger writes;
- `review`, the Challenger.

A parenthesis in the cell is commentary and names no enforcer.

Kinds:

  NO_ENFORCER       a rule whose Enforcer cell names nothing.
  UNKNOWN_KIND      an enforcer naming a check kind that no script under
                    `scripts/` defines as a string literal.
  UNKNOWN_TARGET    an enforcer naming a `lint-…` target the gate's makefile
                    does not define.
  UNKNOWN_ENFORCER  an enforcer item of no recognized form.
  UNRULED_KIND      a gating kind in `lint_comments.py` that no rule names, so
                    a finding of that kind cites no rule a reader can look up.

Usage: validate_rules.py [--rules rules.md] [--scripts DIR] [--mk FILE]
Exit 0 when the rulebook and the checks agree, 1 otherwise.
"""

import argparse
import ast
import os
import re
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ID_RE = re.compile(r'^[A-Z]+-\d+$')
KIND_RE = re.compile(r'^[A-Z][A-Z0-9_]+$')
TARGET_RE = re.compile(r'^lint-[a-z0-9-]+$')
REVIEWS = ('review-record', 'review')
PAREN_RE = re.compile(r'\([^()]*\)')
MK_TARGET_RE = re.compile(r'^([A-Za-z0-9_.%-]+(?:[ \t]+[A-Za-z0-9_.%-]+)*)[ \t]*:(?!=)')


def parse_rules(path):
    """Return [(line_number, cells)] for every rule row of every rule table.

    A rule table is one whose header names ID, Rule and Enforcer. `cells` maps
    each lowercased header to its cell.
    """
    rows = []
    header = None
    with open(path, encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            text = line.strip()
            if not text.startswith('|'):
                header = None
                continue
            cells = [c.strip() for c in text.strip('|').split('|')]
            if header is None:
                header = [c.lower() for c in cells]
                continue
            if all(set(c) <= set('-: ') for c in cells):
                continue
            if not {'id', 'rule', 'enforcer'} <= set(header):
                continue
            row = dict(zip(header, cells))
            if ID_RE.match(row.get('id', '')):
                rows.append((number, row))
    return rows


def enforcers(cell):
    """Return the enforcer items of a cell, parentheses and backticks dropped."""
    previous = None
    while previous != cell:
        previous, cell = cell, PAREN_RE.sub('', cell)
    items = []
    for item in re.split(r'[,;]', cell):
        item = item.strip().strip('`').strip()
        if item and item not in ('—', '-'):
            items.append(item)
    return items


def defined_kinds(scripts):
    """Return every upper-case identifier a script under `scripts` holds as a string.

    A kind is reported as a string literal, so a literal is what defining one
    means. Docstrings hold prose and never match the identifier shape whole.
    """
    kinds = set()
    for name in sorted(os.listdir(scripts)):
        if not name.endswith('.py'):
            continue
        with open(os.path.join(scripts, name), encoding='utf-8') as handle:
            try:
                tree = ast.parse(handle.read(), name)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and KIND_RE.match(node.value):
                kinds.add(node.value)
    return kinds


def gating_kinds(path):
    """Return the names in `GATING_KINDS` of a lint_comments.py, read without running it."""
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as handle:
        tree = ast.parse(handle.read(), path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'GATING_KINDS' for t in node.targets):
            return {n.value for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return set()


def make_targets(path):
    """Return the target names a makefile defines."""
    targets = set()
    if not path or not os.path.exists(path):
        return targets
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            match = MK_TARGET_RE.match(line)
            if match:
                targets.update(match.group(1).split())
    return targets


def check(rows, kinds, gating, targets):
    """Return (line_number, kind, message) findings."""
    findings = []
    named = set()
    for number, row in rows:
        rule = row['id']
        items = enforcers(row.get('enforcer', ''))
        if not items:
            findings.append((number, 'NO_ENFORCER', f'{rule} names no enforcer'))
        for item in items:
            if item in REVIEWS:
                continue
            if KIND_RE.match(item):
                named.add(item)
                if item not in kinds:
                    findings.append((number, 'UNKNOWN_KIND',
                                     f'{rule} names the check kind {item}, which no '
                                     f'script defines'))
            elif TARGET_RE.match(item):
                if item not in targets:
                    findings.append((number, 'UNKNOWN_TARGET',
                                     f'{rule} names the target {item}, which the '
                                     f'gate does not define'))
            else:
                findings.append((number, 'UNKNOWN_ENFORCER',
                                 f'{rule} names the enforcer "{item}", which is no check '
                                 f'kind, no lint- target and no review'))
    for kind in sorted(gating - named):
        findings.append((0, 'UNRULED_KIND',
                         f'the gating kind {kind} in lint_comments.py is named by no rule'))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('--rules', default=os.path.join(SKILL, 'references', 'rules.md'),
                        help='the rulebook (default: references/rules.md)')
    parser.add_argument('--scripts', default=os.path.join(SKILL, 'scripts'),
                        help='the directory of scripts that define check kinds')
    parser.add_argument('--mk', default=os.path.join(SKILL, 'tools', 'disassembly.mk'),
                        help="the gate's makefile, for lint- targets")
    args = parser.parse_args()

    if not os.path.exists(args.rules):
        print(f'Error: no rulebook at {args.rules}')
        return 1

    rows = parse_rules(args.rules)
    if not rows:
        print(f'Error: {os.path.basename(args.rules)} holds no | ID | Rule | Enforcer | table')
        return 1

    findings = check(rows, defined_kinds(args.scripts),
                     gating_kinds(os.path.join(args.scripts, 'lint_comments.py')),
                     make_targets(args.mk))
    name = os.path.basename(args.rules)
    if findings:
        print(f'Found {len(findings)} rulebook problem(s) in {name}:')
        print()
        for number, kind, message in findings:
            where = f'{name}:{number}' if number else name
            print(f'  {where}: {kind} – {message}')
        print()
        return 1
    print(f'rules: {len(rows)} rule(s) in {name}, every enforcer defined, every gating '
          f'kind ruled')
    return 0


if __name__ == '__main__':
    sys.exit(main())
