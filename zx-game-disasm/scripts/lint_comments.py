#!/usr/bin/env python3
"""
Lint comment quality in a generated SkoolKit .skool file, and investigation
vocabulary in the prose deliverables beside it (`*.ref`, `spec/*.md`).

A green build proves byte-identity, never that the documentation is good. This
catches the mechanical comment-quality violations a round-trip never sees, the
ones a reviewer would otherwise flag by hand:

  - RET            a comment on a bare unconditional RET (self-evident; leave it bare)
  - RET_GROUP      a bare unconditional RET swallowed by a '{ }' comment group —
                   the group text describes the logic above; the RET is
                   infrastructure. Close the group on the last logic instruction.
  - RESTATE        a comment that only restates the instruction (LD A,n -> "Load n into A")
  - PLACEHOLDER    a placeholder label left in place (work_b, helper_8e3a, L5B50)
  - SELFLINK       'label (#R$addr)' where the #R resolves to that same label —
                   renders as "name (name)" in the built HTML
  - DIARY          investigation vocabulary in reader-facing text ("unverified",
                   "PROVISIONAL", "this pass", "verified live", "under emulation")
                   — type the uncertainty instead, and cite the code, not a run
  - OPERAND_ECHO   a comment repeating what its own instruction's operand
                   already carries — an address it #R-references, or an
                   immediate it spells out. The row shows the value once
                   already; saying it again says it twice on one line. Runs on
                   the rows of a '{ }' group too: a group opens on the row
                   carrying the operand its first sentence names, which is where
                   the worst instance of this defect lives. Rows whose subject
                   IS the byte are excluded structurally — see
                   operand_literals()
  - ELLIPSIS       a comment spliced across instructions with '...' — one
                   thought spanning rows is a '{ }' comment group, not chained
                   fragments
  - GROUP_SPLIT    a '{ }' comment group spanning an unconditional transfer of
                   control — control leaves the span there, so what follows is
                   a second act wearing the first one's sentence
  - GROUP_ENTRY    a '{ }' comment group whose interior is jumped to from
                   outside the span — a reader arriving by that jump is handed
                   a sentence about instructions that never ran
  - GROUP_SKIP     a '{ }' comment group whose own branch jumps forward over
                   part of its span — the sentence covers rows that do not run
                   on the path that skips them
  - BASE_ECHO      one comment carrying a value twice, once in each base
                   ('$8A (138)') — the base is a notation, the second spelling
                   is the same value read back
  - PITCH          a pitch stated in Hz — the #AUDIO beside it already plays the
                   pitch, so the figure is the clip read back in numbers. The
                   machine's own constants (the 3.5 MHz clock, the 50 Hz frame
                   interrupt) are not pitches and are not reported
  - CODE_ECHO      a number the player cannot see, labeled by an encoding noun:
                   "the drone (type 19)", "enters state 2", "tile codes $21-$44".
                   Every prose unit but register rows and a table's key column;
                   a variable's own data row defines its encoding and is exempt
                   (AUD-4)
  - DATA_ECHO      a data row whose comment repeats the row: an index key at
                   its head ("Code $12:", "Tile $21") or one of its own bytes.
                   The address is the row's position and the bytes are on the
                   line; the comment says what the row holds, and the block
                   description says once what the table is indexed by. A table
                   cell outside the key column that opens on an index is the
                   same defect (ROW-1)
  - CODE_PAREN     a name followed by its code in parentheses, in any shape:
                   "the lantern ($10)", "Wall/border ($21–$44)", "crate
                   (code $12)", "(top-left tile $66)". OUT/IN port operands,
                   register rows and a table's key column are exempt (AUD-4)
  - NUMBER_LIST    four or more numbers in a run, or three after "level(s)":
                   "those of 52, 54, 55, 61, 69" restates the level data (HOME-3)
  - CODE_LIST      three or more codes in a run, "No layout places $04, $12 or
                   $2E" (HOME-3)
  - LEVEL_FACT     a claim about the level data: "Level 100 has no empty cell",
                   "12 slots hold $00", "no level" (HOME-3)
  - HEADING_JARGON a page heading in the program's storage vocabulary ("The
                   spawn-cell record") or a heading or title counting its
                   contents ("The 100 records"). `<hN>`, `[Page:]`,
                   `SectionName=`, entry-section titles and the
                   `[PageHeaders]`/`[Titles]`/`[Links]` values take both halves;
                   entry and glossary titles take the count half (HEAD-2)
  - IDENT_IN_PROSE an equate or constant identifier in prose or a title,
                   "Work buffer (WORKBUF_FB)" (NAME-6)
  - GLOSSARY_DEF   a glossary definition carrying progress ("How far the player
                   has got"), logic that changes the value ("wraps back to 0")
                   or the code that uses it (DEF-2 to DEF-4)
  - GLOSSARY_IDENT a glossary term that is a constant or a category of program
                   symbol, "Constants" (DEF-6)
  - CALLERS        prose listing the code that reads, writes or calls a thing:
                   "Written by #R$B200", "used by the routine", "Callers:".
                   An `s` entry may name what fills it (HOME-4)
  - TYPOGRAPHY     an ASCII stand-in for a typographic character: `2x2`, `->`,
                   `>=`, `45 deg`, `row * 32`, a hyphen or `..` range, a spaced
                   hyphen dash, and `Eb4` for E♭ where the unit is about notes.
                   Quoted game text, text entries and macro parameters keep
                   their bytes (TYPO-2)
  - FRAGMENT_STOP  a full stop on a title, or on a data row, table cell, list
                   item or register row that holds no verb-shaped word,
                   "Silver door key." (TYPO-1)
  - FOIL           an argument against a reading nobody offered: "is not a",
                   ", not to", "rather than", "instead of" (AUD-3)
  - UNUSED_TEXT    any text on an unused entry beyond its "Unused bytes" title;
                   one unused byte keeps its "Unused" row (UNU-1)
  - LABEL_ECHO     a row comment made only of its operand label's words,
                   `DEFW update_rocket ; rocket` (HOME-5)
  - WORDY_VARIABLE more words on a variable of up to four bytes than
                   24 + 6 per extra byte (DEF-5)
  - DEIXIS         an entry pointing at its neighbors by position, "the
                   routines below" (HOME-2)
  - FOREIGN_LOGIC  a data entry's description stating a routine's logic: a
                   sentence holding a link to code and a verb such as "derives",
                   "masks" or "adds" (HOME-2)
  - LABEL_PAIR     a `_hi`/`_high` label whose low byte does not carry the
                   matching `_lo`/`_low` label on the same stem (NAME-7)
  - NON_ZERO       a variable or data definition saying "non-zero" in place of
                   the values it holds (DEF-1)
  - BARE_VALUE     values run into their meanings, "0 left door, 1 right door"
                   (PROSE-9)
  - STE_LENGTH     a sentence of more than 25 words (STE-1)
  - STE_ING        an -ing form outside a technical name; a word of one of the
                   project's labels or glossary term titles is a technical
                   name (STE-4)
  - STE_PARAGRAPH  a paragraph of more than six sentences (STE-6)
  - INLINE_RENDER  a render macro inside a sentence, a row comment or a table
                   cell with three or more words of prose beside it, outside a
                   #UDGTABLE (VIS-1)
  - UNRENDERED     a data block whose title names a sprite, glyph, font or tune,
                   carrying no render macro. The catalog page is an index; a
                   block that encodes one element shows that element
  - SYNTH_ECHO     prose beside an #AUDIO describing how the tone is produced —
                   periods, cycles, T-states, a period formula. The clip is the
                   synthesis; the words owe what the sound means in play, what
                   fires it, and the routine. Block prose and .ref catalogs only:
                   the routine's body is where the algorithm belongs
  - LAYOUT_ECHO    a record's field offset cited in a code block's prose — the
                   layout's one home is the record's own definition; a comment
                   about behavior names the thing, not the byte it sits at
  - SPLICE         a comment continuing the sentence the previous comment left
                   open — one thought split across two comment units, so
                   neither describes the rows it sits on. A unit is open only
                   when it ends on a comma, a conjunction, a preposition, an
                   article or a relative pronoun
  - REFPOINTER     a comment pointing the reader at a `.ref` index file
  - OPEN           a typed uncertainty marker ("(unverified)", "TODO:") — the one
                   legitimate way to leave a doubt in the text, and a standing
                   statement that the work is not finished
  - STAMP          the same sentence (addresses normalized) in two or more
                   block comments — family text stamped per sibling instead of
                   written once at the family head

The text checks read prose units (`prose_units.py`): entry titles, description
paragraphs and notes, row comments and groups, register rows, `.ref` paragraphs,
headings and table cells, glossary titles and bodies, `.ctl` entry titles. Each
check declares the surfaces it applies to and runs over every unit of those
surfaces in every file, so a `.ref` page is held to the same rules as the
listing. Each gating kind's message ends with the rulebook ID it enforces
(`references/rules.md`).

This is deliberately a *small, high-precision* pre-filter, not the review. The
check that matters most is not scriptable and belongs to the Challenger:

  - whether a comment adds what the code cannot show, and whether its sentence
    accounts for everything the span does (both need comprehension).

Where a group's span *ends* is a different question, and the code answers it:
GROUP_SPLIT and GROUP_ENTRY hold a group to one act by reading the control flow,
not the prose. Both are derived from the code, not chosen. What they cannot see
is a long single-entry, single-exit run whose one sentence is too thin for it;
that stays the Challenger's, because nothing structural separates it from a
legitimate unrolled span.

Relocatability (raw addresses in comments) is already covered, and more
precisely, by `skool2asm --create-labels` ("Comment contains address …"), which
the verify gate already treats as an error — so it is not duplicated here.

Operates on the .skool (not the .ctl) because only the generated map pairs each
instruction with its comment and resolves #R references and data sub-blocks. The
checks that read one instruction skip a comment carrying a '{' or '}', whose text
is wrapped across the group's rows and authored on none of them; a group's
interior rows carry no brace and are read like any other row. OPERAND_ECHO reads
every row of a group, brace-carrying or not — see echo_rows() for why.

The catalogs and the behavior spec are the same deliverable, read by the same
reader, so every unit check runs over them too. Pass the `.skool` first: its
labels and entries resolve the `#R` references the other files carry.

The gating kinds are held against the project's `lint-baseline.toml` like every
other gating check, so a mature project records the findings it starts with and
the gate fails on a new one. The advisory kinds print and never fail.

Usage: lint_comments.py <file.skool> [prose-file …]
                       [--baseline FILE] [--write-baseline]
Exit 0 when no unbaselined gating finding stands, 1 otherwise.
"""

import argparse
import bisect
import os
import re
import sys

import ctl_baseline
from prose_units import PROSE_SURFACES, read_units

CHECK = 'comments'

# The kinds that gate. Each is a precise detection of an always-wrong pattern —
# no judgment call sits between the finding and the defect — so each belongs in
# the build's own lint sweep, held against `lint-baseline.toml` like every other
# gating check. The rest (RET, RESTATE, REFPOINTER, STAMP, PLACEHOLDER) are
# prompts to review: a STAMP can be a legitimate formula over a genuinely
# templated reality, and a RET note can carry a real return-state contract, so
# they print and do not fail.
#
# An advisory finding prints and fails nothing, so findings pile up while the
# gate reports every check clean. A check worth writing is worth gating; the
# baseline is what makes gating survivable on a mature project.
GATING_KINDS = frozenset((
    'RET_GROUP', 'SELFLINK', 'DIARY', 'OPERAND_ECHO', 'ELLIPSIS',
    'GROUP_SPLIT', 'GROUP_ENTRY', 'GROUP_SKIP', 'BASE_ECHO', 'SPLICE',
    'LAYOUT_ECHO', 'PITCH', 'SYNTH_ECHO', 'UNRENDERED', 'CODE_ECHO', 'OPEN',
    'DATA_ECHO', 'CODE_PAREN', 'NUMBER_LIST', 'CODE_LIST', 'LEVEL_FACT',
    'HEADING_JARGON', 'IDENT_IN_PROSE', 'GLOSSARY_DEF', 'GLOSSARY_IDENT',
    'CALLERS', 'TYPOGRAPHY', 'FRAGMENT_STOP', 'FOIL', 'UNUSED_TEXT',
    'LABEL_ECHO', 'WORDY_VARIABLE', 'DEIXIS', 'FOREIGN_LOGIC', 'INLINE_RENDER',
    'STE_LENGTH', 'STE_ING', 'STE_PARAGRAPH', 'BARE_VALUE', 'NON_ZERO',
    'LABEL_PAIR',
))

# The finding's own row carries its address, so the baseline key is that address
# rather than the line number the module warns against. A prose finding has no
# address — a `.ref` catalog line is not a directive — so it keys on its file and
# the term that matched, the same shape `validate_prose_names.py` uses and for
# the same reason: the phrase is the identity.
ROW_ADDRESS_RE = re.compile(r'^[ cbtwsgi*]?\$?([0-9A-Fa-f]{4})\b')
QUOTED_TERM_RE = re.compile(r"'([^']+)'")

# An instruction line: an optional control char, $ADDR, the instruction, then
# the comment column. Control char is one of c/b/t/w/s/g/i (block start),
# '*' (sub-entry point / jump target), or a space (continuation).
INSTR_RE = re.compile(r'^(?P<ctrl>[ cbtwsgi*])\$(?P<addr>[0-9A-Fa-f]{4}) (?P<body>.*)$')
# A block comment line (routine title / D / N) renders as a column-0 ';'.
BLOCK_COMMENT_RE = re.compile(r'^;\s?(?P<text>.*)$')
LABEL_RE = re.compile(r'^@label=(?P<label>\S+)\s*$')

# A hand-written label that names nothing — a generic stem plus a hex/numeric
# suffix, or a bare SkoolKit auto-label (L<HEX>). Descriptive labels
# (draw_display_a, door_a, parse_loop) do not match.
PLACEHOLDER_LABEL_RE = re.compile(
    r'(?i)^(l|loc|sub|loop|data|byte|word|var|tmp|temp|work|helper|routine|'
    r'unknown|todo|fixme|xxx|placeholder)[_]?[0-9a-f]{0,4}$'
)

# 'label (#R$addr)' and the reversed '#R$addr (label)' — flagged when the #R
# resolves to that same label, because #R renders as the label and the built
# page then reads "name (name)" either way.
# #R references in a comment, hex or decimal, normalized to a hex string.
COMMENT_REF_RE = re.compile(r'#R\$(?P<hex>[0-9A-Fa-f]{4})|#R(?P<dec>\d{4,5})')

SELFLINK_RE = re.compile(r'(?P<name>\w+)\s*\(#R\$(?P<addr>[0-9A-Fa-f]{4})\)')
SELFLINK_REV_RE = re.compile(r'#R\$(?P<addr>[0-9A-Fa-f]{4})\s*\((?P<name>\w+)\)')

# Investigation vocabulary that narrates the work instead of the game. The
# deliverable states game facts in timeless present; uncertainty is typed (a
# trailing '?', a TODO:), never a prose hedge or a confidence label. The
# emulator terms are absolute: a run supplies the author with evidence, so a
# claim that cites one is a claim the code has not been made to support.
DIARY_RE = re.compile(
    r'(?i)\b(unverified|provisional|not fully pinned|not yet traced|'
    r'code-traced|code-derived|this pass|honestly untraced|'
    r'emulator|emulation|fuse\s?x|play-observed|'
    r'(verified|confirmed|observed|measured|reproduced|replayed|watched)'
    r'\s+(live|in play))\b'
)

# Typed uncertainty, pointed at the exact claim: the sanctioned form, so it is
# not a DIARY hit — but it is counted and reported, because a marker in the text
# is unfinished work, and the coverage gauge holds a project short of the bar
# while one stands. A trailing '?' says the same thing and is not detectable: in
# a real .skool most comments ending in '?' are the condition a test reads
# ("Up held?"), so the Challenger counts those, not this script.
OPEN_MARKER_RE = re.compile(r'(?i)[*_]{0,2}\(unverified\)[*_]{0,2}|\bTODO:')

# The subset of DIARY hits that cite a run rather than hedge a claim; they get
# their own message, because the repair is different — re-derive, don't retype.
RUNTIME_HIT_RE = re.compile(
    r'(?i)emulator|emulation|fuse\s?x|play-observed|'
    r'(verified|confirmed|observed|measured|reproduced|replayed|watched)'
    r'\s+(live|in play)'
)

# The two structural laws over a '{ }' group's span. A comment covers one act,
# and the code says where an act ends: control leaving the span ends it, and a
# jump into the middle of the span means two paths share one sentence.
#
# An unconditional JP/JR — and `JP (HL)`, whose target no static read knows — is
# where an act ends, always. A *conditional* branch is not: an early-out abandons
# the act rather than beginning another, which is why "check X; exit if not" is
# one comment over both rows. A jump back to the span's own top is the span's own
# loop, and a loop is one act; that exemption is computed from the target, not
# assumed. A bare RET inside a group is RET_GROUP's finding, so it is not
# reported twice here.
UNCOND_JUMP_RE = re.compile(
    r'(?i)^(JP|JR)\s+(?!(?:NZ|Z|NC|C|PO|PE|P|M)\s*,)(?P<target>.+)$')
UNCOND_RETURN_RE = re.compile(r'(?i)^(RETI|RETN)\s*$')
# Every instruction that names a target: the edges of the control-flow graph the
# two laws read. CALL is an edge for GROUP_ENTRY (a called address is entered
# from outside) but never a cut for GROUP_SPLIT — a call comes back.
BRANCH_TARGET_RE = re.compile(r'(?i)^(JP|JR|DJNZ|CALL)\s+(?P<target>.+)$')
ADDRESS_OPERAND_RE = re.compile(r'\$(?P<hex>[0-9A-Fa-f]{4})\b|\b(?P<dec>\d{5})\b')

GROUP_SPLIT_DETAIL = (
    "a '{{ }}' comment group spans '{}' — control leaves the span here, so the "
    'rows below it are a second act carrying the first one\'s sentence. Close '
    'the group on this instruction and open the next one below it')
# One value, both bases, in one comment: `$8A (138)`. The base is a notation and
# the parenthetical is the same number read back, so the row says it twice — and
# the repair is never the other base. It is the intent, or the derived fact the
# row cannot show. Exact by construction: the two spellings are compared as
# values, so nothing here is a judgment call. Both orders count, and a value that
# is not its own conversion ("$FF (the sentinel)") is not a hit.
BASE_PAIR_RE = re.compile(
    r'\$(?P<hex>[0-9A-Fa-f]{1,4})\s*\(\s*(?P<dec>\d{1,5})\s*\)'
    r'|(?<![\w$])(?P<dec2>\d{1,5})\s*\(\s*\$(?P<hex2>[0-9A-Fa-f]{1,4})\s*\)')
BASE_ECHO_DETAIL = (
    "'{}' spells one value in both bases — the base is a notation, so the "
    'parenthetical is the operand read back. State the intent, or the derived '
    'fact the row cannot show')

GROUP_SKIP_DETAIL = (
    "a '{{ }}' comment group's own branch at ${} jumps forward over this row — "
    'on that path the rows below the branch do not run, so the sentence covers '
    'instructions the reader may never execute. Close the group at the branch')
GROUP_ENTRY_DETAIL = (
    "a '{{ }}' comment group is entered at this row from outside its span "
    '({}) — a reader arriving by that jump is handed a sentence about '
    'instructions that never ran. Close the group before this row')


def operand_target(operands, label_addrs):
    """Return the address a branch operand names, as uppercase hex, or None.

    Both notations count, and a label operand resolves through the .skool's own
    `@label` map, so a project built with labels is read the same as one built
    with addresses.
    """
    m = ADDRESS_OPERAND_RE.search(operands)
    if m:
        if m.group('hex'):
            return m.group('hex').upper()
        return f'{int(m.group("dec")):04X}'
    name = operands.split(',')[-1].strip()
    return label_addrs.get(name)


# A comment unit is one group or one commented row, and each one describes the
# rows it sits on. A unit that opens lowercase after a unit that ended open - on
# a comma, a conjunction, a preposition, an article or a relative pronoun - is
# not doing that: the two are one sentence cut in half, and the second half
# describes nothing on its own. "Leave it alone while the grow animation still
# runs," / "and while the shrink animation still runs." is the shape – the
# reader of the second block is handed a subordinate clause.
#
# Both halves of the test are needed. Opening lowercase is not enough on its own
# (a unit may start with a symbol or a lowercased identifier), and a unit ending
# without a full stop is a noun-phrase row, which takes none. A cross-reference
# between blocks is still allowed, written as a sentence of its own.
# A pitch in Hz is the sound described in the sound's own unit: the `#AUDIO` at
# the block plays it, so the figure adds nothing the reader is missing and binds
# the page to a tone formula that belongs once at the primitive. Being *derived*
# does not save it — that is the one conversion the derived-facts rule does not
# cover, and `references/comment-style.md` says so where the rule is stated.
#
# Two figures are not pitches and are excluded structurally: the CPU clock, which
# is written in MHz and so never matches, and the 50 Hz frame interrupt, which is
# the machine's tick and a sanctioned assumption to state. Digits are matched
# with their thousands separators so a sample rate reads as one number rather
# than lending its tail to a false hit.
PITCH_RE = re.compile(r'(?i)(?<![\w.])~?\s*(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?P<k>k?)Hz\b')
# Synthesis vocabulary: how the tone is *made*. Periods, cycles, T-states, and a
# formula computing a period from a counter.
# What a block of unused bytes owes: that it is unused, and any one thing about
# it worth knowing. Nothing else exists to say, so the ceiling is a real bound
# rather than a preference — which is why a cap is the right instrument here and
# the wrong one for prose in general (see references/prose-bar.md).
# A number the player cannot see does not belong in prose. Not a state index, not
# an object type, not a tile or slot code, not a bit position. Say what happens —
# "enters the death reaction", not "(state 2)"; "the rocket", not "type 17"; "a
# wall or border", not "tile codes $21-$44". The `#R` reference already written is
# the reader's way to the encoding, and repeating it beside the name is noise.
#
# Type codes, tile ranges and state numbers are one rule, because they share
# one shape: a number *labeled by an encoding noun*. A number the
# player meets carries a domain noun instead — "500 points", "3 lives", "250
# frames" — and is kept.
#
# Five exemptions, each structural rather than a judgment:
#
#   A table's key column. `{ $02 | silver key | … }` is the code's only home,
#   and striking it out leaves a row about no code. The row's other cells, and
#   prose in the same block, are not covered by this: "for character codes $20
#   to $5A" on the font block is a citation like any other, and the render below
#   it already shows the glyphs.
#
#   A variable's own data row. A `g` entry's row defines its encoding, so its
#   bit and its values are the definition, not a citation.
#
#   An `R` line. A routine's register contract is where it states the convention
#   its callers must honor – "I:DE pointer to the string (bit 7 set marks the
#   final character)". That is the implementer speaking, not a caller citing.
#
#   A platform encoding. ULA bit 4, port $FE, an opcode byte. Not this program's
#   to reassign, so no edit to the game can falsify the sentence.
#
#   A Z80 mnemonic. `BIT 7`, `SET 3`, `RES 0` are instructions that happen to
#   read like codes.
CODE_ECHO_NOUN = r'(?:state|type|class|slot|bit|code|codes|index|mode|phase|octant|headings?|ids?)'
CODE_ECHO_NUM = r'(?:\$[0-9A-Fa-f]{1,2}(?![0-9A-Fa-f])|\b\d{1,3}\b(?!°))'
CODE_ECHO_RE = re.compile(
    r'(?i)\b' + CODE_ECHO_NOUN + r'[-\s]+' + CODE_ECHO_NUM +
    r'|\b' + CODE_ECHO_NOUN + r's?\s+\$[0-9A-Fa-f]{2}\s*(?:to|[-\u2013])\s*\$?[0-9A-Fa-f]{2}\b')
CODE_ECHO_PLATFORM_RE = re.compile(r'(?i)\bULA\b|\bport \$?[0-9A-Fa-f]|\bopcode\b|\bROM\b')
CODE_ECHO_MNEMONIC_RE = re.compile(r'(?i)\b(BIT|SET|RES|RST|IM)\s+\d')
CODE_ECHO_DETAIL = (
    "cites a number the player cannot see ('{}'). Say what happens, not which "
    "code it is: 'starts to explode', not 'state 2'; 'the rocket', not "
    "'type 17'; 'a wall or border', not a tile range. The #R reference already "
    "there is the reader's way to the encoding. A number the player meets — a "
    "score, a count, a duration — stays"
)

# A block whose own title says it holds a picture, a glyph or a tune owes the
# reader the thing itself. The catalog page is an index — it shows everything at
# once — and an index is not where someone lands when they follow a link to one
# block. `#UDGARRAY` is one line and is derived from the same bytes the listing
# shows, so there is no cost to weigh against.
RENDER_MACRO_RE = re.compile(r'#(UDGARRAY|UDGTABLE|UDG|FONT|SCR|FRAMES|PLOT|COPY|AUDIO)')
# What the title has to name for the block to owe a render.
RENDERABLE_RE = re.compile(
    r'(?i)\b(sprite|bitmap|glyph|glyphs|font|wordmark|logo|tileset)\b')
# …and what disqualifies it: a block *about* sprites is not a block *of* them.
NOT_RENDERABLE_RE = re.compile(
    r'(?i)\b(state|flag|flags|counter|count|pool|buffer|pointer|pointers'
    r'|residual|selector|progress|codes|index)\b')
UNRENDERED_DETAIL = (
    "the title says this block holds something the reader can see or hear, and "
    "the block does not show it. Render it here, from these bytes — #UDGARRAY for "
    "a sprite or a glyph, #FONT for a character set, #AUDIO for an effect. The "
    "catalog page is an index of everything at once; it is not the block"
)

SYNTH_RE = re.compile(
    r'(?i)\bperiods?\b|\bcycles?\b|\bT-states?\b|\bhalf-cycle\b'
    r'|\b\d+\s*\*\s*[A-Za-z_#(]|#REG[a-z]+\s*='
)
SYNTH_DETAIL = (
    "describes how the tone is produced ('{}') beside the #AUDIO that plays it — "
    "the clip is the synthesis, so the words owe what the sound means in play, the "
    "event that fires it and the routine. The period formula is a mechanism and "
    "belongs once, at the tone primitive that implements it"
)

PITCH_DETAIL = (
    "states a pitch ('{}') — the #AUDIO plays the pitch, so the figure is the "
    'clip read back in numbers. Name what the sound means and what fires it; '
    'the tone formula belongs once at the primitive')


def pitch_echo(text):
    """Return the match of the pitch a text states, or None when it states none."""
    for m in PITCH_RE.finditer(text):
        if not m.group('k') and m.group('n').replace(',', '') in ('50', '48'):
            continue
        return m
    return None


# A record's layout has one home: the block whose bytes are the record, where
# `ctl-authoring.md` requires the stride, the fields and the sentinel. Everywhere
# else the offset is a citation — "the record whose +0/+1 word holds its X/Y" is
# the implementation quoted into a sentence about behavior, and it binds that
# sentence to a layout nothing re-derives. Name the thing instead: "the left
# door's position".
#
# Told apart by location, which the .skool carries: a comment inside a `c` entry
# is describing code, so an offset in it is a citation; a `D`/`N` on a data entry
# is the definition and keeps it.
#
# A geometric offset is not a record field, so a run of them ending in a unit
# ("vertical bounds of +10 and +1 pixels") is not a hit. The run is matched
# whole and its suffix tested, because testing one token at a time lets the
# first of a coordinated pair slip past the unit that governs both.
OFFSET_RUN_RE = re.compile(
    r'(?<![\w])\+\$?[0-9A-Fa-f]{1,2}'
    r'(?:\s*(?:and|,|to|/|or)\s*\+?\$?[0-9A-Fa-f]{1,2})*')
OFFSET_UNIT_RE = re.compile(
    r'(?i)^\s*(pixels?|px|degrees?|ms|Hz|frames?|lines?|scanlines?|cells?|rows?'
    r'|columns?)\b')
LAYOUT_ECHO_DETAIL = (
    "cites a record's field offset ('{}') in prose about code — the layout "
    'belongs at the record\'s own block, stated once; here, name what the field '
    'holds')


def layout_echo(text):
    """Return the offset a comment cites, or None when it cites none."""
    for m in OFFSET_RUN_RE.finditer(text):
        if not OFFSET_UNIT_RE.match(text[m.end():]):
            return m.group(0)
    return None


SPLICE_DETAIL = (
    'this comment finishes the sentence the previous unit left open ({!r}) — '
    'each comment describes its own rows, so a clause that only makes sense '
    'after the one above it belongs in that one, or in a sentence of its own '
    'that names what it refers to')


# A unit that opens on an identifier and an operator - `dx = ...`,
# `col = ...`, `lives := ...` - states its own equation. A noun-phrase row ends
# without a full stop, so the unit above it may end open without leaving a
# sentence for this one to finish.
EQUATION_OPEN_RE = re.compile(r"^[a-z_][\w.]*'?(?:\[[^\]]*\])?\s*(?:=|:=|\+=|-=|->)")


# What a cut sentence ends on: a comma, or a word that needs what follows it - a
# conjunction, a preposition, an article or a relative pronoun. A noun phrase
# ends on its noun and takes no full stop (TYPO-1), so a missing full stop is
# not a cut, and reading it as one pushes an author to stop every fragment.
SPLICE_OPEN_WORDS = frozenset((
    'and', 'or', 'but', 'nor', 'so', 'yet',
    'to', 'of', 'in', 'on', 'at', 'for', 'with', 'from', 'by', 'into', 'onto',
    'over', 'under', 'as', 'than', 'via', 'about', 'through', 'toward',
    'towards', 'between', 'against', 'without', 'within', 'across', 'past', 'per',
    'the', 'a', 'an',
    'that', 'which', 'while', 'when', 'where', 'who', 'whose', 'whom',
))


def unit_left_open(text):
    """True when `text` ends where a sentence cannot."""
    text = text.rstrip()
    if text.endswith(','):
        return True
    words = re.findall(r"[A-Za-z']+$", text)
    return bool(words) and words[0].lower() in SPLICE_OPEN_WORDS


def splice_units(units):
    """Report each unit that completes the previous unit's unfinished sentence.

    `units` is (lineno, line, text) in file order, one per comment unit.
    """
    hits = []
    for (_, _, prev), (lineno, line, text) in zip(units, units[1:]):
        prev = prev.rstrip()
        if not prev or not text or not text[0].islower():
            continue
        if EQUATION_OPEN_RE.match(text):
            continue
        if not unit_left_open(prev):
            continue
        hits.append((lineno, line, prev[-48:]))
    return hits


def base_echo(text):
    """Return the '$8A (138)' match when one comment spells a value twice."""
    for m in BASE_PAIR_RE.finditer(text):
        hexed = m.group('hex') or m.group('hex2')
        dec = m.group('dec') or m.group('dec2')
        if int(hexed, 16) == int(dec):
            return m
    return None


def group_split_row(instr, group_addrs, label_addrs):
    """True when this instruction ends the act its group is describing."""
    m = UNCOND_JUMP_RE.match(instr)
    if UNCOND_RETURN_RE.match(instr):
        return True
    if not m:
        return False
    target = operand_target(m.group('target'), label_addrs)
    # `JP (HL)` resolves to nothing, so it can never be the span's own back-edge.
    return target not in group_addrs


# A comment that sends the reader to a `.ref` index instead of carrying the fact
# (or its rendered macro) where the reader already is. Scoped to the .skool: a
# `.ref` file naming its siblings is the index doing its job.
REF_POINTER_RE = re.compile(r'(?i)\b(graphics|sound)\.ref\b')

# STAMP: a whole sentence appearing in more than one block comment. The unit is
# the sentence because that is what an author writes and copies, and the count is
# two because two is what "repeated" means — neither is tuned.
#
# Addresses are normalized so a sentence stamped with only the address swapped
# still matches. A "sentence" with no word in it is not one — splitting on `.`
# cuts `#R$9A10.` into a token and a stop — and SkoolKit's own generated lines
# are excluded by name, since the author did not write them and cannot unwrite
# them.
STAMP_GENERATED = ('used by the routine', 'used by the routines',
                   'this entry point is used by')
ADDR_TOKEN_RE = re.compile(r'(?i)(#r\$?[0-9a-f]{2,5}|\$[0-9a-f]{2,5}|\bl[0-9a-f]{4}\b)')
WORD_RE = re.compile(r'[a-z0-9§]+')
# Structurally repeated by nature, so excluded from STAMP: rendered-macro spans
# (every frame block carries the same #UDGTABLE shape) and register lines (a
# handler family legitimately shares its R-line template).
MACRO_SPAN_RE = re.compile(r'#(UDGTABLE|TABLE|LIST).*?(TABLE#|LIST#)', re.S)
MACRO_RE = re.compile(r'#\w+(\([^)]*\))*')
REGISTER_LINE_RE = re.compile(r'^\s*[IO]:')


def split_comment(body):
    """Split an instruction body into (instruction, comment).

    The comment starts at the first ' ;' that is not inside a quoted string, so
    a DEFM containing a semicolon is not mistaken for a comment boundary.
    """
    in_quote = False
    for i in range(len(body) - 1):
        c = body[i]
        if c == '"':
            in_quote = not in_quote
        elif c == ';' and not in_quote and body[i - 1] == ' ':
            return body[:i].rstrip(), body[i + 1:].strip()
    # No comment column at all (rare): treat the whole thing as instruction.
    return body.rstrip(), ''


def comment_body(comment):
    """Strip SkoolKit comment-group markers, returning the real comment text.

    A '{' opens and a '}' closes a comment that spans several instructions, so
    a line like 'RET ; }' carries no comment of its own — it only closes a group
    whose text lives on an earlier line. Such markers must not be read as content.
    """
    return comment.strip().lstrip('{').rstrip('}').strip()


def comment_restates(mnemonic, operands, comment):
    """High-precision check: the comment only narrates the instruction.

    Deliberately narrow — a false positive here blocks the build. Only the
    clearest restatements are caught; subtler ones are the Challenger's call.
    """
    c = comment.strip().rstrip('.').lower()
    if not c:
        return False
    ops = [o.strip() for o in operands.split(',')] if operands else []

    def reg(o):
        return re.escape(o.lower()) if o else ''

    m = mnemonic.upper()
    if m in ('INC', 'DEC') and ops:
        verb = 'increment' if m == 'INC' else 'decrement'
        if re.fullmatch(rf'{verb}s?\s+{reg(ops[0])}', c):
            return True
    if m in ('PUSH', 'POP') and ops:
        if re.fullmatch(rf'{m.lower()}(es|s)?\s+{reg(ops[0])}', c):
            return True
    if m in ('CALL', 'JP', 'JR') and ops:
        target = ops[-1]
        # Only when the target is a real label, not a raw L#### / $#### address.
        if target and not re.fullmatch(r'(L?[0-9A-Fa-f]{4}|\$[0-9A-Fa-f]{4})', target):
            verb = r'(call|calls|jump to|jumps to|go to|goes to)'
            if re.fullmatch(rf'{verb}\s+#?r?\$?{reg(target)}', c):
                return True
    if m == 'LD' and len(ops) == 2:
        dst, src = reg(ops[0]), reg(ops[1])
        patterns = [
            rf'load\s+{src}\s+into\s+{dst}',
            rf'loads?\s+{dst}\s+with\s+{src}',
            rf'store\s+{src}\s+(in|into|to)\s+{dst}',
            rf'set\s+{dst}\s+to\s+{src}',
            rf'copy\s+{src}\s+(to|into)\s+{dst}',
            rf'move\s+{src}\s+(to|into)\s+{dst}',
        ]
        if any(re.fullmatch(p, c) for p in patterns):
            return True
    return False


def operand_addresses(operands):
    """Return the addresses an instruction's operand field names, as uppercase hex.

    Both notations count: `$9C40` and the decimal `40000` SkoolKit renders
    without `--hex`. Decimals are read as addresses only inside the RAM range, so
    a `LD BC,$00A2` byte count is not mistaken for one.
    """
    addrs = {a.upper() for a in re.findall(r'\$([0-9A-Fa-f]{4})\b', operands)}
    addrs |= {f'{int(n):04X}' for n in re.findall(r'\b(\d{4,5})\b', operands)
              if 16384 <= int(n) <= 65535}
    return addrs


OPERAND_ECHO_DETAIL = ('the comment repeats its own operand — the row already '
                       'shows that value, and a label operand links it too; '
                       'say the action, drop the echo')

# The literal half of the same rule. An immediate is as visible on the row as a
# label is, so a comment repeating it says it twice just the same, and comparing
# the two is the same string test — nothing here needs judgment.
#
# What needs judgment is only which rows are ABOUT their byte, and those are
# separable structurally, without reading a word of the prose:
#
#   - a data directive is the encoding's own definition; the catalog row whose
#     job is to say that $89 means the shield stops saying anything without it;
#   - indexed addressing is a record walk, and a record's field offsets are the
#     interface a reader needs to use the code, not an internal name.
#
# An arithmetic or logic mnemonic against an immediate is not excluded, on the
# grounds that a classifier tests a value and a dispatcher names its case. That
# is the "it names a case, not a count" exclusion, and the principle rules it
# out — `head right (octant 2)` is `head right toward the player`, and
# `CP $8A ; clamp to a maximum of $8A` is the row read back.
#
# Its residue is named rather than excluded: where the value is part of the
# game's own name for the thing — `CP $02 ; is the current player Player 2` —
# the deletion test keeps the byte, and the check still reports it. Those rows
# are dismissed by reading, and that is the price of not keying an exclusion on
# wording.
#
# These two are the whole exclusion list, and nothing else needs one. Self-
# modifying code writing an opcode reads like a fourth — the byte IS the subject
# at `LD A,$C9` — but an opcode has a name, and naming it clears the row without
# losing anything: "write the RET opcode over the first byte". A row that looks
# unclearable is the rule asking for the name of the thing, not for an exemption.
IMMEDIATE_RE = re.compile(r'\$([0-9A-Fa-f]{2})(?![0-9A-Fa-f])')
# The same value written the other way round. "Copy 28 tile codes" beside
# `LD B,$1C` repeats the operand as surely as "$1C" would: the base is a
# notation, the echo is the value, and a reader who needs the count has it on
# the row. Excluded to the left: '$' (the hex form, already matched), '+'/'-'
# (a record offset – "+1" names a field, not a value), the en dash and minus
# sign that stand for the hyphen in typeset prose, and a word character.
# Excluded to the right: a word character, so "20th" is not a value, and a '.'
# followed by a digit, so "1.3 kHz" is one number rather than two. A '.' that
# ends a sentence is not part of the number, so "period: 50." still matches.
DECIMAL_RE = re.compile(r'(?<![\w$+.\-\u2013\u2212])(\d{1,5})(?![\w])(?!\.\d)')
INDEXED_RE = re.compile(r'\((I[XY])\s*[-+]')
DATA_DIRECTIVES = frozenset(('DEFB', 'DEFW', 'DEFM', 'DEFS'))


def operand_literals(mnemonic, operands):
    """Return the immediate values in `operands` whose echo is worth reporting.

    Empty for the two row shapes whose subject is the byte itself, so a catalog
    row and a record walk are never reported.
    """
    m = (mnemonic or '').upper()
    if m in DATA_DIRECTIVES:
        return set()
    if INDEXED_RE.search(operands):
        return set()
    return {int(v, 16) for v in IMMEDIATE_RE.findall(operands)}


LITERAL_TOKEN_RE = re.compile(
    r'\$([0-9A-Fa-f]{2})(?![0-9A-Fa-f])|(?<![\w$+.\-\u2013\u2212])(\d{1,5})(?![\w])(?!\.\d)')


def comment_literals(comment):
    """Return the values a comment spells out, in either base.

    Values, not spellings. The base is a notation and the echo is the value, so
    "28" beside `LD B,$1C` restates the row exactly as "$1C" would.

    A decimal that looks like a false positive is usually the rule biting. The
    repair for `LD D,$64  ; start period $64 (100)` is not "start period 100" —
    that is still the operand, in the other base. Nor is it the same number with
    a unit on the front: `y 38` beside `CP $26` is `$26` in decimal. The repair
    is what the row is *for*. See "A comment never echoes the implementation" in
    `references/comment-style.md`.
    """
    values = {int(v, 16) for v in IMMEDIATE_RE.findall(comment)}
    values.update(int(v) for v in DECIMAL_RE.findall(comment))
    return values


def echo_rows(rows):
    """Return the rows whose comment repeats something that same row's operand
    already carries — an address it #R-references, or an immediate it spells out.

    `rows` is a list of (lineno, line, comment, operand_addresses,
    operand_literals): one row for a lone instruction, and every row of a '{ }'
    comment group. The test is row-local because the defect is: the reader sees
    the value twice, side by side, on one line of the page.

    Both halves are one rule and one string test. The symbol half compares a
    resolved #R against the addresses in the operand field; the literal half
    compares a bare $XX against the immediates. Neither reads the prose.

    The two halves are scoped differently. Widening the **symbol** half to the
    whole group — every #R in the text against every operand under it — reports
    the prose doing its job: a group comment names the things its span touches,
    and "Seed #R$9A10 to 9" over a span ending in `LD (obj_count),A` is not an
    echo. So the symbol half stays row-local.

    The **literal** half is span-scoped, in close_group(): a byte quoted by the
    text is a byte the reader can see on a row below, and row-locality misses
    exactly that shape — a clamp naming its threshold one row above the `CP`
    that tests it. See span_echoes() for the one exemption that scoping
    needs.

    The cost of row-locality is that a group's text is soft-wrapped, so which row
    a reference falls on moves when the text is reflowed, and an echo can wrap
    off its operand's row and go unreported. It under-reports rather than
    over-reports, which is the side a gating check has to err on.
    """
    hits = []
    for lineno, line, comment, addrs, literals in rows:
        echoed = any(
            (cm.group('hex') or f"{int(cm.group('dec')):04X}").upper() in addrs
            for cm in COMMENT_REF_RE.finditer(comment)
        ) or bool(comment_literals(comment) & literals)
        if echoed:
            hits.append((lineno, line))
    return hits


# A group's text against the immediates its own rows carry. Row-locality alone
# misses the shape the rule exists for: the sentence opens on one row and the
# value it quotes sits two rows down, still inside the span the sentence claims.
#
# One context is exempt, and structurally: a value inside an arithmetic
# expression is a formula's constant, and the doctrine asks for the formula once
# at block level ("Screen attribute offset = (7 - row) * 8 + column"). Without
# that exemption the check fires on every stated formula.
#
# The residue is named rather than excluded: where the values *are* the subject —
# `AT 1,5`, the ROM coordinate — the deletion test keeps them and the check still
# reports. That is the same trade as the classifier rows, and the same answer:
# dismiss by reading, do not key an exclusion on wording.
SPAN_ARITH_RE = re.compile(r'(?i)[=*+/^]|>>|<<|\bAND\b|\bXOR\b|\bmod\b|-\s*\d')
SPAN_ECHO_DETAIL = ('the comment quotes {} — a value carried by an instruction '
                    'inside its own span. Say what the span is for; the row '
                    'below already shows the byte')


def span_echoes(text, values):
    """Return the literals a group's text quotes from its own span."""
    hits = set()
    for m in LITERAL_TOKEN_RE.finditer(text):
        value = int(m.group(1), 16) if m.group(1) else int(m.group(2))
        if value not in values:
            continue
        if SPAN_ARITH_RE.search(text[max(0, m.start() - 14):m.end() + 14]):
            continue
        hits.add(m.group(0))
    return hits


def normalize_tokens(text):
    """Lowercase words with every address-like token collapsed to '§', so a
    sentence stamped across blocks with only the address swapped still matches.
    Macro spans are dropped first — they repeat by nature, not by laziness."""
    text = MACRO_SPAN_RE.sub(' ', text)
    text = ADDR_TOKEN_RE.sub('§', text)
    text = MACRO_RE.sub(' ', text)
    return WORD_RE.findall(text.lower())


SENTENCE_RE = re.compile(r'[^.!?]+[.!?]')


def find_stamps(units):
    """Find sentences written into more than one block comment.

    units: list of (lineno, raw paragraph text).
    """
    seen = {}
    for lineno, text in units:
        for raw in SENTENCE_RE.findall(text):
            sentence = ' '.join(normalize_tokens(raw))
            if not sentence or any(w in sentence for w in STAMP_GENERATED):
                continue
            seen.setdefault(sentence, []).append(lineno)
    results = []
    for sentence, linenos in seen.items():
        places = sorted(set(linenos))
        if len(places) > 1:
            results.append((places[0], sentence, len(places)))
    return sorted(results)


OPEN_DETAIL = ("typed uncertainty ('{}') — the right way to leave a doubt in the "
               'text, and a claim that the work is unfinished: it needs an open '
               'dig-task, and no page carrying one is done')


def diary_detail(hit):
    """The DIARY message, sharpened for a runtime citation."""
    if RUNTIME_HIT_RE.fullmatch(hit):
        return (f"the deliverable rests on a run ('{hit}') — a run is how you "
                'got the evidence, not what supports the claim: re-derive the '
                'fact from the code and state it flat, or drop it')
    return (f"investigation vocabulary ('{hit}') — state the game fact flat; "
            "type real uncertainty at the claim (trailing '?', '(unverified)', "
            "TODO:) or file a dig-task")


# A data row is already clear about itself in two ways: its bytes are on the
# line, and its position in the table is its address. A comment that quotes one
# of its own bytes, or opens by naming the index the row sits at ("Code $12:",
# "Tile $21", "Class 7 (enemy):"), hands one of those back. The index belongs
# once in the block's own description, where the table says what it is indexed
# by; each row says what it holds. Read over whole '{ }' groups, because a
# sub-block comment spans every row of the sub-block.
DATA_DIRECTIVE_RE = re.compile(r'^(DEFB|DEFW|DEFM|DEFS)\b', re.I)
DATA_VALUE_RE = re.compile(r'\$([0-9A-Fa-f]{4}|[0-9A-Fa-f]{2})(?![0-9A-Fa-f])')
DATA_INDEX_RE = re.compile(
    r'^(?:Codes?|Tiles?|Entry|Entries|Index|Indices|Slots?|Class(?:es)?|Rows?'
    r'|Offsets?|Types?|Bytes?|Records?|Sub-frames?|Elements?|Items?|Cells?)'
    r' (?:\$[0-9A-Fa-f]+|\d+)(?:\s*-\s*(?:\$[0-9A-Fa-f]+|\d+))?\b')
DATA_ECHO_DETAIL = ("a data row's comment repeats {} – the row shows its bytes "
                    "and its address is its position. Say what the row holds; "
                    "state the index once, in the block description")


def data_echoes(lines):
    """Yield (lineno, line, what) for a data row whose comment echoes the row.

    `what` names the echoed index key or the quoted byte values. Only groups
    made entirely of data directives are read; an instruction's operand belongs
    to OPERAND_ECHO.
    """
    group, depth, block = None, 0, ''

    def finish(g):
        if not g or not g['data'] or not g['text'].strip():
            return None
        text = MACRO_RE.sub(' ', MACRO_SPAN_RE.sub(' ', g['text'])).strip()
        hits = []
        km = DATA_INDEX_RE.match(text)
        if km:
            hits.append(f'its index ("{km.group(0)}")')
        # A variable's row documents its encoding, and its byte is only the
        # value the snapshot caught, so a `g` row may name any of its values.
        quoted = [] if g['block'] == 'g' else sorted(
            {m.group(0).upper() for m in DATA_VALUE_RE.finditer(text)} & g['values'])
        if quoted:
            hits.append('its own bytes (' + ', '.join(quoted) + ')')
        return (g['lineno'], g['line'], ' and '.join(hits)) if hits else None

    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip('\n')
        im = INSTR_RE.match(line)
        if im:
            instr, comment = split_comment(im.group('body'))
            if im.group('ctrl') in 'bcgstuwi':
                block = im.group('ctrl')
            if depth == 0:
                hit = finish(group)
                if hit:
                    yield hit
                group = {'lineno': lineno, 'line': line.strip()[:120], 'text': '',
                         'values': set(), 'data': True, 'block': block}
            group['data'] = group['data'] and bool(DATA_DIRECTIVE_RE.match(instr.strip()))
            group['values'] |= {'$' + v.upper() for v in DATA_VALUE_RE.findall(instr)}
            group['text'] += ' ' + comment_body(comment)
            depth = max(0, depth + comment.count('{') - comment.count('}'))
        elif re.match(r'^\s+;', line) and group is not None:
            cont = line.split(';', 1)[1].strip()
            group['text'] += ' ' + comment_body(cont)
            depth = max(0, depth + cont.count('{') - cont.count('}'))
        else:
            hit = finish(group)
            if hit:
                yield hit
            group, depth = None, 0
    hit = finish(group)
    if hit:
        yield hit


def unrendered_elements(lines):
    """Yield (lineno, title) for data blocks that name a renderable element and
    show none. Decided by the block's own title, so the author declares what the
    bytes are and the check holds them to it."""
    index, total = 0, len(lines)
    while index < total:
        if not lines[index].startswith(';'):
            index += 1
            continue
        start, block = index, []
        while index < total and lines[index].startswith(';'):
            block.append(lines[index][1:].strip())
            index += 1
        entry = index
        while entry < total and (lines[entry].startswith('@') or not lines[entry].strip()):
            entry += 1
        if entry >= total or not re.match(r'^[bgtws][$][0-9A-Fa-f]{4}', lines[entry]):
            continue
        title = next((b for b in block if b and b != '.'), '')
        if not RENDERABLE_RE.search(title) or NOT_RENDERABLE_RE.search(title):
            continue
        gutter, row = [], entry
        while row < total and lines[row].strip() and not lines[row].startswith(';'):
            gutter.append(lines[row])
            row += 1
        if RENDER_MACRO_RE.search(' '.join(block + gutter)):
            continue
        yield start + 1, title[:120]


# --- Checks over prose units -------------------------------------------------
#
# Every text check below reads units from `prose_units.py` and declares the
# surfaces it applies to. A unit is a title, a paragraph, a row comment or a
# group, a register row, a table cell, a heading, a glossary title or body, in
# a `.skool`, a `.ref`, a `.ctl` or a Markdown page alike. A check therefore
# runs over every surface it names, in every file, with no second wiring for a
# second file type.
#
# Each DETAIL ends with the rulebook ID the check enforces (`references/rules.md`).

ALL_SURFACES = PROSE_SURFACES
NOT_REGISTER = PROSE_SURFACES - {'register'}
# The surfaces a reader meets as running prose, outside the listing's rows.
PAGE_PROSE = frozenset(('block', 'ref-para', 'term-body', 'list-item', 'table-cell'))
SKOOL_COMMENT_SURFACES = frozenset(('title', 'block', 'register', 'row', 'data-row'))

# The project's labels and entries, read from the `.skool`, so a `.ref` page's
# `#R` can be resolved to the entry it names.
ENV = {'labels': {}, 'entries': [], 'starts': []}


def set_env(labels, entries):
    ENV['labels'] = labels
    ENV['entries'] = sorted((int(e.addr, 16), e) for e in entries if e.addr)
    ENV['starts'] = [a for a, _ in ENV['entries']]


def entry_at(addr_hex):
    """The entry whose span holds `addr_hex`, or None."""
    try:
        addr = int(addr_hex, 16)
    except ValueError:
        return None
    index = bisect.bisect_right(ENV['starts'], addr) - 1
    return ENV['entries'][index][1] if index >= 0 else None


def entry_of(unit):
    return unit.ctx.get('entry')


def first_cell(unit):
    """A table row's first cell holds its key, which the code checks exempt."""
    return unit.surface == 'table-cell' and unit.ctx.get('col') == 0 \
        and unit.ctx.get('table') != 'UDGTABLE'


SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z#$"(])')


def sentences(text):
    """Yield (offset, sentence) for each sentence of `text`."""
    start = 0
    for m in SENTENCE_SPLIT_RE.finditer(text):
        yield start, text[start:m.start()]
        start = m.end()
    yield start, text[start:]


QUOTED_RE = re.compile(r'"[^"]*"|“[^”]*”')


def unquoted(text):
    """`text` with quoted game text blanked, offsets kept."""
    return QUOTED_RE.sub(lambda m: ' ' * len(m.group(0)), text)


def cite(detail, rule):
    return f'{detail} [{rule}]'


# BASE_ECHO, PITCH, OPEN, DIARY, REFPOINTER and SELFLINK read every unit.
def check_base_echo(unit):
    # A POKE page gives the decimal address the reader types and the hex that
    # finds it in the listing: two facts, not one value read back.
    if str((unit.ctx or {}).get('section', '')).startswith('Poke:'):
        return
    m = base_echo(unit.text)
    if m:
        yield m.start(), BASE_ECHO_DETAIL.format(m.group(0))


def check_pitch(unit):
    m = pitch_echo(unit.text)
    if m:
        yield m.start(), PITCH_DETAIL.format(m.group(0).strip())


def check_open(unit):
    for m in OPEN_MARKER_RE.finditer(unit.text):
        yield m.start(), OPEN_DETAIL.format(m.group(0))


def check_diary(unit):
    m = DIARY_RE.search(OPEN_MARKER_RE.sub(lambda x: ' ' * len(x.group(0)), unit.text))
    if m:
        yield m.start(), diary_detail(m.group(0))


def check_refpointer(unit):
    m = REF_POINTER_RE.search(unit.text)
    if m:
        yield m.start(), (f"points the reader at '{m.group(0)}' – render the resource "
                          'here (#UDG / #AUDIO); the .ref file is only the index')


def check_selflink(unit):
    for rx in (SELFLINK_RE, SELFLINK_REV_RE):
        m = rx.search(unit.text)
        if m and ENV['labels'].get(m.group('addr').upper()) == m.group('name'):
            name = m.group('name')
            yield m.start(), (f"'{name}' and '#R${m.group('addr')}' render as "
                              f'"{name} ({name})" – link the first mention only, drop '
                              'the parenthetical')
            return


def check_synth(unit):
    if not (unit.ctx.get('run_audio') or unit.ctx.get('section_audio')):
        return
    m = SYNTH_RE.search(unit.text)
    if m:
        yield m.start(), SYNTH_DETAIL.format(m.group(0).strip())


def check_code_echo(unit):
    """A number the player cannot see, cited beside a name (AUD-4).

    Read per sentence: the platform and mnemonic exemptions cover the sentence
    that names the port or the instruction, and no other.
    """
    if first_cell(unit):
        return
    e = entry_of(unit)
    # A variable's own row is where its encoding is defined.
    if unit.surface == 'data-row' and e is not None and e.type == 'g':
        return
    text = unit.text
    lead = len(text) - len(text.lstrip())
    for offset, sentence in sentences(text):
        if CODE_ECHO_PLATFORM_RE.search(sentence) or CODE_ECHO_MNEMONIC_RE.search(sentence):
            continue
        m = CODE_ECHO_RE.search(sentence)
        if not m:
            continue
        # A data row that opens on its index is DATA_ECHO's one finding.
        if unit.surface == 'data-row' and offset + m.start() == lead \
                and DATA_INDEX_RE.match(text.strip()):
            continue
        yield offset + m.start(), cite(CODE_ECHO_DETAIL.format(m.group(0)), 'AUD-4')


# CODE_PAREN. A name, then its code in parentheses, in any shape the code
# takes: one code, a range, a list, or a code behind an encoding noun.
CODE_PAREN_RE = re.compile(
    r'(?i)\b([a-z][\w/-]*)\s\((?:(?:tile|slot|type|code|state|class|index)s?\s+)?'
    r'\$[0-9a-f]{2,4}(?![0-9a-f])[^()]*\)')
CODE_PAREN_NOUN_RE = re.compile(
    r'\([^()]*\b(?:tile|slot|type|code|state|class)s?\s+\$[0-9A-Fa-f]{2}(?![0-9A-Fa-f])[^()]*\)')
CODE_PAREN_DETAIL = (
    "names a thing and then its code in parentheses ('{}') – the code is "
    "implementation the reader cannot see, and the name already says which "
    "thing is meant; drop the code")


def check_code_paren(unit):
    if first_cell(unit):
        return
    for m in CODE_PAREN_RE.finditer(unit.text):
        if m.group(1).upper() in ('OUT', 'IN'):
            continue
        yield m.start(), cite(CODE_PAREN_DETAIL.format(m.group(0)), 'AUD-4')
        return
    m = CODE_PAREN_NOUN_RE.search(unit.text)
    if m:
        yield m.start(), cite(CODE_PAREN_DETAIL.format(m.group(0)), 'AUD-4')


# HOME-3. Four or more numbers in a run, or three after "level(s)", is a list of
# values the data already holds. Three or more codes in a run is the same list
# in hex.
NUMBER_SEP = r'(?:\s*,\s*(?:(?:and|or)\s+)?|\s+(?:and|or)\s+)'
NUMBER_LIST_RE = re.compile(
    r'(?<![\w$.#,+\-–])\d{1,3}(?:' + NUMBER_SEP + r'\d{1,3}(?![\d.]\d)){3,}(?![\w,]|\.\d)'
    r'|(?i:\blevels?\s+)\d{1,3}(?:' + NUMBER_SEP + r'\d{1,3}){2,}(?![\w,])')
CODE_ITEM = r'\$[0-9A-Fa-f]{2}(?![0-9A-Fa-f])(?:\s*[–-]\s*\$[0-9A-Fa-f]{2}(?![0-9A-Fa-f]))?'
CODE_LIST_RE = re.compile(
    CODE_ITEM + r'(?:\s*(?:,|\bor\b|\band\b)?\s*(?:(?:and|or)\s+)?' + CODE_ITEM + r'){2,}')
NUMBER_LIST_DETAIL = (
    "lists numbers ('{}') – a list of the levels, slots or values that hold "
    "something restates the game's data, which the data tables show")
CODE_LIST_DETAIL = (
    "lists codes ('{}') – a run of codes restates the game's data; name what "
    "the codes have in common, or leave the list to the table that holds them")


def check_number_list(unit):
    if first_cell(unit):
        return
    for m in NUMBER_LIST_RE.finditer(unit.text):
        yield m.start(), cite(NUMBER_LIST_DETAIL.format(m.group(0)), 'HOME-3')


def check_code_list(unit):
    if first_cell(unit):
        return
    for m in CODE_LIST_RE.finditer(unit.text):
        yield m.start(), cite(CODE_LIST_DETAIL.format(m.group(0)), 'HOME-3')


LEVEL_FACT_RE = re.compile(
    r'(?i)\blevels?\s+\d+\s+(?:has|have|holds?|carries|carry|contains?|places?|uses?)\b'
    r'|\bno levels?\b'
    r'|\b(?:every|each) level\b[^.]*\b\d+\s+(?:slots?|cells?|tiles?|times)\b'
    r'|\b\d+\s+(?:slots?|cells?|levels?)\s+(?:hold|carry|use|place|have|contain)\b'
    r'|\b\w+ of the \d+ (?:\w+ )?(?:levels?|scripts?)\b')
LEVEL_FACT_DETAIL = (
    "states a fact about the level data ('{}') – which levels hold what, and "
    "how many slots carry a value, is the data itself; the data tables show it")
DATA_ENTRY_TYPES = frozenset('bgstuw')


def check_level_fact(unit):
    e = entry_of(unit)
    if e is not None and e.type not in DATA_ENTRY_TYPES:
        return
    m = LEVEL_FACT_RE.search(unit.text)
    if m:
        yield m.start(), cite(LEVEL_FACT_DETAIL.format(m.group(0)), 'HOME-3')


# HEAD-2. The storage vocabulary reads page headings only: an entry title in the
# listing is the listing's own word for its bytes ("Tile attribute table"). A
# count is wrong on any heading or title, the listing's included.
HEADING_JARGON_RE = re.compile(
    r'(?i)\b(records?|tables?|bytes?|pointers?|buffers?|offsets?)\b'
    r'|\b\d+\s+[a-z]+s\b')
HEADING_COUNT_RE = re.compile(r'(?i)^(?:the\s+)?\d+\s+[a-z-]+s\b')
HEADING_JARGON_DETAIL = (
    "heading '{}' uses the program's storage vocabulary or counts its "
    "contents – name what the reader is browsing, in the game's terms")


def check_heading_jargon(unit):
    text = unit.text.strip()
    if unit.surface == 'ref-heading':
        hit = HEADING_JARGON_RE.search(text)
    else:
        hit = HEADING_COUNT_RE.search(text)
    if hit:
        yield 0, cite(HEADING_JARGON_DETAIL.format(text), 'HEAD-2')


# NAME-6. An equate or constant name in prose: what a reader meets as a word is
# the thing's name, never the identifier the assembler reads.
IDENT_RE = re.compile(r'(?<![\w$#])[A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9](?![\w])')
IDENT_DETAIL = (
    "names a constant by its identifier ('{}') – a reader meets the thing, not "
    "the name the assembler reads; say what it is in words")


def check_ident(unit):
    m = IDENT_RE.search(unquoted(unit.text))
    if m:
        yield m.start(), cite(IDENT_DETAIL.format(m.group(0)), 'NAME-6')


# DEF-2 to DEF-4. A glossary definition says what the thing is. Progress, the
# logic that changes the value, and the code that uses it are not that.
GLOSSARY_PROGRESS_RE = re.compile(r'(?i)\bhow far\b|\bhas got\b|\bso far\b|\bhas reached\b')
GLOSSARY_LOGIC_RE = re.compile(
    r'(?i)\b(?:wraps?|wrapped|resets?|increments?|incremented|decrements?|decremented'
    r'|rolls? over)\b'
    r'|\b(?:after|when|once|until|whenever|each time)\b[^.]*\b(?:advances?|repeats?'
    r'|restarts?|clears?|counts? (?:up|down))\b')
GLOSSARY_USE_RE = re.compile(r'#R\$[0-9A-Fa-f]{4}|(?i:\broutines?\b)')
GLOSSARY_DEF_DETAIL = (
    "the definition describes {} ('{}') – a glossary entry says what the thing "
    "is, true before play starts; how it changes and what uses it belong to "
    "the listing")


def check_glossary_def(unit):
    for rx, what, rule in ((GLOSSARY_PROGRESS_RE, "the player's progress", 'DEF-4'),
                           (GLOSSARY_LOGIC_RE, 'logic that changes the value', 'DEF-2'),
                           (GLOSSARY_USE_RE, 'the code that uses it', 'DEF-3')):
        m = rx.search(unit.text)
        if m:
            yield m.start(), cite(GLOSSARY_DEF_DETAIL.format(what, m.group(0)), rule)
            return


GLOSSARY_IDENT_RE = re.compile(
    r'(?i)^(?:constants?|variables?|labels?|equates?|identifiers?|symbols?)$')
GLOSSARY_IDENT_DETAIL = (
    "glossary term '{}' is a constant or a category of program symbol – the "
    "glossary holds the game's and the project's own terms, and an identifier "
    "is named in words where it is used")


def check_glossary_ident(unit):
    text = unit.text.strip()
    if GLOSSARY_IDENT_RE.match(text) or IDENT_RE.search(text):
        yield 0, cite(GLOSSARY_IDENT_DETAIL.format(text), 'DEF-6')


# HOME-4. The actor must be a routine reference, so "cleared by a hit" is not
# a hit. An `s` entry may name what fills it, so a writer verb there is exempt.
CALLER_READ_VERBS = r'read|used|called|dispatched|polled|tested|consulted|checked'
CALLER_WRITE_VERBS = (r'written|rewritten|set|cleared|updated|armed|seeded|incremented'
                      r'|decremented|bumped|reset|zeroed|stored')
CALLERS_RE = re.compile(
    r'(?i)\b(?P<verb>' + CALLER_READ_VERBS + r'|' + CALLER_WRITE_VERBS + r')'
    r'\s+(?:only\s+|both\s+|first\s+)?by\s+(?:#R\$|the routines?\b)'
    r'|\b(?:readers?|writers?|callers?|used by)\s*:|\bEREF\b')
CALLER_WRITE_RE = re.compile(r'(?i)^(?:' + CALLER_WRITE_VERBS + r')$')
CALLERS_DETAIL = (
    "lists the code that reads, writes or calls the thing ('{}') – the "
    "listing's links already carry who touches what; say what the thing is")


def check_callers(unit):
    e = entry_of(unit)
    for m in CALLERS_RE.finditer(unit.text):
        verb = m.group('verb') or ''
        if e is not None and e.type == 's' and CALLER_WRITE_RE.match(verb):
            continue
        yield m.start(), cite(CALLERS_DETAIL.format(m.group(0)), 'HOME-4')
        return


# TYPO-2. ASCII stand-ins for the typographic characters. Quoted game text and
# macro parameters keep their bytes: the parameters are scrubbed from the unit,
# and quoted text is blanked before matching.
TYPO_RULES = (
    ('a dimension', '×', re.compile(r'(?<![\w$#.])(?!0x)\d+\s?[xX]\s?\d+(?![\w])')),
    ('an arrow', '→', re.compile(r'(?<![-<!])->|<-(?!-)|=>')),
    ('a comparison', '≥ ≤ ≠', re.compile(r'(?<![<>=!])(?:>=|<=|!=)(?!=)')),
    ('an angle', '°', re.compile(r'(?i)\b\d+\s*(?:deg|degrees?)\b')),
    ('a product', '×', re.compile(r'(?<=[\w)])\s?\*\s?(?=[\w(])')),
    ('a range', 'an en dash',
     re.compile(r'(?<![\w$#\-–])(?:\$[0-9A-Fa-f]{2,4}|\d+)(?:-|\.\.)'
                r'(?:\$[0-9A-Fa-f]{2,4}|\d+)(?![\w\-])')),
    ('a minus sign', '−', re.compile(r'(?<![\w$#\-–+])-(?=\d)')),
    ('a dash or a minus', 'a spaced en dash, or − for minus',
     re.compile(r'(?<=[\w).])\s-\s(?=[\w(#$])')),
)
FLAT_RE = re.compile(r'(?<![\w$#])[A-G]b(?:\d|(?![\w]))')
NOTE_CONTEXT_RE = re.compile(r'(?i)\b(?:note|notes|tune|pitch|pitches|melody|scale)\b')
TYPOGRAPHY_DETAIL = (
    "writes {} in ASCII ('{}') – prose uses {}; quoted game text and macro "
    "parameters keep their bytes")


def note_context(unit):
    e = entry_of(unit)
    if unit.ctx.get('run_audio') or unit.ctx.get('section_audio'):
        return True
    if e is not None and (e.audio or NOTE_CONTEXT_RE.search(e.title or '')):
        return True
    return bool(NOTE_CONTEXT_RE.search(unit.ctx.get('section') or ''))


def check_typography(unit):
    e = entry_of(unit)
    if e is not None and e.type == 't':
        return
    text = unquoted(unit.text)
    for what, write, rx in TYPO_RULES:
        m = rx.search(text)
        if m:
            yield m.start(), cite(TYPOGRAPHY_DETAIL.format(what, m.group(0).strip(), write),
                                  'TYPO-2')
            return
    if note_context(unit):
        m = FLAT_RE.search(text)
        if m:
            yield m.start(), cite(TYPOGRAPHY_DETAIL.format('a flat', m.group(0), '♭'),
                                  'TYPO-2')


# TYPO-1. A full stop ends a sentence, and a noun phrase takes none. A unit is a
# sentence when it holds a verb, and the test for one is broad on purpose: an
# imperative opening a clause, a word from a long list of verbs, or any word after
# the first ending in -s, -es, -ed or -ing. A plural noun or a participle passes
# the last test too, so the check reports only units with no verb-shaped word in
# them. Code rows are not read: they are imperatives.
IMPERATIVES = frozenset('''
    set clear add skip return stop step point copy draw mark keep take leave read
    write load store test wait move fill pick hold count start award arm blank
    blip bump call check compare compute convert decrement divide double drop
    enter erase exit find fire flash flip get give halve increment invert jump
    loop lower make mask merge multiply negate open paint play poll pop print
    push put raise redraw render reset restore resume rotate run save scan seed
    select shift show spawn swap toggle turn update use walk wipe zero apply
    advance build choose close convert emit follow kill sound beep send seed
    see note stash recover align end begin go try let pass repeat continue
    finish carry flag hide reveal score subtract scroll wrap clamp fetch
'''.split())
# Past forms that name things in a listing (a shot, a bit, a set, a hit, the
# left column, a read pointer) are left out, so a row naming one is still read.
FINITE_VERBS = frozenset('''
    is are was were be been being am has have had does do did can cannot could
    will would may might must shall should isn't aren't wasn't weren't doesn't
    don't didn't can't won't hasn't haven't
    holds draws stands takes runs moves sets clears goes comes keeps makes gives
    leaves marks points reads writes stores starts stops ends begins counts
    returns plays shows means falls rises turns becomes covers lies sits carries
    contains follows repeats spawns appears hides bounces breaks hits needs uses
    lets gets puts says wins loses dies kills scores lands passes stays waits
    fires flashes selects picks tests adds skips steps lasts reaches equals
    matches spans shrinks grows slows speeds sticks drops opens closes wraps
    flips swaps scrolls clamps fills wipes blanks arms awards
    went made took gave kept held drew ran put fell rose began begun drawn
    taken given shown known seen done gone became come brought caught thought
    found lost won sent spent built meant led struck stuck spun spread let got
    sat laid paid said told sold slid hid heard
'''.split())
# A word after the first that ends this way may be a verb, so the unit may be a
# sentence. Short words (its, this, his, bus), -ss and -us words (class, bonus)
# and -eed words (speed, seed) are not counted.
VERB_ENDING_RE = re.compile(r'(?i)^[a-z][a-z\'’-]*(?:(?<![su])s|es|(?<!e)ed|ing)$')
NOT_VERB_ENDINGS = frozenset('''
    its this his hers ours yours theirs thus plus less unless across always
    perhaps nothing something anything everything
'''.split())
# A first word ending in -s is a verb when one of these follows it. `of` and
# `per` are left out: "Tiles per level" and "Records of the player" are nouns.
VERB_OBJECT_WORDS = frozenset('''
    the a an its their his her every each all both this that these those one
    two any no on to in at into from with by for over off up down out through
    toward towards back away
'''.split())
# A word after one of these is in that preposition's object.
PREPOSITIONS = frozenset('''
    of per for in on at with by from to into onto over under between across
    through toward towards within without
'''.split())
# Bare verbs a plural subject takes that the imperative list does not hold.
BARE_VERBS = frozenset('''
    run hit fall rise lie sit stand bounce break die win lose land stay last
    reach equal match span shrink grow slow speed stick come go appear hide
    sound count hold
'''.split())
WORD_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
FRAGMENT_DETAIL = (
    "ends a noun phrase with a full stop ('{}') – a full stop ends a sentence. "
    "A row, caption, title or cell that names a thing takes none")


def suffix_verb(words):
    """Return whether a clause's words hold a verb by its ending, after a subject.

    A word after a preposition belongs to that preposition's object, so "grid of
    tile slot codes" holds a noun where "the lift rises" holds a verb.
    """
    for position, word in enumerate(words):
        lower = word.lower()
        if lower in PREPOSITIONS:
            return False
        if position and len(lower) > 3 and lower not in NOT_VERB_ENDINGS \
                and VERB_ENDING_RE.match(lower):
            return True
    return False


def has_verb(text):
    """Return whether a unit holds a verb-shaped word, by the broad test above."""
    for clause in re.split(r'[:;,]', text):
        first = WORD_TOKEN_RE.search(clause)
        if first and first.group(0).lower() in IMPERATIVES:
            return True
    words = WORD_TOKEN_RE.findall(text)
    if any(w.lower() in FINITE_VERBS for w in words):
        return True
    for clause in re.split(r'[:;,]', text):
        if suffix_verb(WORD_TOKEN_RE.findall(clause)):
            return True
    # A clause's first word is a verb when the subject is left out ("Paints the
    # wall", "Advances HL to the next row", "Homes on the player"): an -s or -es
    # word followed by an object or a preposition.
    for clause in re.split(r'[:;,]', text):
        pair = WORD_TOKEN_RE.findall(clause)[:2]
        if len(pair) < 2:
            continue
        first, following = pair[0].lower(), pair[1]
        if (len(first) > 3 and first not in NOT_VERB_ENDINGS and first.endswith('s')
                and VERB_ENDING_RE.match(first)
                and (following.lower() in VERB_OBJECT_WORDS
                     or re.fullmatch(r'[A-Z]{1,3}', following))):
            return True
    for word, following in zip(words, words[1:]):
        # A plural subject and a bare verb: "Records run in level order".
        lower = word.lower()
        if (len(lower) > 3 and lower not in NOT_VERB_ENDINGS and VERB_ENDING_RE.match(lower)
                and lower.endswith('s') and following.lower() in IMPERATIVES | BARE_VERBS):
            return True
    return False


def check_fragment_stop(unit):
    text = unit.text.strip()
    if not text.endswith('.') or text.endswith('..') or text.endswith('…'):
        return
    tail = ' '.join(text.split()[-6:])
    if unit.surface == 'title':
        yield len(unit.text.rstrip()) - 1, cite(FRAGMENT_DETAIL.format(tail), 'TYPO-1')
        return
    if unit.ctx.get('header'):
        return
    if len(list(sentences(text))) > 1:
        return
    if not WORD_TOKEN_RE.search(text) or has_verb(text):
        return
    yield len(unit.text.rstrip()) - 1, cite(FRAGMENT_DETAIL.format(tail), 'TYPO-1')


# AUD-3. An argument against a reading nobody offered.
FOIL_RE = re.compile(
    r'(?i)\b(?:is|are|was|were)\s+not\s+(?:a|an|the)\b'
    r'|,\s+not\s+(?:a|an|the|by|as|in|on|to|at|for|from|with)\b'
    r'|\brather than\b|\binstead of\b|\bnot\s+\w+\s*,\s*but\b'
    r'|\bbelongs? to [^,.]+, not\b')
FOIL_DETAIL = (
    "argues against a reading nobody offered ('{}') – state what the thing is "
    "or does; a contrast earns its place only when the other side is on the page")


DEFECT_SECTION_RE = re.compile(r'(?i)bug|defect')
DEFECT_LINK_RE = re.compile(r'(?i)#LINK[(:][^)]*(?:bug|defect)')


def check_foil(unit):
    """AUD-3, minus a defect statement, which names the faulty behavior beside
    the intended one: a `.ref` defects or bugs section, or a unit marked BUG or
    linking to the defects page."""
    text = unit.text.strip()
    if unit.surface in ('row', 'data-row') and text.endswith('?'):
        return
    if DEFECT_SECTION_RE.search(unit.ctx.get('section') or '') \
            or DEFECT_LINK_RE.search(unit.raw) or re.search(r'\bBUG\b', unit.text):
        return
    m = FOIL_RE.search(unit.text)
    if m:
        yield m.start(), cite(FOIL_DETAIL.format(m.group(0)), 'AUD-3')


# HOME-2 and HOME-8. "Below" is a position, and a reader who arrived by a link
# has no position to read it from.
DEIXIS_RE = re.compile(
    r'(?i)\b(?:the|these|those)\s+(?:routines?|entries|entry|blocks?|tables?)\s+'
    r'(?:below|above)\b')
DEIXIS_DETAIL = (
    "points at its neighbors by position ('{}') – a reader who arrived by a link "
    "has no 'below'; name the entry by its link, or describe only this one")


def check_deixis(unit):
    m = DEIXIS_RE.search(unit.text)
    if m:
        yield m.start(), cite(DEIXIS_DETAIL.format(m.group(0)), 'HOME-2')


FOREIGN_VERBS_RE = re.compile(
    r'(?i)\b(?:derives?|computes?|finds?|checks?|tests?|compares?|loops?|walks?'
    r'|adds?|subtracts?|shifts?|masks?|branches?|packs?|reaches?|calculates?)\b')
FOREIGN_LOGIC_DETAIL = (
    "describes another routine's logic ('{}') on a data entry's page – the "
    "page describes its own bytes; at most it names the routine that fills them")


def check_foreign_logic(unit):
    e = entry_of(unit)
    if e is None or e.type not in ('b', 'g', 's', 'w', 't', 'u'):
        return
    for offset, sentence in sentences(unit.text):
        verb = FOREIGN_VERBS_RE.search(sentence)
        if not verb:
            continue
        for ref in re.finditer(r'#R\$([0-9A-Fa-f]{4})', sentence):
            target = entry_at(ref.group(1))
            if target is not None and target.type == 'c':
                quote = sentence[min(ref.start(), verb.start()):
                                 max(ref.end(), verb.end())]
                yield offset + min(ref.start(), verb.start()), cite(
                    FOREIGN_LOGIC_DETAIL.format(quote), 'HOME-2')
                return


# VIS-1. A render inside a sentence draws inside the sentence's box.
INLINE_RENDER_DETAIL = (
    "draws a render inside a line of text ('{}') – a render sits in a block of "
    "its own (#UDGTABLE in an N note or a page block), never in a sentence or "
    "a row comment")


def check_inline_render(unit):
    if not unit.render or unit.ctx.get('table') == 'UDGTABLE' or unit.ctx.get('markup'):
        return
    words = re.findall(r'[A-Za-z]{2,}', unit.text)
    if len(words) >= 3:
        yield 0, cite(INLINE_RENDER_DETAIL.format(' '.join(words[:6])), 'VIS-1')


# ROW-1 on a `.ref` table: a cell other than the key column that opens on an
# index ("Code $12:") repeats the key the row already shows.
def check_cell_index(unit):
    if first_cell(unit) or unit.ctx.get('header'):
        return
    text = unit.text.strip()
    m = DATA_INDEX_RE.match(text)
    if m:
        yield unit.text.find(text), DATA_ECHO_DETAIL.format(f'its index ("{m.group(0)}")')


# HOME-5. A row whose comment is only its operand label's words says what the
# link beside it already says.
LABEL_DROP_WORDS = frozenset(('update', 'anim', 'src', 'handler', 'h'))
LABEL_OPERAND_RE = re.compile(r'(?i)^(DEFW|JP|CALL|JR|DJNZ|LD)\b\s*(.*)$')
LABEL_ECHO_DETAIL = (
    "the comment is the label's own words ('{}') – the operand's link already "
    "names the target; say what this row does with it")


def operand_labels(instr):
    m = LABEL_OPERAND_RE.match(instr.strip())
    if not m:
        return []
    found = []
    for token in re.split(r'[,\s()]+', m.group(2)):
        if not token:
            continue
        if token.startswith('$') and re.fullmatch(r'\$[0-9A-Fa-f]{4}', token):
            label = ENV['labels'].get(token[1:].upper())
        elif re.fullmatch(r'\d{4,5}', token):
            label = ENV['labels'].get(f'{int(token):04X}')
        else:
            label = token if token in ENV['labels'].values() else None
        if label:
            found.append(label)
    return found


def check_label_echo(unit):
    instrs = unit.ctx.get('instrs') or []
    if len(instrs) != 1:
        return
    labels = operand_labels(instrs[0])
    if not labels:
        return
    label_words = set()
    for label in labels:
        label_words |= {w for w in re.split(r'[_\-]+', label.lower())
                        if w and not w.isdigit() and w not in LABEL_DROP_WORDS}
    comment = re.sub(r'#R\$[0-9A-Fa-f]{4}', ' ', unit.text.lower())
    words = {w for w in re.findall(r'[a-z]+', comment) if w not in ('a', 'an', 'the')}
    if words and words <= label_words:
        yield 0, cite(LABEL_ECHO_DETAIL.format(unit.text.strip()), 'HOME-5')


# STE-1, STE-4 and STE-6. The writing rules of ASD-STE100, Simplified
# Technical English, that a pattern can decide. Quoted game text is blanked
# first: the game's own words keep their length and their forms.
STE_MAX_WORDS = 25
STE_MAX_SENTENCES = 6
STE_WORD_RE = re.compile(r"[A-Za-z0-9$#][A-Za-z0-9$#'’-]*")
STE_ING_RE = re.compile(r"\b([A-Za-z]{2,}ing)\b")
# Words ending in -ing that are no form of a verb.
STE_NOT_ING = frozenset((
    'thing', 'nothing', 'something', 'anything', 'everything', 'string',
    'during', 'king', 'ring', 'spring', 'wing', 'ceiling', 'morning', 'evening',
    'sibling', 'sting', 'bring',
    # The noun for a disassembly's assembly text, not a form of a verb.
    'listing'))
STE_LENGTH_DETAIL = (
    "a sentence of {} words ('{}') – a sentence holds at most "
    f"{STE_MAX_WORDS} words; split it at its ideas")
STE_ING_DETAIL = (
    "'{}' is an -ing form – write the verb in a simple tense, or the noun it "
    "names. A word of a label is a technical name and may keep its -ing")
STE_PARAGRAPH_DETAIL = (
    "a paragraph of {} sentences – a paragraph holds at most "
    f"{STE_MAX_SENTENCES} sentences; give each topic its own")


# PROSE-9. A value and its meaning are joined by a word. "0 left door, 1 right
# door" runs each number into its meaning, and so does a lone "Phase: 0 idle";
# "0 for the left door, 1 for the right door" does not.
BARE_GLUE = (r'(?:if|when|for|to|while|otherwise|or|and|bytes?|bits?|px|pixels?|'
             r'frames?|game|times|of|per|cells?|rows?|columns?|hits?|points?|steps?|'
             r'words?|lives|seconds?|degrees?|more|less|as|at|is|means?|by|in|x|'
             r'characters?|tiles?|slots?|entries|entry|levels?|notes?|cycles?|'
             r'digits?|records?|sprites?|codes?|values?|'
             r'kinds?|types?|stages?|ticks?|units?|sweeps?|laps?|ms|set|clear|'
             r'glyph|bitmaps?|above|below|belong)')
BARE_ITEM = (rf'(?:\$[0-9A-F]{{2,4}}|\b\d+)\s+(?!{BARE_GLUE}\b)(?!on\s+[a-z])[a-z]')
BARE_VALUE_RE = re.compile(rf'{BARE_ITEM}[^,;.()]*,\s+{BARE_ITEM}'
                           rf'|(?:^|[:,;]\s+)(?:\$[0-9A-F]{{2,4}}|\b\d+)\s+(?!{BARE_GLUE}\b)'
                           rf'[a-z][a-z-]*(?=\s*(?:$|[,;]|\bto\b))')
BARE_VALUE_DETAIL = (
    "values run into their meanings ('{}') – join each value to its meaning "
    "with a word: '0 for the left door, 1 for the right door', '1 if the key "
    "is held'")


def check_bare_value(unit):
    m = BARE_VALUE_RE.search(unquoted(unit.text))
    if m:
        yield m.start(), cite(BARE_VALUE_DETAIL.format(m.group(0)[:40]), 'PROSE-9')


# DEF-1. A definition states the values it holds. "Non-zero while X" names no
# value: a flag says what it holds when set, and a counter its range.
NON_ZERO_RE = re.compile(r'(?i)\bnon-?zero\b')
NON_ZERO_DETAIL = (
    "'{}' names no value – say what the variable holds: '1 while the player "
    "is stunned, 0 otherwise', or a counter's range and what 0 means")


def check_non_zero(unit):
    e = entry_of(unit)
    if unit.surface == 'block' and (e is None or e.type not in ('g', 'b', 's')):
        return
    m = NON_ZERO_RE.search(unquoted(unit.text))
    if m:
        yield m.start(), cite(NON_ZERO_DETAIL.format(m.group(0)), 'DEF-1')


TERM_TITLE_RE = re.compile(r'^\[Term:[^:\]]*:([^\]]*)\]', re.M)


def read_term_words(paths):
    """The words of every glossary term title among `paths`: technical names."""
    words = set()
    for path in paths:
        if path.endswith('.ref') and os.path.exists(path):
            text = open(path, encoding='utf-8').read()
            for title in TERM_TITLE_RE.findall(text):
                words |= set(re.findall(r'[a-z]+', title.lower()))
    ENV['term_words'] = frozenset(words)


def ste_names():
    """The -ing words STE treats as technical names: words of labels and glossary terms."""
    names = ENV.get('ste_names')
    if names is None:
        names = frozenset(w for label in ENV['labels'].values()
                          for w in label.lower().split('_') if w.endswith('ing'))
        names |= {w for w in ENV.get('term_words', ()) if w.endswith('ing')}
        ENV['ste_names'] = names
    return names


def check_ste_length(unit):
    text = unquoted(unit.text)
    for offset, sentence in sentences(text):
        words = STE_WORD_RE.findall(sentence)
        if len(words) > STE_MAX_WORDS:
            yield offset, cite(STE_LENGTH_DETAIL.format(
                len(words), ' '.join(words[:6]) + ' …'), 'STE-1')
            return


def check_ste_ing(unit):
    text = unquoted(unit.text)
    for m in STE_ING_RE.finditer(text):
        word = m.group(1).lower()
        if word in STE_NOT_ING or word in ste_names():
            continue
        yield m.start(), cite(STE_ING_DETAIL.format(m.group(1)), 'STE-4')
        return


def check_ste_paragraph(unit):
    count = sum(1 for _, s in sentences(unquoted(unit.text)) if s.strip())
    if count > STE_MAX_SENTENCES:
        yield 0, cite(STE_PARAGRAPH_DETAIL.format(count), 'STE-6')


# Every unit check: its kind, the surfaces it reads, and the file types it reads
# them in (None for every type).
UNIT_CHECKS = (
    ('BASE_ECHO', ALL_SURFACES, None, check_base_echo),
    ('PITCH', ALL_SURFACES, None, check_pitch),
    ('OPEN', ALL_SURFACES, None, check_open),
    ('DIARY', ALL_SURFACES, None, check_diary),
    ('REFPOINTER', SKOOL_COMMENT_SURFACES, ('.skool',), check_refpointer),
    ('SELFLINK', ALL_SURFACES, None, check_selflink),
    ('SYNTH_ECHO', ALL_SURFACES - {'row', 'data-row', 'register'}, None, check_synth),
    ('CODE_ECHO', NOT_REGISTER - {'ref-heading', 'term-title'}, None, check_code_echo),
    ('CODE_PAREN', NOT_REGISTER, None, check_code_paren),
    ('NUMBER_LIST', NOT_REGISTER, None, check_number_list),
    ('CODE_LIST', NOT_REGISTER, None, check_code_list),
    ('LEVEL_FACT', NOT_REGISTER - {'title', 'ref-heading', 'term-title'}, None,
     check_level_fact),
    ('HEADING_JARGON', frozenset(('ref-heading', 'title', 'term-title')), None,
     check_heading_jargon),
    ('IDENT_IN_PROSE', NOT_REGISTER, None, check_ident),
    ('GLOSSARY_DEF', frozenset(('term-body',)), None, check_glossary_def),
    ('GLOSSARY_IDENT', frozenset(('term-title',)), None, check_glossary_ident),
    ('CALLERS', ALL_SURFACES, None, check_callers),
    ('TYPOGRAPHY', ALL_SURFACES, None, check_typography),
    # Code rows are imperatives, and no fixed verb list holds them all.
    ('FRAGMENT_STOP', frozenset(('data-row', 'table-cell', 'register', 'title',
                                 'list-item')), None, check_fragment_stop),
    ('FOIL', ALL_SURFACES, None, check_foil),
    ('DEIXIS', frozenset(('block', 'title')), None, check_deixis),
    ('FOREIGN_LOGIC', frozenset(('block',)), None, check_foreign_logic),
    ('INLINE_RENDER', frozenset(('block', 'row', 'data-row', 'ref-para', 'term-body',
                                 'list-item', 'table-cell')), None, check_inline_render),
    ('DATA_ECHO', frozenset(('table-cell',)), None, check_cell_index),
    ('LABEL_ECHO', frozenset(('row', 'data-row')), ('.skool',), check_label_echo),
    ('BARE_VALUE', ALL_SURFACES, None, check_bare_value),
    ('NON_ZERO', frozenset(('data-row', 'block')), ('.skool',), check_non_zero),
    # A register row is one noun phrase (REG-2), never a sentence to split.
    ('STE_LENGTH', NOT_REGISTER, None, check_ste_length),
    ('STE_ING', ALL_SURFACES, None, check_ste_ing),
    ('STE_PARAGRAPH', frozenset(('block', 'ref-para', 'term-body')), None,
     check_ste_paragraph),
)


def unit_findings(path, units):
    """Run every unit check over every unit it applies to.

    Returns (lineno, kind, display, detail) tuples, one per kind per line.
    """
    ext = os.path.splitext(path)[1]
    seen, found = set(), []
    for unit in units:
        for kind, surfaces, files, check in UNIT_CHECKS:
            if unit.surface not in surfaces or (files and ext not in files):
                continue
            for offset, detail in check(unit):
                lineno, display = unit.locate(offset)
                key = (lineno, kind, detail)
                if key in seen:
                    continue
                seen.add(key)
                found.append((lineno, kind, display[:120], detail))
    return found


# UNU-1 and UNU-3. An unused entry is its title and nothing else.
UNUSED_TITLES = ('unused bytes', 'unused byte')
UNUSED_TEXT_DETAIL = (
    "an unused entry carries text ('{}') – unused bytes are titled 'Unused "
    "bytes' and say nothing else: no reason, no neighbors, no guessed purpose. "
    "One unused byte inside a used table keeps its 'Unused' row")
# DEF-5. A variable's words, against the variables and bytes it holds: 24 words
# for each labeled variable and 6 for each further byte.
WORDY_BASE, WORDY_PER_BYTE, WORDY_MAX_BYTES = 24, 6, 4
WORDY_DETAIL = (
    "{} words on a {}-byte variable ('{}') – a variable's definition says what it holds "
    "and how it is encoded, in one sentence per byte or so; who reads it, how "
    "it changes and what it selects belong to the code")


def entry_findings(units):
    """UNUSED_TEXT and WORDY_VARIABLE, which read a whole entry's units."""
    by_entry = {}
    for unit in units:
        e = entry_of(unit)
        if e is not None and unit.surface in SKOOL_COMMENT_SURFACES:
            by_entry.setdefault(id(e), (e, []))[1].append(unit)
    found = []
    for e, entry_units in by_entry.values():
        if e.type == 'u':
            for unit in entry_units:
                text = unit.text.strip()
                if unit.surface == 'title' and text.lower().rstrip('.') in UNUSED_TITLES:
                    continue
                if e.length == 1 and unit.surface in ('row', 'data-row') \
                        and text.rstrip('.').lower() == 'unused':
                    continue
                found.append((unit.lineno, 'UNUSED_TEXT', unit.display[:120],
                              cite(UNUSED_TEXT_DETAIL.format(text[:60]), 'UNU-1')))
                break
        elif e.type == 'g' and 0 < e.length <= WORDY_MAX_BYTES:
            words = sum(len(u.text.split()) for u in entry_units if u.surface != 'register')
            # Each labeled byte is a variable of its own, with its own sentence.
            variables = max(1, sum(1 for addr, _ in e.rows if addr in ENV['labels']))
            budget = WORDY_BASE * variables + WORDY_PER_BYTE * max(0, e.length - variables)
            if words > budget:
                first = entry_units[0]
                found.append((first.lineno, 'WORDY_VARIABLE', first.display[:120],
                              cite(WORDY_DETAIL.format(words, e.length, e.title[:60]), 'DEF-5')))
    return found


def scan_prose(path):
    """Scan a reader-facing page (`.ref`, `.ctl` titles, a spec page).

    The same unit checks the `.skool` gets, over the same surfaces: a page is
    read by the same reader as the listing, so it is held to the same rules.
    The `.skool`'s labels and entries, when it was scanned first, resolve the
    page's `#R` references.
    """
    units = read_units(path)[0]
    violations = unit_findings(path, units)
    violations.sort(key=lambda v: v[0])
    return violations


# NAME-7. A byte pair is one family: its high byte's `_hi` or `_high` label has
# a low byte labeled on the same stem with `_lo` or `_low`, one or two bytes
# below. `door_timer` beside `door_timer_hi` names the pair as if the low
# byte were the whole value.
LABEL_PAIR_SUFFIXES = (('_hi', '_lo'), ('_high', '_low'))
LABEL_PAIR_DETAIL = (
    "'{}' has no low-byte twin – label the byte below it '{}', so both halves "
    "carry the pair's one naming scheme")


def label_pairs(lines):
    """Yield (lineno, label, wanted) for each high-byte label with no matching low byte."""
    placed, pending = [], None
    for lineno, raw in enumerate(lines, 1):
        m = LABEL_RE.match(raw.rstrip('\n'))
        if m:
            pending = (lineno, m.group('label'))
            continue
        im = INSTR_RE.match(raw.rstrip('\n'))
        if im and pending:
            # A code label's _lo and _hi name branches, not the halves of a value.
            if re.search(r'\bDEF[BW]\b', raw):
                placed.append((pending[0], pending[1], int(im.group('addr'), 16)))
            pending = None
    by_addr = {addr: label for _, label, addr in placed}
    for lineno, label, addr in placed:
        for hi, lo in LABEL_PAIR_SUFFIXES:
            if label.endswith(hi):
                wanted = label[:-len(hi)] + lo
                if wanted not in (by_addr.get(addr - 1), by_addr.get(addr - 2)):
                    yield lineno, label, wanted


def scan(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # The text checks read prose units, each over the surfaces it declares; the
    # checks below them read the listing's structure, which a unit does not
    # carry: groups and their spans, operands, entry types.
    units, unit_labels, entries = read_units(path)
    set_env(unit_labels, entries)

    violations_pending = unit_findings(path, units) + entry_findings(units)

    for lineno, text, what in data_echoes(lines):
        violations_pending.append((lineno, 'DATA_ECHO', text,
                                   cite(DATA_ECHO_DETAIL.format(what), 'ROW-1')))

    for lineno, label, wanted in label_pairs(lines):
        violations_pending.append((lineno, 'LABEL_PAIR', label,
                                   cite(LABEL_PAIR_DETAIL.format(label, wanted), 'NAME-7')))

    for lineno, title in unrendered_elements(lines):
        violations_pending.append((lineno, 'UNRENDERED', title, UNRENDERED_DETAIL))

    violations = list(violations_pending)

    def add(lineno, kind, text, detail):
        violations.append((lineno, kind, text, detail))

    # Pre-pass: map each address to its @label, for the SELFLINK check.
    labels = {}
    pending_label = None
    for raw in lines:
        line = raw.rstrip('\n')
        m = LABEL_RE.match(line)
        if m:
            pending_label = m.group('label')
            continue
        im = INSTR_RE.match(line)
        if im and pending_label:
            labels[im.group('addr').upper()] = pending_label
        # Another @ directive may sit between @label and its instruction; only a
        # non-directive line breaks the association.
        if line.strip() and not line.startswith('@'):
            pending_label = None

    # Pre-pass: the control-flow edges, for GROUP_ENTRY. Every branch and call in
    # the file, by target, so a group can ask whether one of its interior rows is
    # reached from outside its own span. Built over the whole .skool, not the
    # routine: the jump that makes a group's middle a second entrance usually
    # comes from another block.
    label_addrs = {name: addr for addr, name in labels.items()}
    edges = {}
    for raw in lines:
        im = INSTR_RE.match(raw.rstrip('\n'))
        if not im:
            continue
        code, _ = split_comment(im.group('body'))
        bm = BRANCH_TARGET_RE.match(code.strip())
        if not bm:
            continue
        target = operand_target(bm.group('target'), label_addrs)
        if target:
            edges.setdefault(target, set()).add(im.group('addr').upper())

    # Block-comment paragraphs (consecutive ';' lines), for the STAMP check.
    units = []
    para_lineno, para_text = None, []
    in_group = False  # inside an open '{ }' instruction-comment group
    group_rows = []   # the open group's (lineno, line, comment, operand addresses)
    # The same rows again, as {lineno, line, addr, ctrl, instr}, but tracked from
    # the braces alone. A mid-block ';' note (SkoolKit's "This entry point is
    # used by …") breaks a group for the per-row checks, whose text it is not
    # part of — but the brace pair still spans it, and so does the sentence on
    # the page. The two structural laws have to read that real span, or they go
    # blind at exactly the rows they exist to judge: an entry-point note sits
    # directly above the '*' row GROUP_ENTRY is about.
    in_span = False
    span_ins = []
    comment_units = []  # (lineno, line, text) per comment unit, for SPLICE
    unit_open = None    # the unit being accumulated, while a group is open
    in_code = False     # inside a `c` entry, where an offset is a citation

    layout_rows = []  # (lineno, line, joined text, inside a code entry)

    def close_para():
        nonlocal para_lineno, para_text
        if para_text:
            units.append((para_lineno, ' '.join(para_text)))
            joined = ' '.join(para_text)
            layout_rows.append((para_lineno, joined.strip()[:120], joined, in_code))
        para_lineno, para_text = None, []

    def close_group():
        """Report the open group's operand echoes, then forget the group."""
        nonlocal group_rows
        reported = set()
        for lineno, text in echo_rows(group_rows):
            add(lineno, 'OPERAND_ECHO', text, OPERAND_ECHO_DETAIL)
            reported.add(lineno)
        # Only when no row of the group was reported already: a group whose
        # opening row echoes its own operand is one defect, not two.
        if group_rows and not reported:
            joined = ' '.join(r[2] for r in group_rows if r[2])
            values = set().union(*(r[4] for r in group_rows))
            quoted = span_echoes(joined, values)
            if quoted:
                add(group_rows[0][0], 'OPERAND_ECHO', group_rows[0][1],
                    SPAN_ECHO_DETAIL.format(', '.join(sorted(quoted))))
        group_rows = []

    def close_span():
        """Apply the two structural laws to the completed brace-delimited span.

        Both need the span whole — whether a jump is this span's own back-edge,
        and whether an entry point is reached from outside it, are questions
        about the set of addresses the span covers — so neither can run per row.
        """
        nonlocal span_ins
        span_addrs = {row['addr'] for row in span_ins}
        for row in span_ins[:-1]:
            if group_split_row(row['instr'], span_addrs, label_addrs):
                add(row['lineno'], 'GROUP_SPLIT', row['line'],
                    GROUP_SPLIT_DETAIL.format(row['instr']))
        for row in span_ins[1:]:
            if row['ctrl'] != '*':
                continue
            sources = edges.get(row['addr'], set())
            outside = sorted(sources - span_addrs)
            if outside:
                add(row['lineno'], 'GROUP_ENTRY', row['line'],
                    GROUP_ENTRY_DETAIL.format(
                        ', '.join('$' + a for a in outside[:3])))
                continue
            # A target reached only from inside the span is exempt when every
            # such source sits *below* it: that is the span's own loop, and a
            # loop is one act. A source above it is a forward skip, and those
            # are not the same thing — on the skipping path the rows between
            # the branch and this row never execute, so the sentence covers
            # instructions the reader may not run. Without that distinction a
            # clamp's sentence swallows a separately named act whenever the
            # branch over the clamp lands inside the span.
            skips = sorted(s for s in sources if s < row['addr'])
            if skips:
                add(row['lineno'], 'GROUP_SKIP', row['line'],
                    GROUP_SKIP_DETAIL.format(skips[0]))
        span_ins = []

    for i, raw in enumerate(lines):
        line = raw.rstrip('\n')
        lineno = i + 1

        m = LABEL_RE.match(line)
        if m and PLACEHOLDER_LABEL_RE.match(m.group('label')):
            add(lineno, 'PLACEHOLDER', line.strip(),
                f"label '{m.group('label')}' names nothing — name it for what it does")
            continue

        comment = None
        instr = None
        bm = BLOCK_COMMENT_RE.match(line)
        im = INSTR_RE.match(line)
        if bm is not None and im is None:
            comment = bm.group('text')
            if not REGISTER_LINE_RE.match(comment):
                if para_lineno is None:
                    para_lineno = lineno
                para_text.append(comment)
        elif im is not None:
            instr, comment = split_comment(im.group('body'))
            if im.group('ctrl') in 'cbtwsgi':
                in_code = im.group('ctrl') == 'c'
            close_para()
        elif line.startswith('@'):
            # An @isub/@ofix/@label directive sits between two instructions of a
            # group without interrupting it, so it must not close one.
            continue
        else:
            close_para()
            in_group = False        # a group cannot span a non-instruction line
            close_group()
            in_span = False         # a blank line is an entry boundary
            close_span()

        if comment is None:
            continue

        # Track '{ }' group state and flag a bare RET the group swallows: the
        # group's text is about the logic above it; the RET is infrastructure.
        if instr is not None:
            parts0 = instr.split(None, 1)
            if (parts0 and parts0[0].upper() == 'RET' and len(parts0) == 1
                    and (in_group or ('}' in comment and not comment_body(comment)))):
                add(lineno, 'RET_GROUP', line.strip(),
                    "a '{ }' comment group spans this RET — close the group on "
                    'the last instruction its text describes; the RET stays bare')
            opens = '{' in comment and (comment_body(comment) or in_group)
            if in_group or opens:
                operands0 = parts0[1] if len(parts0) > 1 else ''
                group_rows.append((lineno, line.strip(), comment_body(comment),
                                   operand_addresses(operands0),
                                   operand_literals(parts0[0], operands0)))
            body_text = comment_body(comment)
            if opens:
                unit_open = [lineno, line.strip(), body_text]
                comment_units.append(unit_open)
                layout_rows.append((lineno, line.strip(), unit_open, in_code))
            elif in_group and unit_open is not None:
                if body_text:
                    unit_open[2] = (unit_open[2] + ' ' + body_text).strip()
            elif body_text:
                comment_units.append([lineno, line.strip(), body_text])
                layout_rows.append((lineno, line.strip(), body_text, in_code))
            if in_span or opens:
                span_ins.append({'lineno': lineno, 'line': line.strip(),
                                 'addr': im.group('addr').upper(),
                                 'ctrl': im.group('ctrl'),
                                 'instr': instr.strip().rstrip(';').strip()})
            if opens:
                in_group = True
                in_span = True
            if '}' in comment:
                in_group = False
                unit_open = None
                close_group()
                in_span = False
                close_span()
        else:
            in_group = False        # a block-comment line breaks any group
            close_group()

        # ELLIPSIS runs before the group skip below, because the splice it looks
        # for is *made of* groups: one closes on '...' and the next opens on
        # '...', chaining a thought across two groups instead of writing one over
        # the rows it covers. Skipping braced rows would blind the check to its
        # own primary case, the form `; {Copy one glyph row...` /
        # `; {...stepping down one row.`.
        # The marker is authored, so testing the group's own text is exact.
        if instr is not None:
            spliced = comment_body(comment)
            if spliced.startswith(('...', '…')) or spliced.endswith(('...', '…')):
                add(lineno, 'ELLIPSIS', line.strip(),
                    "a '...'-spliced continuation — one thought spanning "
                    "instructions is a '{ }' comment group, not chained fragments")

        # A comment carrying a '{' or '}' belongs to a multi-line group that
        # spans a *set* of instructions; its text is wrapped across those lines
        # and is not authored on any single one. Whether such a group spans the
        # right instructions is an expert judgment (the Challenger's), not a
        # scriptable one — so the checks that read one instruction skip these.
        # The skip is per row, not per group: a group's interior rows carry no
        # brace, fall through here, and are read like any other row.
        # OPERAND_ECHO skips nothing — close_group() runs it over every row of
        # the group, each against the operand standing beside it.
        if '{' in comment or '}' in comment:
            continue
        comment = comment_body(comment)

        if instr is not None and comment:
            parts = instr.split(None, 1)
            mnemonic = parts[0] if parts else ''
            operands = parts[1] if len(parts) > 1 else ''
            if mnemonic.upper() == 'RET' and not operands:
                add(lineno, 'RET', line.strip(),
                    'comment on a bare RET — self-evident; leave it bare')
            elif comment_restates(mnemonic, operands, comment):
                add(lineno, 'RESTATE', line.strip(),
                    'comment only restates the instruction — say the why, not the what')
            # A group's interior row reaches here with no brace of its own, and
            # close_group() already reads it; only an ungrouped row is checked.
            if not in_group:
                for echo_lineno, echo_text in echo_rows(
                        [(lineno, line.strip(), comment,
                          operand_addresses(operands),
                          operand_literals(mnemonic, operands))]):
                    add(echo_lineno, 'OPERAND_ECHO', echo_text, OPERAND_ECHO_DETAIL)

    close_para()
    close_group()
    close_span()
    for lineno, line, prev in splice_units([tuple(u) for u in comment_units]):
        add(lineno, 'SPLICE', line, SPLICE_DETAIL.format(prev))
    # Tested on the joined unit rather than the row: a group's text is wrapped
    # across its rows, and half a coordinated run reads like a bare offset.
    for lineno, line, text, code in layout_rows:
        offset = layout_echo(text[2] if isinstance(text, list) else text)
        if offset and code:
            add(lineno, 'LAYOUT_ECHO', line, LAYOUT_ECHO_DETAIL.format(offset))
    for lineno, phrase, count in find_stamps(units):
        add(lineno, 'STAMP', f'"{phrase[:100]}…"' if len(phrase) > 100 else f'"{phrase}"',
            f'this sentence is written into {count} block comments — write it '
            'once at the family head (dispatcher/primitive/table), keep only '
            'deltas here')

    # A group's findings are raised when the group closes, and STAMP's when the
    # file ends, so report order follows the file rather than the check.
    violations.sort(key=lambda v: v[0])
    return violations


def token(finding):
    """The baseline's third field for one finding: an address, or file:term."""
    m = ROW_ADDRESS_RE.match(finding[2].lstrip())
    if m:
        return f'${m.group(1).upper()}'
    term = QUOTED_TERM_RE.search(finding[3])
    slug = re.sub(r'[ _-]+', '-', term.group(1).lower()) if term else finding[1].lower()
    return f'{os.path.basename(finding[4])}:{slug}'


def main():
    parser = argparse.ArgumentParser(
        description='Lint comment quality in a generated .skool and the prose '
                    'deliverables beside it.')
    parser.add_argument('paths', nargs='+', help='the .skool, then any prose files')
    parser.add_argument('--advisory', action='store_true',
                        help='list the advisory findings, not just their counts')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    findings = []
    read_term_words(args.paths)
    for path in args.paths:
        try:
            scanned = scan(path) if path.endswith('.skool') else scan_prose(path)
        except FileNotFoundError:
            print(f'Error: File not found: {path}')
            return 1
        findings += [v + (path,) for v in scanned]

    gating = [f for f in findings if f[1] in GATING_KINDS]
    advisory = [f for f in findings if f[1] not in GATING_KINDS]

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, gating, [], token_of=token))
        return 0

    new, held, stale = ctl_baseline.partition(
        args.baseline, CHECK, gating, [],
        report_stale=not args.ignore_stale, token_of=token)

    def by_kind(items):
        groups = {}
        for v in items:
            groups.setdefault(v[1], []).append(v)
        return groups

    # `Found <n> …` is the sweep's contract: `lint_sweep.sh` reads the count back
    # out of this line, and a failing check whose count it cannot parse is
    # reported as unreadable rather than as zero. The advisory tally must not
    # start that way — it is not a finding count the gate is entitled to add.
    if new:
        print(f'Found {len(new)} comment defect(s):')
        for kind, items in sorted(by_kind(new).items()):
            print(f'\n[{kind}] {len(items)}')
            for lineno, _, text, detail, path in items:
                print(f'  {os.path.basename(path)}:{lineno}: {detail}')
                print(f'    {text}')
        print()
    elif not held and not stale:
        print('comments: no gating comment defect')

    if advisory:
        tally = ', '.join(f'{len(v)} {k}' for k, v in sorted(by_kind(advisory).items()))
        print(f'  advisory, not gated: {tally}'
              + ('' if args.advisory else '  — run `lint_comments.py … --advisory`'
                                          ' for the list'))
        # STAMP counts phrases, and a phrase is bounded by comment units. Splitting
        # one unit into two, or rewording a sentence, moves the count without
        # touching the duplication it tracks, so the number reads like a
        # project-quality figure and is not one.
        if 'STAMP' in by_kind(advisory):
            print('  (a STAMP count is not comparable across an edit: the phrase it '
                  'matches is bounded by comment units, so splitting a unit or '
                  'rewording a sentence moves the tally without changing what is '
                  'duplicated. Read the list, not the delta.)')
        if args.advisory:
            for kind, items in sorted(by_kind(advisory).items()):
                print(f'\n[{kind}] {len(items)}')
                for lineno, _, text, detail, path in items:
                    print(f'  {os.path.basename(path)}:{lineno}: {detail}')
                    print(f'    {text}')
            print()

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
