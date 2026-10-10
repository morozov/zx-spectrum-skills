#!/usr/bin/env python3
"""
Fail a staged diff that deletes more than a few entries nobody scoped.

A sweep that applies one test to many entries deletes the ones the test fits
and, with them, ones it was never asked about. The review record is where the
scope is stated: its `scope` list names each entry the reviewer checked the
deletion of. Above the threshold, every removed item must be named there.

Kinds:

  DELETION_SCOPE  the staged diff removes more than 3 items and no review
                  record for that exact diff names each of them in `scope`.

A removed item is:

- a `[Term:…]` section header in a `.ref`, named by its term ID;
- an `@ $X label=L` line in a `.ctl`, named by L, when no added line gives $X a
  label again;
- an entry directive in a `.ctl`, named by its address, when no added line
  opens an entry at that address again.

A rename or a retitle therefore deletes nothing. A scope string names an item
when it holds one of the item's names as a whole token: the term ID, the label,
or the address with its `$`.

The record is `build/review/<diffhash>.json` at the repo root, where the hash
is the one `review_record.py hash --cached` prints for the staged diff.

Usage: validate_deletion_scope.py [-C DIR] [--threshold 3]
Exit 0 when the deletions are in scope, 1 otherwise.
"""

import argparse
import json
import os
import re
import sys

import review_record

CHECK = 'deletion-scope'
KIND = 'DELETION_SCOPE'

FILE_RE = re.compile(r'^diff --git a/(.*?) b/')
TERM_RE = re.compile(r'^\[Term:([^:\]]+)')
LABEL_RE = re.compile(r'^@ +(\$?[0-9A-Fa-f]+) +label=(\S+)')
ENTRY_RE = re.compile(r'^([bcgistuw]) +(\$?[0-9A-Fa-f]+)(?: +(\S.*))?$')


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def removed_items(diff):
    """
    Return [(file, description, names)] for each item the diff removes.

    `names` are the tokens a scope entry may use to name the item.
    """
    removed = {'term': {}, 'label': {}, 'entry': {}}
    added = {'term': set(), 'label': set(), 'entry': set()}
    path, in_hunk = None, False
    for raw in diff.splitlines():
        header = FILE_RE.match(raw)
        if header:
            path, in_hunk = header.group(1), False
            continue
        if raw.startswith('@@'):
            in_hunk = True
            continue
        if not in_hunk or not raw or raw[0] not in '+-':
            continue
        sign, line = raw[0], raw[1:]
        term = TERM_RE.match(line) if path and path.endswith('.ref') else None
        if term:
            key = (path, term.group(1))
            if sign == '-':
                removed['term'][key] = (path, line.strip(), [term.group(1)])
            else:
                added['term'].add(key)
            continue
        if not path or not path.endswith('.ctl'):
            continue
        label = LABEL_RE.match(line)
        if label:
            address = parse_address(label.group(1))
            key = (path, address)
            if sign == '-':
                removed['label'][key] = (path, line.strip(),
                                         [label.group(2), f'${address:04X}'])
            else:
                added['label'].add(key)
            continue
        entry = ENTRY_RE.match(line.rstrip())
        if entry:
            address = parse_address(entry.group(2))
            key = (path, address)
            if sign == '-':
                removed['entry'][key] = (path, line.strip(), [f'${address:04X}'])
            else:
                added['entry'].add(key)
    items = []
    for kind in ('term', 'label', 'entry'):
        for key, item in removed[kind].items():
            if key not in added[kind]:
                items.append(item)
    return items


def names_item(scope, names):
    """Whether any scope string holds one of an item's names as a whole token."""
    for entry in scope:
        for name in names:
            if re.search(r'(?<![\w$])' + re.escape(name) + r'(?!\w)', str(entry), re.I):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('-C', dest='directory', default='.', help='run in this repository')
    parser.add_argument('--threshold', type=int, default=3,
                        help='the most removed items that need no scope (default 3)')
    args = parser.parse_args()

    os.chdir(args.directory)
    diff = review_record.staged_diff().decode('utf-8', errors='replace')
    items = removed_items(diff)
    if len(items) <= args.threshold:
        print(f'{CHECK}: the staged diff removes {len(items)} item(s), at or under '
              f'the threshold of {args.threshold}')
        return 0

    digest = review_record.diff_hash(cached=True)
    path = review_record.record_dir() / f'{digest}.json'
    scope = []
    if path.exists():
        record = review_record.load(path)
        scope = record.get('scope') or []
        if not isinstance(scope, list):
            scope = [scope]
    unnamed = [item for item in items if not names_item(scope, item[2])]
    if not unnamed:
        print(f'{CHECK}: the staged diff removes {len(items)} item(s), and the review '
              f'record names each in its scope')
        return 0

    where = (f'the review record build/review/{digest}.json does not name'
             if path.exists() else
             f'no review record build/review/{digest}.json exists to name')
    print(f'Found {len(unnamed)} removed item(s) out of scope: the staged diff removes '
          f'{len(items)}, over the threshold of {args.threshold}, and {where} these:')
    print()
    for file, line, _ in unnamed:
        print(f'  {file}: {KIND} – {line}')
    print()
    print('  List each deletion in the review record\'s scope, or restore the ones '
          'nobody asked to delete.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
