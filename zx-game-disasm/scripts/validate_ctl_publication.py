#!/usr/bin/env python3
"""
Validate the set of pages a .ctl publishes: one page per thing, and only things.

Every entry in a .ctl becomes a page on the site and a row in the memory map.
Two failures put the wrong set of pages there, and both pass the round-trip, the
tiling check and the identity check, because neither is about the bytes an entry
declares - it is about whether the entry should be an entry at all.

  OUTSIDE     an entry outside the program image. Generated render-only data -
              sprite masks a build script produced - declared at $1000 in a
              project whose image starts at $4000 makes `skool2html` emit a page
              and a memory-map row for RAM the program never occupies, at
              addresses that are ROM on real hardware. A reader has no way to
              tell those pages from the ones that document the game.
              Render-only data belongs in a `.ref` `[Graphic:]` entry or beside
              the script that generates it, not in the disassembly's address
              space. `i` blocks are exempt: they publish no page, and the
              terminator sits at the end of the image by construction.

  FRAGMENTED  one structure cut into pages. A loading screen published as one
              entry per screen address the front-end writes to is a page and a
              memory-map row per address, and no page anywhere saying "this is
              the loading screen". The signature is a run of consecutive
              entries of one structure type, each with no sub-directive of its
              own, all headed by the same thing. Nothing in such a run says more
              about its bytes than the run above it does; the structure that
              spans them is stated nowhere. The fix is one entry with one title
              and a sub-directive per part.

Consecutive entries always tile - the next entry's address is where the previous
one ends - so contiguity carries no information and is not tested. What carries
information is that the run says one thing N times. A project with a genuine row
of small distinct tables states a distinct title on each and is not reported.

## What "the same thing" means, and why it is the head of the title

A fragment of a structure is written the way a reader writes a caption: the
structure's own name, then a note about this fragment's part in it.

    b $4010 Loading-screen bitmap; start cell reused for the score readout
    b $4050 Loading-screen bitmap; start cell reused for the high-score heading
    b $40B0 Loading-screen bitmap; start cell reused for the options line

Comparing whole titles, with only an index stripped, calls those three distinct
and reports nothing. The distinguishing tail is not a second
subject: it is a note about one address inside the one subject the head names.
So the run is keyed on the head of the title, the clause before the first `:`,
`;`, `,`, `(` or dash. Three entries all headed "Loading-screen bitmap" are one
loading screen; three headed "Sprite mask table", "Sound effect table" and
"Tile attribute table" are three tables.

Only `b` and `w` are tested. A `g` entry is one game-status variable and a `t`
entry is one message, and having no sub-directive is the normal form for both,
so three consecutive `Player N score` entries are the standard idiom rather than
a structure cut up; `s` and `u` declare space, which is not a structure at all.

Usage: validate_ctl_publication.py CTL [CTL ...] --org ADDR --size N
                                   [--baseline FILE]
Exit 0 when clean, 1 when the .ctl publishes a page it should not.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'publication'

# Entry types that publish a page. `i` marks where the disassembly stops.
PUBLISHED_TYPES = 'bcgstuw'

# Types a fragmented structure is cut from. Consecutive `c` entries are separate
# routines by definition - the disassembly proves it - so code is not tested.
# `g` (one status variable), `t` (one message) and `s`/`u` (declared space) are
# not structures either, and a sub-directive-free run of them is the idiom.
STRUCTURE_TYPES = 'bw'

# How many same-titled, sub-directive-free entries in a row make a run a
# fragmented structure rather than a coincidence. Three is the smallest number
# that cannot be two neighbors that happen to do the same job.
FRAGMENT_RUN = 3

ENTRY_RE = re.compile(r'^([bcgistuwz]) +(\$?[0-9A-Fa-f]+) *(.*)$')
SUB_RE = re.compile(r'^[BCSTWM] +\$?[0-9A-Fa-f]+')

# Where the head of a title ends and its note about this fragment begins.
HEAD_RE = re.compile(r'[:;,(]|\s[—–-]\s')

# What an index looks like on the title of a fragment: a trailing or embedded
# number, or the words a split puts there. Stripping them is what makes "Loading
# screen row 3" and "Loading screen row 4" the same title.
#
# The `$` is mandatory on the hex alternative. Optional, under re.I, it would
# make every word spelled from the letters A-F an index: `Face sprite` would
# normalize to `sprite`, `Fade table` to `table` and `Dead-ship flag` to `ship
# flag`, and three unrelated entries would collide into one FRAGMENTED finding.
INDEX_RE = re.compile(
    r'(?:\b(?:part|row|column|col|segment|section|block|chunk|piece|line|no\.?|#)\s*)?'
    r'(?:\$[0-9A-Fa-f]{2,}\b|\b\d+\b)'
    r'|\b(?:continued|cont\.?|ctd\.?)\b', re.I)


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def parse_ctl(lines):
    """Return every entry with its line number, type, address, title and sub count."""
    entries = []
    for number, line in enumerate(lines, 1):
        match = ENTRY_RE.match(line.rstrip())
        if match:
            entries.append({'line_number': number, 'type': match.group(1),
                            'address': parse_address(match.group(2)),
                            'title': match.group(3).strip(), 'subs': 0})
    for index, entry in enumerate(entries):
        end = entries[index + 1]['line_number'] if index + 1 < len(entries) else len(lines) + 1
        for number in range(entry['line_number'], end - 1):
            if SUB_RE.match(lines[number].rstrip()):
                entry['subs'] += 1
    return entries


def title_head(title):
    """
    The subject a title names, with its per-fragment note and any index removed.

    Empty when the title is empty or is nothing but an index: an untitled entry
    is `validate_ctl_identity`'s finding, and reporting it here too would record
    one defect twice in the baseline.
    """
    head = HEAD_RE.split(title, maxsplit=1)[0]
    head = INDEX_RE.sub(' ', head.lower().replace('-', ' '))
    return re.sub(r'\s+', ' ', head).strip(' .,')


def check_outside(entries, org, size, path):
    """Report an entry that publishes a page outside the program image."""
    findings = []
    for entry in entries:
        if entry['type'] not in PUBLISHED_TYPES:
            continue
        if org <= entry['address'] < org + size:
            continue
        where = 'below' if entry['address'] < org else 'above'
        findings.append((
            entry['line_number'], 'OUTSIDE',
            f"`{entry['type']} ${entry['address']:04X}` publishes a page and a memory-map row "
            f"{where} the program image (${org:04X}..${org + size - 1:04X}). The program never "
            f"occupies ${entry['address']:04X}, so the page documents memory this disassembly "
            f"does not describe. Render-only or generated data belongs in a `.ref` "
            f"`[Graphic:]` entry, not in the address space",
            path, entry['address']))
    return findings


def check_fragmented(entries, path):
    """Report a run of entries that is one structure cut into pages."""
    findings = []
    runs, current = [], []
    for entry in entries:
        breaks = (not current
                  or entry['type'] != current[-1]['type']
                  or entry['type'] not in STRUCTURE_TYPES
                  or entry['subs']
                  or current[-1]['subs']
                  or not title_head(entry['title'])
                  or title_head(entry['title']) != title_head(current[-1]['title']))
        if breaks:
            runs.append(current)
            current = [entry]
        else:
            current.append(entry)
    runs.append(current)

    for run in runs:
        if (len(run) < FRAGMENT_RUN or run[0]['type'] not in STRUCTURE_TYPES
                or run[0]['subs'] or not title_head(run[0]['title'])):
            continue
        head, tail = run[0], run[-1]
        findings.append((
            head['line_number'], 'FRAGMENTED',
            f"{len(run)} consecutive `{head['type']}` entries, ${head['address']:04X} through "
            f"${tail['address']:04X}, each with no sub-directive and each headed "
            f"\"{title_head(head['title'])}\" — the first reads \"{head['title']}\". "
            f"That is one structure published as {len(run)} pages and {len(run)} memory-map "
            f"rows, with no page saying what the whole of it is. Make it one entry with one "
            f"title and a sub-directive per part",
            path, head['address']))
    return findings


def token(finding):
    """The baseline's third field: the address of the entry the finding points at."""
    return f'${finding[4]:04X}'


def main():
    parser = argparse.ArgumentParser(
        description='Validate the set of pages a .ctl publishes.')
    parser.add_argument('ctl', nargs='+',
                        help='every .ctl the project builds the disassembly from; a '
                             'secondary one publishes pages exactly as the main one does')
    parser.add_argument('--org', type=lambda s: int(s, 0), required=True,
                        help='address the program image loads at')
    parser.add_argument('--size', type=lambda s: int(s, 0), required=True,
                        help='length of the program image in bytes')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    findings, published = [], 0
    for path in args.ctl:
        try:
            with open(path, encoding='utf-8') as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            print(f'Error: File not found: {path}')
            return 1
        entries = parse_ctl(lines)
        published += sum(1 for e in entries if e['type'] in PUBLISHED_TYPES)
        findings += (check_outside(entries, args.org, args.size, path)
                     + check_fragmented(entries, path))
    findings.sort(key=lambda f: (f[3], f[0]))

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, findings, [], token_of=token))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, findings, [],
                                              report_stale=not args.ignore_stale,
                                              token_of=token)

    if new:
        print(f'Found {len(new)} page(s) the .ctl should not publish:')
        print()
        for line_number, kind, message, path, _ in new:
            print(f'  {os.path.basename(path)}:{line_number}: {kind} — {message}')
            print()
    elif not held and not stale:
        print(f'publication: {published} page(s), every one inside '
              f'${args.org:04X}..${args.org + args.size - 1:04X} and standing for one thing')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
