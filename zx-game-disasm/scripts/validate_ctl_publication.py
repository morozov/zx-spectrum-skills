#!/usr/bin/env python3
"""
Validate the set of pages a .ctl publishes: one page per thing, and only things.

Every entry in a .ctl becomes a page on the site and a row in the memory map.
Five failures put the wrong page there, and all five pass the round-trip, the
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

  MUTABLE     a `b` or `u` entry the program stores into. `b` says these bytes are
              what the program was loaded with and stay that way - a table, a
              glyph set, a constant; `u` says nothing in the image reads or writes
              them at all, which is that promise and more. `g` says the program
              writes here as it runs, and SkoolKit heads a `g` page "Game status
              buffer entry at", so the type is what the page tells the reader the
              bytes are. It also decides what a porter initializes versus
              allocates, and which addresses an agent-trainer treats as state.
              `b $9B00 Game progress and option settings` over the level number
              and the lives count publishes as load-time data bytes the game
              writes.

  CONTRADICTED an entry that says nothing writes these bytes, over an address
              the code stores to. `b $F100 Undetermined - no reader or writer
              found in the image`, labeled `unused_f100`, can publish bytes the
              listing on that same page sets: `slot_1_x` from $9100, `slot_2_x`
              from $9105, `hit_side` from $9200. MUTABLE reports the letter, and
              the letter is the smaller error - a reader who distrusts a `b`
              still has no reason to distrust a sentence, and `unused_f100` is
              what he greps for.

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

`u` is held to the same evidence, because it makes the same promise the other way
round: the skill's own rule is that a region nothing reads or writes is `u` rather
than `b`, so an absolute store into one is the same mistyping and takes the same
`g`. Settling `b`, `g` and `u` in the prose and gating two of the three would
leave the third stated and unheld.

## Why CONTRADICTED reads the prose, where MUTABLE refuses to

The objection above is to a word standing in for evidence, not to reading words.
"Non-zero while a level transition runs" is a guess about the author's meaning.
"No writer found in the image" is a statement of the same fact `read_stores`
already returns, and the file returns the opposite - so the finding is still an
instruction address, and the sentence is the thing it convicts. Every part of the
check exists to keep that anchor:

- **The evidence is a writer, so only a writer is contradicted.** A store proves
  nothing about readers, and a byte written and never read is a real thing to
  document. "No reader found in the image" is a claim a store leaves standing;
  only the writer half of "no reader or writer" is read.
- **A one-word characterization is read where it names the entry: the title and
  the `@label`.** Inside a paragraph `unused` is about whatever the paragraph
  discusses - an object record its handlers write through IY can say "+$02 to
  +$06 are unused by the handlers" about five of its fields. A denial with a
  verb ("nothing writes", "no writer", "never written") is a statement about
  writers wherever it stands, so it is read in the entry's `D` and `N` too.
- **The word is not read on a `g` entry at all.** That letter already says the
  program writes these bytes, so the store the check would convict it with is the
  store the letter promised, and `orphan_list_head` over the head of an
  orphaned-object list is a name rather than a denial. There would be nothing to
  strike and nothing to retype in such a finding, which is a build broken over a
  naming choice. A verb denial is still read there: an entry saying "nothing
  writes these" over a store contradicts itself whatever its letter.
- **A claim inside the entry is read over its own bytes.** `D`/`N` at the entry's
  address, and the entry's title, speak for everything it publishes. Text written
  at an address inside it - a `D`/`N` further in, a description on a
  sub-directive - speaks for that sub-block, from its address to the next address
  carrying text. `N $D0E0 Unused tail of the back-buffer page` sits inside
  `b $D000` and is about $D0E0 onwards, not about $D000.
- **A writer the prose names is not a writer the prose denies.** "So these 52
  bytes are never written by it" carries a denial and names its writer two
  clauses earlier (#R$9C80). A store is evidence only when neither its own
  address nor the address of the .skool entry containing it is named in text that
  speaks for those bytes - the entry's own, and the sub-block's own for a claim
  written there. Both forms of naming count: the address, and the label, which is
  what the listing prints and therefore what an author writes.
- **`c` entries are not read.** A routine's description is about the data it
  touches, not about its own bytes: a routine carrying one of these denials is
  speaking of a table living somewhere else.

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
SUB_RE = re.compile(r'^([BCSTWM]) +(\$?[0-9A-Fa-f]+)(\S*) *(.*)$')
LABEL_RE = re.compile(r'^@ +(\$?[0-9A-Fa-f]+) +label=(\S+)')
NOTE_RE = re.compile(r'^[DN] +(\$?[0-9A-Fa-f]+) *(.*)$')

# An identifier in prose, for the label a denial names its writer by.
WORD_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')

# The one entry type whose contents are a single kind by construction. `M` spans
# sub-blocks with a comment and declares no bytes, so it is not a content type.
SINGLE_KIND_SUBS = {'t': 'T'}
NON_CONTENT_SUB = 'M'

# The types whose letter promises the bytes are not written as the program runs.
# `b` says they are what the program was loaded with; `u` says nothing in the
# image reads or writes them at all, which is the same promise and more. A store
# breaks either one, and the repair is the same letter.
UNWRITTEN_TYPES = 'bu'
UNWRITTEN_PROMISE = {'b': 'data the program was loaded with',
                     'u': 'a region nothing in the image reads or writes'}
UNWRITTEN_REST = {'b': 'the rest of it really is a static table with a runtime slot '
                       'glued to its tail',
                  'u': 'the rest of it really is untouched'}

# Types whose own text is about their own bytes. A routine's description is
# about the data it touches, so a `c` entry saying "never read" means a sound
# table living somewhere else.
CLAIMING_TYPES = 'bgstuw'

# The type whose letter already says the program writes these bytes. A one-word
# characterization on a `g` entry is therefore not a denial of a writer: the page
# is headed "Game status buffer entry at", so `orphan_list_head` over the head of
# an orphaned-object list names what the list holds, and the store that would
# convict it is the store the letter promised. A denial with a verb is still read
# there - an entry saying "nothing writes these" over a store contradicts itself
# whatever its letter is.
WRITTEN_TYPE = 'g'

# A denial with a verb: a statement about writers wherever it stands, so it is
# read in the entry's title and in its `D`/`N`. The bounded gap carries "no reader
# or writer" and "nothing in the image writes"; `\w+` cannot cross the punctuation
# that would end the clause, so the two halves stay in one sentence.
WRITER_DENIAL_RE = re.compile(
    r'\bno(?:\s+\w+){0,3}\s+writers?\b'
    r'|\bnothing(?:\s+\w+){0,4}\s+writes\b'
    r'|\b(?:never|not)\s+written\b', re.I)

# A one-word characterization, read only where it names the entry as a whole -
# the title and the `@label`. Inside a paragraph it is about whatever the
# paragraph discusses: an object record the game writes every frame says "+$02 to
# +$06 are unused by the handlers" about five of its fields.
#
# All three words deny any use, which is what makes a store contradict them: a
# block a routine stores to is not unused, not unreferenced and not an orphan.
# "No reader" is the denial a store leaves standing, and it is not read here.
UNUSED_RE = re.compile(r'\bunused\b|\bunreferenced\b|\borphan\b', re.I)
UNUSED_LABEL_RE = re.compile(r'(?:^|_)(?:unused|unreferenced|orphan)(?:_|$)', re.I)

# An address the entry's text names, in the `#R$9C40` cross-reference or bare. A
# writer the text names is a writer the text does not deny.
CITED_RE = re.compile(r'\$([0-9A-Fa-f]{4})\b')

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


def parse_ctl(lines, image_end=None):
    """
    Return every entry with its line number, type, address, title and contents.

    `subs` counts the sub-directives inside the entry and `sub_kinds` pairs each
    one's letter with its address. `end` is the address the entry stops at, taken
    from the next entry; the last entry in a file states no length of its own, so
    it takes `image_end` - the end of the program image, which is where the
    disassembly stops - and is `None` only when even that is unknown or behind it.

    `note` is the entry's own description: the `D` and `N` text at the entry's
    address, which speaks for every byte the entry publishes.

    `sub_claims` is the text written at an address *inside* the entry - a `D` or
    `N` further in, and the description on a sub-directive - each with the byte
    range it speaks for, which runs to the next address carrying text. A comment
    on one sub-block is about those bytes, so it is read about those bytes and
    not about the entry.
    """
    entries = []
    for number, line in enumerate(lines, 1):
        match = ENTRY_RE.match(line.rstrip())
        if match:
            entries.append({'line_number': number, 'type': match.group(1),
                            'address': parse_address(match.group(2)),
                            'title': match.group(3).strip(), 'subs': 0,
                            'sub_kinds': [], 'end': None, 'note': '',
                            'sub_claims': []})
    for index, entry in enumerate(entries):
        if index + 1 < len(entries):
            entry['end'] = entries[index + 1]['address']
        elif image_end is not None and image_end > entry['address']:
            entry['end'] = image_end
        end = entries[index + 1]['line_number'] if index + 1 < len(entries) else len(lines) + 1
        note, inside = [], {}
        for number in range(entry['line_number'], end - 1):
            text = lines[number].rstrip()
            match = SUB_RE.match(text)
            if match:
                entry['subs'] += 1
                address = parse_address(match.group(2))
                entry['sub_kinds'].append((match.group(1), address))
                if match.group(4).strip():
                    claim = inside.setdefault(address, {'line_number': number + 1, 'text': []})
                    claim['text'].append(match.group(4).strip())
            match = NOTE_RE.match(text)
            if match:
                address = parse_address(match.group(1))
                if address == entry['address']:
                    note.append(match.group(2).strip())
                else:
                    claim = inside.setdefault(address, {'line_number': number + 1, 'text': []})
                    claim['text'].append(match.group(2).strip())
        entry['note'] = ' '.join(note)
        addresses = sorted(inside)
        for position, address in enumerate(addresses):
            following = (addresses[position + 1] if position + 1 < len(addresses)
                         else entry['end'])
            entry['sub_claims'].append({'line_number': inside[address]['line_number'],
                                        'address': address, 'end': following,
                                        'text': ' '.join(inside[address]['text'])})
    return entries


def parse_labels(lines):
    """
    Map each address the .ctl names to that label, and back.

    Returns (labels, addresses_by_label): the first names a byte in a finding,
    the second reads a label out of prose, which is how an entry names the
    routine that writes it - the listing prints the label, not the address.
    """
    labels, addresses = {}, {}
    for line in lines:
        match = LABEL_RE.match(line.rstrip())
        if match:
            address = parse_address(match.group(1))
            labels[address] = match.group(2)
            addresses[match.group(2)] = address
    return labels, addresses


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
    Return (stores, owners) read from the .skool the build generates.

    `stores` maps each address the program stores to onto the instruction
    addresses that do it. Only absolute stores are found - see the module
    docstring: the result is sound evidence that an address is written and no
    evidence at all that one is not.

    `owners` maps each of those instruction addresses onto the address of the
    .skool entry holding it, which is the address prose cites when it names a
    writer: an entry's text says "#R$9C40", never the address of the `LD` inside
    it.

    Raises ValueError when no line in the file is an instruction at all. A .skool
    the pattern cannot read yields no target, and MUTABLE then reports nothing on
    a project full of `b` entries the code writes - which reads as clean. The
    check has to say it could not read the file instead.
    """
    stores, owners, instructions, entry = {}, {}, 0, None
    with open(path, encoding='utf-8') as f:
        for line in f:
            match = SKOOL_INSTR_RE.match(line.rstrip())
            if not match:
                continue
            instructions += 1
            source = int(match.group(2), 16)
            # The entry-type column carries a letter on an entry's first line and
            # a space or `*` on every line after it.
            if match.group(1) != ' ' and match.group(1) != '*':
                entry = source
            body = instruction_body(match.group(3))
            if DATA_DIRECTIVE_RE.match(body):
                continue
            for store in STORE_RE.finditer(body):
                target = parse_address(store.group(1))
                width = 1 if store.group(2).upper() == 'A' else 2
                for offset in range(width):
                    stores.setdefault(target + offset, []).append(source)
                owners[source] = entry
    if not instructions:
        raise ValueError(f'{path} holds no instruction line this check can read. It expects '
                         f'the .skool the build generates, which `sna2skool.py --hex` writes '
                         f'as `c$F000 LD ($9B00),A`')
    return stores, owners


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
    """Report a `b` or `u` entry the program stores into."""
    findings = []
    for entry in entries:
        if entry['type'] not in UNWRITTEN_TYPES or entry['end'] is None:
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
                     f", or - if {UNWRITTEN_REST[entry['type']]} - split the written bytes "
                     f"into a `g` entry of their own"))
        findings.append((
            entry['line_number'], 'MUTABLE',
            f"`{entry['type']} ${entry['address']:04X} {entry['title']}` publishes "
            f"{size} byte{'' if size == 1 else 's'} as {UNWRITTEN_PROMISE[entry['type']]}, and the "
            f"code stores to {scope}: {cited}. Bytes the program writes as it runs are `g`, the "
            f"page SkoolKit heads \"Game status buffer entry at\" — the type is what tells a "
            f"reader whether a value survives a replay, a porter what to allocate rather than "
            f"initialize, and an agent-trainer which addresses are state. {remedy}",
            path, entry['address']))
    return findings


def acknowledged_addresses(text, addresses_by_label):
    """
    Every writer address the text names: an address it cites, or a label it uses.

    `#R$9C40` and a bare `$9C40` are the citation; `init_levels` is the same
    statement in the form a reader of the page actually sees, since the listing
    prints the label and not the address. Both are the entry saying what writes
    the bytes, which is the opposite of denying that anything does.
    """
    named = {int(match, 16) for match in CITED_RE.findall(text)}
    named |= {addresses_by_label[word] for word in WORD_RE.findall(text)
              if word in addresses_by_label}
    return named


def unacknowledged_stores(start, end, stores, owners, cited):
    """
    Map each written address in `start`..`end` onto a store `cited` does not name.

    `cited` is every writer address named by text that speaks for these bytes. A
    store is acknowledged when that text names the instruction's own address or
    the address of the .skool entry containing it: "nothing writes them
    individually; the only writer is the level-setup clear (#R$9C40)" names its
    writer, and a sentence that names a writer is not denying one. Addresses whose
    every store is acknowledged are left out.
    """
    found = {}
    for address in range(start, end):
        for source in stores.get(address, []):
            if source in cited or owners.get(source) in cited:
                continue
            found[address] = source
            break
    return found


def entry_claims(entry, labels):
    """
    Every claim the entry publishes, with the bytes each one speaks for.

    The entry's own text - title, `@label`, `D`/`N` at its address - speaks for
    all of its bytes. Text at an address inside it speaks for that sub-block:
    `N $D0E0 Unused tail of the back-buffer page` inside `b $D000` is a statement
    about $D0E0 onwards, so it is read there and not over the whole entry.

    A one-word characterization is read only where it names bytes the letter does
    not already declare written. On a `g` entry the store is what the letter
    promised, so `orphan_list_head` is a name, not a denial; a denial with a verb
    is read on any type.
    """
    label = labels.get(entry['address'], '')
    words = entry['type'] != WRITTEN_TYPE
    claims = []

    stated = []
    for where, text in (('title', entry['title']), ('description', entry['note'])):
        denial = WRITER_DENIAL_RE.search(text) or (
            UNUSED_RE.search(text) if where == 'title' and words else None)
        if denial:
            stated.append(f'its {where} says "{denial.group(0)}"')
    if words and UNUSED_LABEL_RE.search(label):
        stated.append(f'it is labeled `{label}`')
    if stated:
        claims.append({'line_number': entry['line_number'], 'start': entry['address'],
                       'end': entry['end'], 'stated': stated, 'text': '',
                       'lead': f"`{entry['type']} ${entry['address']:04X} "
                               f"{entry['title']}` publishes"})

    for sub in entry['sub_claims']:
        if sub['end'] is None:
            continue
        denial = WRITER_DENIAL_RE.search(sub['text'])
        if not denial:
            continue
        claims.append({'line_number': sub['line_number'], 'start': sub['address'],
                       'end': sub['end'], 'text': sub['text'],
                       'stated': [f'the text on ${sub["address"]:04X} says '
                                  f'"{denial.group(0)}"'],
                       'lead': f"`{entry['type']} ${entry['address']:04X} "
                               f"{entry['title']}` describes ${sub['address']:04X} over"})
    return claims


def check_contradicted(entries, stores, owners, labels, addresses_by_label, path):
    """Report a claim that nothing writes bytes the code stores to."""
    findings = []
    for entry in entries:
        if entry['type'] not in CLAIMING_TYPES or entry['end'] is None:
            continue
        # Acknowledgment reaches as far as the claim does. The entry's own text
        # speaks for every byte it publishes, so a writer named there answers any
        # claim inside it; a sub-block's text answers only its own. A writer named
        # on some other sub-block, fifty bytes away, is not this claim naming it.
        entry_text = f"{entry['title']} {entry['note']}"

        for claim in entry_claims(entry, labels):
            acknowledged = acknowledged_addresses(f"{entry_text} {claim['text']}",
                                                  addresses_by_label)
            written = unacknowledged_stores(claim['start'], claim['end'],
                                            stores, owners, acknowledged)
            if not written:
                continue
            size = claim['end'] - claim['start']
            cited = ', '.join(
                f"${address:04X}"
                + (f" ({labels[address]})" if address in labels else '')
                + f" from ${written[address]:04X}"
                for address in sorted(written)[:3])
            # `g` is already the letter for bytes the program writes, so only the
            # sentence is wrong there; on any other type the same store settles
            # both, and saying so is the whole fix rather than half of it.
            letter = ('' if entry['type'] == WRITTEN_TYPE else
                      ' The same store settles the letter: what the program writes is `g`, '
                      'and `u` is the type for a region nothing reads or writes.')
            findings.append((
                claim['line_number'], 'CONTRADICTED',
                f"{claim['lead']} "
                f"{size} byte{'' if size == 1 else 's'} and claims nothing writes them — "
                f"{', and '.join(claim['stated'])} — while the code stores to {len(written)} "
                f"of them: {cited}. Nothing there names those writers, so the page states the "
                f"opposite of what the listing on it shows, and a sentence is the one part a "
                f"reader has no way to check. Strike the claim and say what writes the "
                f"bytes.{letter}",
                path, claim['start']))
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
        stores, owners = read_stores(args.skool)
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
        entries = parse_ctl(lines, image_end=args.org + args.size)
        labels, addresses_by_label = parse_labels(lines)
        published += sum(1 for e in entries if e['type'] in PUBLISHED_TYPES)
        findings += (check_outside(entries, args.org, args.size, path)
                     + check_fragmented(entries, path)
                     + check_mixed(entries, path)
                     + check_mutable(entries, stores, labels, path)
                     + check_contradicted(entries, stores, owners, labels,
                                          addresses_by_label, path))
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
              f'no page typed `b` or claiming nothing writes it over any of the '
              f'{len(stores)} address(es) the code stores to')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
