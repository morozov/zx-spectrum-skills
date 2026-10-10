#!/usr/bin/env python3
"""
Hold every rename in a `.ctl` diff to a registry row that lands with it.

A rename retires a word. The registry in `glossary.ref` (a `Write | Not` table,
read by `validate_glossary_terms.py`) is what holds every remaining mention of
the retired word to the new one, so the row goes in with the rename and the
terms check then fails until the sweep is complete.

Kinds:

  RENAME_UNREGISTERED  a label replaced by another at the same address, or an
                       entry title reworded at the same address, that drops a
                       word no registry Not cell lists.

The comparison reads the `.ctl` at a base revision (`HEAD` by default) against
the working file. Labels split into words on `_` and `-`; titles split on
everything but letters and digits, and skip the words of grammar. A plural and
its singular are one word.

A rename is a swap: one or two words dropped while at least one is added. A
name that only loses words renamed nothing, and one that drops three or more is
a rewrite, which a registry row per word would not describe. Three more drops
ask for no row:

- a word made only of digits, which is a position;
- a declared label-family prefix (`--agents`), which is a family move;
- any word of a name replaced by a generated `unused_` label or the title
  "Unused bytes", which reclassifies the bytes and renames no term.

Usage: validate_renames.py CTL [--registry glossary.ref] [--base REF] [--agents AGENTS.md]
Exit 0 when every dropped word is registered, 1 otherwise.
"""

import argparse
import os
import re
import subprocess
import sys

import validate_glossary_terms
import validate_label_family

CHECK = 'renames'

LABEL_RE = re.compile(r'^@ +(\$?[0-9A-Fa-f]+) +label=(\S+)')
ENTRY_RE = re.compile(r'^([bcgistuw]) +(\$?[0-9A-Fa-f]+)(?: +(\S.*))?$')
LABEL_SPLIT_RE = re.compile(r'[_-]+')
TITLE_SPLIT_RE = re.compile(r"[^a-z0-9]+")
MACRO_RE = re.compile(r'#[A-Za-z]+[^\s]*')

# Words of grammar, which a reworded title gains and loses without renaming
# anything.
STOPWORDS = frozenset('''
    a an the of in on to and or for with by at from its it is as into per
    one two three four five six seven eight nine ten
'''.split())


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def names(lines):
    """Return ({address: (label, line)}, {address: (title, line)}, {address: type})."""
    labels, titles, types = {}, {}, {}
    for number, line in enumerate(lines, 1):
        match = LABEL_RE.match(line)
        if match:
            labels[parse_address(match.group(1))] = (match.group(2), number)
            continue
        entry = ENTRY_RE.match(line.rstrip())
        if entry:
            titles[parse_address(entry.group(2))] = ((entry.group(3) or '').strip(), number)
            types[parse_address(entry.group(2))] = entry.group(1)
    return labels, titles, types


# The names that reclassify bytes as unused, which rename no term.
UNUSED_LABEL_RE = re.compile(r'^unused_')
UNUSED_TITLE_RE = re.compile(r'(?i)^unused bytes?\.?$')

# The most words a swap drops; more is a rewrite.
SWAP_LIMIT = 2


def singular(word):
    """Fold a regular plural onto its singular, so `sprites` keeps `sprite`."""
    if len(word) > 3 and word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word


def label_words(label):
    return [singular(w) for w in LABEL_SPLIT_RE.split(label.lower()) if w]


def title_words(title):
    return [singular(w) for w in TITLE_SPLIT_RE.split(MACRO_RE.sub(' ', title).lower())
            if w and w not in STOPWORDS]


def registered_words(registry):
    """Return every word of every form the registry's Not cells list."""
    pairs, _ = validate_glossary_terms.registry(registry)
    words = set()
    for form, _ in pairs:
        words.update(singular(w) for w in TITLE_SPLIT_RE.split(form.lower()) if w)
    return words


def dropped(old, new, exempt):
    """Return the words of `old` absent from `new`, in order, minus the exempt ones."""
    kept = set(new)
    out = []
    for word in old:
        if word in kept or word in out or word.isdigit() or word in exempt:
            continue
        out.append(word)
    return out


def swapped(old_words, new_words, exempt):
    """Return the words a swap drops, or [] when the change is no swap."""
    lost = dropped(old_words, new_words, exempt)
    gained = dropped(new_words, old_words, exempt)
    if not gained or len(lost) > SWAP_LIMIT:
        return []
    return lost


def check(before, after, registered, exempt):
    """Return (line_number, kind, message) findings for one .ctl's two versions."""
    findings = []
    old_labels, old_titles, old_types = names(before)
    new_labels, new_titles, new_types = names(after)

    # Labels are unique, so a label standing at a second address is evidence
    # that it moved there. A move renames nothing: splitting a block moves its
    # label, and its title with it, to the new start.
    old_at = {v[0]: a for a, v in old_labels.items()}
    new_at = {v[0]: a for a, v in new_labels.items()}

    def label_moved(address, old, new):
        if new_at.get(old, address) != address:
            return True                      # the old name now stands elsewhere
        came_from = old_at.get(new, address)
        new_entry = address in new_types and address not in old_types
        return came_from != address and new_entry   # moved in to start a new entry

    def title_moved(address, old):
        label = old_labels.get(address, (None,))[0]
        there = new_at.get(label)
        return there is not None and there != address and \
            new_titles.get(there, (None,))[0] == old

    for address in sorted(set(old_labels) & set(new_labels)):
        old, new = old_labels[address][0], new_labels[address][0]
        if old == new or UNUSED_LABEL_RE.match(new):
            continue
        if label_moved(address, old, new):
            continue
        for word in swapped(label_words(old), label_words(new), exempt):
            if word not in registered:
                findings.append((new_labels[address][1], 'RENAME_UNREGISTERED',
                                 f"label at ${address:04X}: {old} → {new} drops '{word}', "
                                 f"which no Not cell of the registry lists. Add the row "
                                 f"with the rename, so the terms check holds every "
                                 f"remaining mention"))

    for address in sorted(set(old_titles) & set(new_titles)):
        old, new = old_titles[address][0], new_titles[address][0]
        if old == new or UNUSED_TITLE_RE.match(new):
            continue
        if title_moved(address, old):
            continue
        for word in swapped(title_words(old), title_words(new), exempt):
            if word not in registered:
                findings.append((new_titles[address][1], 'RENAME_UNREGISTERED',
                                 f"title at ${address:04X}: \"{old}\" → \"{new}\" drops "
                                 f"'{word}', which no Not cell of the registry lists. "
                                 f"Add the row with the rename, so the terms check holds "
                                 f"every remaining mention"))
    return findings


def base_lines(path, base):
    """Return the .ctl's lines at `base`, or None when git has no such file there."""
    directory = os.path.dirname(os.path.abspath(path))
    try:
        top = subprocess.run(['git', '-C', directory, 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    relative = os.path.relpath(os.path.realpath(path), os.path.realpath(top))
    run = subprocess.run(['git', '-C', top, 'show', f'{base}:{relative}'],
                         capture_output=True, text=True)
    if run.returncode != 0:
        return None
    return run.stdout.splitlines()


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('ctl', help='the .ctl file to compare against its base')
    parser.add_argument('--registry', help='the .ref page holding the Write/Not table '
                                           '(default: glossary.ref beside the .ctl)')
    parser.add_argument('--base', default='HEAD', help='the revision to compare against')
    parser.add_argument('--agents', help="the project's AGENTS.md, whose label-families "
                                         "prefixes a family move may drop")
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as handle:
            after = handle.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    before = base_lines(args.ctl, args.base)
    if before is None:
        print(f'{CHECK}: {os.path.basename(args.ctl)} has no version at {args.base}, '
              f'so nothing was renamed')
        return 0

    registry = args.registry or os.path.join(
        os.path.dirname(os.path.abspath(args.ctl)), 'glossary.ref')
    families = validate_label_family.read_families(args.agents) or []
    exempt = {prefix.strip('_-') for prefix, _, _ in families}

    findings = check(before, after, registered_words(registry), exempt)
    if findings:
        print(f'Found {len(findings)} rename(s) with no registry row, against {args.base}:')
        print()
        for line_number, kind, message in findings:
            print(f'  Line {line_number}: {kind} – {message}')
        print()
        return 1
    print(f'{CHECK}: every word a rename dropped since {args.base} has its registry row')
    return 0


if __name__ == '__main__':
    sys.exit(main())
