#!/usr/bin/env python3
"""
List the entries a diff touches, marking the ones it deletes.

A bulk edit's scope is a list of entries. This prints that list for the diff as
it stands, so the scope an author states can be compared with the scope the
diff carries, and a deletion nobody named shows up by name.

An entry is:

- in a `.ctl`, a block: an entry directive and every directive whose address
  falls inside it, the `@` lines at its own address included;
- in a `.ref`, a section: a `[Name]` header and the lines under it, which covers
  `[Term:…]` and `[Page:…]`.

Any other changed file is listed whole.

Each line reads `<file>: <entry>  [<status>]`, the status one of added,
modified or deleted.

Usage: diff_entries.py [--cached] [--base REF] [-C DIR] [PATH …]
The comparison is the working tree against HEAD, or the index against HEAD with
`--cached`. Exit 0.
"""

import argparse
import bisect
import re
import subprocess
import sys

ENTRY_RE = re.compile(r'^([bcgistuw]) +(\$?[0-9A-Fa-f]+)(?: +(\S.*))?$')
ADDRESSED_RE = re.compile(r'^(?:[@A-Za-z] +|  )(\$?[0-9A-Fa-f]+)\b')
SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*$')


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def git(directory, *args):
    run = subprocess.run(['git', '-C', directory] + list(args),
                         capture_output=True, encoding='utf-8', errors='replace')
    if run.returncode != 0:
        raise SystemExit(f'diff_entries: git {" ".join(args)} failed: {run.stderr.strip()}')
    return run.stdout


def ctl_entries(text):
    """Return {key: (name, body)} for the blocks of a .ctl."""
    lines = text.splitlines()
    starts = []
    for line in lines:
        match = ENTRY_RE.match(line.rstrip())
        if match:
            starts.append((parse_address(match.group(2)), match.group(1),
                           (match.group(3) or '').strip()))
    starts.sort()
    entries = {}
    names = {}
    for address, kind, title in starts:
        key = f'${address:04X}'
        names[key] = f'{kind} ${address:04X} {title}'.rstrip()
        entries[key] = []

    addresses = [start for start, _, _ in starts]

    def owner(address):
        at = bisect.bisect_right(addresses, address)
        return f'${addresses[at - 1]:04X}' if at else None

    current = None
    for line in lines:
        match = ADDRESSED_RE.match(line)
        if match:
            current = owner(parse_address(match.group(1))) or '(before the first entry)'
        key = current or '(before the first entry)'
        entries.setdefault(key, []).append(line)
        names.setdefault(key, key)
    return {key: (names[key], '\n'.join(body)) for key, body in entries.items()}


def ref_entries(text):
    """Return {key: (name, body)} for the sections of a .ref page."""
    entries = {}
    key = '(before the first section)'
    for line in text.splitlines():
        match = SECTION_RE.match(line)
        if match:
            key = f'[{match.group(1)}]'
        entries.setdefault(key, (key, []))[1].append(line)
    # A section's trailing blank lines separate it from the next one and change
    # when a section below it is removed, which edits nothing in it.
    return {k: (name, '\n'.join(body).rstrip()) for k, (name, body) in entries.items()}


def show(directory, revision, path):
    """Return a file's text at a revision (`:` for the index), or '' if absent."""
    spec = f':{path}' if revision == ':' else f'{revision}:{path}'
    run = subprocess.run(['git', '-C', directory, 'show', spec],
                         capture_output=True, encoding='utf-8', errors='replace')
    return run.stdout if run.returncode == 0 else ''


def read_work(directory, path):
    try:
        with open(f'{directory}/{path}', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except FileNotFoundError:
        return ''


def touched(old, new):
    """Return [(name, status)] for the entries that differ between two parses."""
    out = []
    for key in list(old) + [k for k in new if k not in old]:
        if key not in new:
            out.append((old[key][0], 'deleted'))
        elif key not in old:
            out.append((new[key][0], 'added'))
        elif old[key][1] != new[key][1]:
            out.append((new[key][0], 'modified'))
    return out


def entries_for(directory, base, cached, paths=()):
    """Return [(path, name, status)] for every entry the diff touches."""
    top = git(directory, 'rev-parse', '--show-toplevel').strip()
    args = ['diff', '--name-status', '--no-renames']
    if cached:
        args.append('--cached')
    args += [base, '--'] + list(paths)
    rows = []
    for line in git(directory, *args).splitlines():
        status, _, path = line.partition('\t')
        old = show(top, base, path)
        new = show(top, ':', path) if cached else read_work(top, path)
        if path.endswith('.ctl'):
            parse = ctl_entries
        elif path.endswith('.ref'):
            parse = ref_entries
        else:
            word = {'A': 'added', 'D': 'deleted'}.get(status[:1], 'modified')
            rows.append((path, '(whole file)', word))
            continue
        for name, word in touched(parse(old), parse(new)):
            rows.append((path, name, word))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('paths', nargs='*', help='limit the diff to these paths')
    parser.add_argument('--cached', action='store_true',
                        help='compare the index, rather than the working tree, with the base')
    parser.add_argument('--base', default='HEAD', help='the revision to compare against')
    parser.add_argument('-C', dest='directory', default='.', help='run in this repository')
    args = parser.parse_args()

    rows = entries_for(args.directory, args.base, args.cached, args.paths)
    for path, name, status in rows:
        print(f'{path}: {name}  [{status}]')
    deleted = sum(1 for _, _, status in rows if status == 'deleted')
    print(f'diff_entries: {len(rows)} entry(ies) touched, {deleted} deleted')
    return 0


if __name__ == '__main__':
    sys.exit(main())
