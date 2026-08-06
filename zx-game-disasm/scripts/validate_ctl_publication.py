#!/usr/bin/env python3
"""
Validate the set of pages a .ctl publishes: one page per thing, and only things.

Every entry in a .ctl becomes a page on the site and a row in the memory map.
Four failures put the wrong page there, and all four pass the round-trip, the
tiling check and the identity check, because none of them is about the bytes an
entry declares - it is about whether the entry is the thing its heading says.

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

  MIXED       several things fused into one page, under the heading of the
              first. A `t $9A00 Text: GAME OVER` that runs on to the next entry
              swallows the `B` sub-directives after the message, so a runtime
              counter such as `idle_ticks` publishes on a page headed
              "Text: GAME OVER" and appears under that title in the memory map.
              The fix is a split: one entry per thing, each headed by what it
              is.

  MUTABLE     a `b` entry the program stores into. `b` says these bytes are what
              the program was loaded with and stay that way - a table, a glyph
              set, a constant. `g` says the program writes here as it runs, and
              SkoolKit heads a `g` page "Game status buffer entry at", so the type
              is what the page tells the reader the bytes are. It also decides
              what a porter initializes versus allocates, and which addresses an
              agent-trainer treats as state. `b $9B00 Game progress and option
              settings` over the level number and the lives count publishes as
              load-time data bytes the game writes.

Consecutive entries always tile - the next entry's address is where the previous
one ends - so contiguity carries no information and is not tested. What carries
information is that the run says one thing N times. A project with a genuine row
of small distinct tables states a distinct title on each and is not reported.

## Which sub-directive disagreements are real (MIXED)

Only `t` is tested. A `b` entry legitimately mixes `B`, `W` and `S`; a `g` entry
does the same; a `w` entry carries its own stride and declares no sub-directive
at all. `t` is the one type whose contents are a single kind by construction -
characters - so a non-`T` sub-directive inside one is something else riding along
on a message's page. `M`, a comment spanning sub-blocks, declares no bytes and is
not a content type, so it never disagrees with anything.

The general form - any entry whose sub-directives disagree with its own type -
is not safe: it has no definition that the four data types share.

## Why MUTABLE reads the code and not the prose (and why the converse is absent)

A vocabulary match over entry descriptions - "while", "set when", "cleared on",
"counts", "current", "progress", "advances" - flags many of a project's `b`
entries. The count is not the objection: a check firing on many data blocks is
affordable if every finding is true. The objection is that nothing in the match
is evidence. "Non-zero while a level transition runs" is a sentence, and a
linter reading it is guessing at what its author meant - the same words sit in
the description of a static table, saying what the reader does while scanning
it. A check whose findings have to be argued about one at a time gets switched
off, which is the failure the baseline mechanism exists to prevent.

The code settles it instead. An address a routine stores to is not what the
program was loaded with, and the .skool the build already produces carries every
such store. Z80 has exactly one addressing mode that names its target in the
instruction - `LD (nn),A` and `LD (nn),rr` for BC/DE/HL/SP/IX/IY - so those
instructions are read out of the .skool and their targets matched against the
entries. A finding is then an instruction address, not an adjective.

That evidence is sound and incomplete, and the asymmetry is the whole design. A
store to `$9B06` proves `$9B06` is not static. Silence proves nothing: a routine
that writes through `HL`, `IX` or an `LDIR` names no target in the instruction.
A tile state map, a keyboard save or an object record the game writes only
through a register pair shows no absolute store at all. So the converse check, a
`g` entry nothing writes, is not implemented: it would report exactly those
entries. A `g` entry mistyped the other way has to be found by reading the code,
not by a linter.

A partly-written `b` entry is reported too, and the message says how many of its
bytes are written - as the evidence, not as a verdict on the rest. The asymmetry
holds there as well: one absolute store in a large buffer the game clears
through `HL` says the buffer is not static, not that one byte of it is. So the
remedy leads with the retype whatever the count, and offers the split as the
alternative for the case a reader can confirm from the code - a static table with
a runtime slot glued to its tail.

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
                                   --skool FILE [--baseline FILE]
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
SUB_RE = re.compile(r'^([BCSTWM]) +(\$?[0-9A-Fa-f]+)')
LABEL_RE = re.compile(r'^@ +(\$?[0-9A-Fa-f]+) +label=(\S+)')

# The one entry type whose contents are a single kind by construction. `M` spans
# sub-blocks with a comment and declares no bytes, so it is not a content type.
SINGLE_KIND_SUBS = {'t': 'T'}
NON_CONTENT_SUB = 'M'

# The type whose whole promise is that the bytes never change.
STATIC_TYPE = 'b'

# A skool instruction line: the entry-type or branch-marker column, the address,
# then the instruction. `@label=` and `;` lines are excluded by the leading column.
SKOOL_INSTR_RE = re.compile(r'^([ *bcgistuw])\$([0-9A-Fa-f]{4}) (.*)$')

# Every Z80 store whose target is in the instruction: `LD (nn),A` and `LD (nn),rr`
# for BC, DE, HL, SP, IX and IY. A store through a register pair - `LD (HL),A`,
# `LD (IX+d),A`, `LDIR` - names no target, so the .skool cannot yield one.
#
# The `$` is mandatory: the build disassembles with `sna2skool.py --hex`, so an
# absolute operand is hex, and requiring the sigil keeps a decimal-looking token
# somewhere else on the line from being read as an address.
#
# Case-insensitive because `sna2skool.py --lower` writes the whole listing in
# lower case, and a store the pattern cannot read is a target the check drops.
STORE_RE = re.compile(r'\bLD +\((\$[0-9A-Fa-f]+)\),(A|BC|DE|HL|SP|IX|IY)\b', re.I)

# A data directive's operand is bytes, not an instruction. `DEFM "LD ($F128),A"`
# spells a store without being one, so these lines are not read for targets.
DATA_DIRECTIVE_RE = re.compile(r'DEF[BWMS]\b', re.I)

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
    """
    Return every entry with its line number, type, address, title and contents.

    `subs` counts the sub-directives inside the entry and `sub_kinds` pairs each
    one's letter with its address. `end` is the address the entry stops at, taken
    from the next entry; the last entry in a file has no stated length, so its
    `end` is None and the checks that need a span skip it.
    """
    entries = []
    for number, line in enumerate(lines, 1):
        match = ENTRY_RE.match(line.rstrip())
        if match:
            entries.append({'line_number': number, 'type': match.group(1),
                            'address': parse_address(match.group(2)),
                            'title': match.group(3).strip(), 'subs': 0,
                            'sub_kinds': [], 'end': None})
    for index, entry in enumerate(entries):
        if index + 1 < len(entries):
            entry['end'] = entries[index + 1]['address']
        end = entries[index + 1]['line_number'] if index + 1 < len(entries) else len(lines) + 1
        for number in range(entry['line_number'], end - 1):
            match = SUB_RE.match(lines[number].rstrip())
            if match:
                entry['subs'] += 1
                entry['sub_kinds'].append((match.group(1), parse_address(match.group(2))))
    return entries


def parse_labels(lines):
    """Map each address the .ctl names to that label, for naming a byte in a finding."""
    labels = {}
    for line in lines:
        match = LABEL_RE.match(line.rstrip())
        if match:
            labels[parse_address(match.group(1))] = match.group(2)
    return labels


def instruction_body(text):
    """The instruction with its trailing `;` comment removed, quotes respected."""
    quoted = False
    for index in range(1, len(text)):
        if text[index] == '"':
            quoted = not quoted
        elif text[index] == ';' and not quoted and text[index - 1] == ' ':
            return text[:index]
    return text


def read_stores(path):
    """
    Map each address the program stores to onto the instruction addresses that do it.

    Only absolute stores are found - see the module docstring: the result is sound
    evidence that an address is written and no evidence at all that one is not.

    Raises ValueError when no line in the file is an instruction at all. A .skool
    the pattern cannot read yields no target, and MUTABLE then reports nothing on
    a project full of `b` entries the code writes - which reads as clean. The
    check has to say it could not read the file instead.
    """
    stores, instructions = {}, 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            match = SKOOL_INSTR_RE.match(line.rstrip())
            if not match:
                continue
            instructions += 1
            body = instruction_body(match.group(3))
            if DATA_DIRECTIVE_RE.match(body):
                continue
            source = int(match.group(2), 16)
            for store in STORE_RE.finditer(body):
                target = parse_address(store.group(1))
                width = 1 if store.group(2).upper() == 'A' else 2
                for offset in range(width):
                    stores.setdefault(target + offset, []).append(source)
    if not instructions:
        raise ValueError(f'{path} holds no instruction line this check can read. It expects '
                         f'the .skool the build generates, which `sna2skool.py --hex` writes '
                         f'as `c$F000 LD ($9B00),A`')
    return stores


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


def check_mixed(entries, path):
    """Report an entry holding something other than what its type declares."""
    findings = []
    for entry in entries:
        expected = SINGLE_KIND_SUBS.get(entry['type'])
        if not expected:
            continue
        foreign = [(kind, address) for kind, address in entry['sub_kinds']
                   if kind not in (expected, NON_CONTENT_SUB)]
        if not foreign:
            continue
        listed = ', '.join(f'`{kind} ${address:04X}`' for kind, address in foreign[:3])
        findings.append((
            entry['line_number'], 'MIXED',
            f"`{entry['type']} ${entry['address']:04X} {entry['title']}` publishes one page "
            f"headed as text, but not all of its contents are text: {listed} among its "
            f"{entry['subs']} sub-directives. Everything inside the entry renders on that page "
            f"and is filed under that title in the memory map, so a reader looking for those "
            f"bytes finds them under a message. Split the entry: one entry per thing, each "
            f"headed by what it is",
            path, entry['address']))
    return findings


def check_mutable(entries, stores, labels, path):
    """Report a `b` entry the program stores into."""
    findings = []
    for entry in entries:
        if entry['type'] != STATIC_TYPE or entry['end'] is None:
            continue
        written = [address for address in range(entry['address'], entry['end'])
                   if address in stores]
        if not written:
            continue
        size = entry['end'] - entry['address']
        cited = ', '.join(
            f"${address:04X}"
            + (f" ({labels[address]})" if address in labels else '')
            + f" from ${stores[address][0]:04X}"
            for address in written[:3])
        scope = ('every one of them' if len(written) == size
                 else f'{len(written)} of them')
        # The count is evidence, never a verdict on the bytes no store names: a
        # buffer written wholesale through `HL` can show one absolute store in
        # hundreds of bytes. So the retype leads at any count, and the split is
        # the alternative for a reader who can confirm the rest is static.
        remedy = ('Retype the entry `g`'
                  + ('' if len(written) == size else
                     ', or - if the rest of it really is a static table with a runtime slot '
                     'glued to its tail - split the written bytes into a `g` entry of their own'))
        findings.append((
            entry['line_number'], 'MUTABLE',
            f"`{entry['type']} ${entry['address']:04X} {entry['title']}` publishes "
            f"{size} byte{'' if size == 1 else 's'} as data the program was loaded with, and the "
            f"code stores to {scope}: {cited}. Bytes the program writes as it runs are `g`, the "
            f"page SkoolKit heads \"Game status buffer entry at\" — the type is what tells a "
            f"reader whether a value survives a replay, a porter what to allocate rather than "
            f"initialize, and an agent-trainer which addresses are state. {remedy}",
            path, entry['address']))
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
    parser.add_argument('--skool', required=True,
                        help='the .skool the build generates from these .ctl files; it '
                             'is the witness for MUTABLE, and passing it is not optional '
                             'because a linter that silently skips half its checks is '
                             'worse than one that is not wired up')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        stores = read_stores(args.skool)
    except FileNotFoundError:
        print(f'Error: File not found: {args.skool}')
        return 1
    except ValueError as error:
        print(f'Error: {error}')
        return 1

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
                     + check_fragmented(entries, path)
                     + check_mixed(entries, path)
                     + check_mutable(entries, stores, parse_labels(lines), path))
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
              f'${args.org:04X}..${args.org + args.size - 1:04X}, standing for one thing, and '
              f'no `b` page over any of the {len(stores)} address(es) the code stores to')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
