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
  - UNRENDERED     a data block whose title names a sprite, glyph, font or tune,
                   carrying no render macro. The catalog page is an index; a
                   block that encodes one element shows that element
  - EULOGY         more than a couple of dozen words on a `u` block — bytes
                   nothing uses. It owes that it is unused plus any real trivia,
                   never the proof: the reader census, the fill that stops short,
                   the stride that could not be found
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
                   neither describes the rows it sits on
  - REFPOINTER     a comment pointing the reader at a `.ref` index file
  - OPEN           a typed uncertainty marker ("(unverified)", "TODO:") — the one
                   legitimate way to leave a doubt in the text, and a standing
                   statement that the work is not finished
  - STAMP          the same >=8-word phrase (addresses normalized) in 3+ block
                   comments — family text stamped per sibling instead of written
                   once at the family head

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
reader, so DIARY runs over them too — any non-.skool argument is scanned line by
line for that vocabulary alone. The `.skool` was linted and the `.ref` files were
not, which is exactly where runtime-sourced claims accumulated.

The gating kinds are held against the project's `lint-baseline.txt` like every
other gating check, so a mature project records the findings it starts with and
the gate fails on a new one. The advisory kinds print and never fail.

Usage: lint_comments.py <file.skool> [prose-file …] [--baseline FILE] [--write-baseline]
Exit 0 when no unbaselined gating finding stands, 1 otherwise.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'comments'

# The kinds that gate. Each is a precise detection of an always-wrong pattern —
# no judgment call sits between the finding and the defect — so each belongs in
# the build's own lint sweep, held against `lint-baseline.txt` like every other
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
    'LAYOUT_ECHO', 'PITCH', 'SYNTH_ECHO', 'EULOGY', 'UNRENDERED', 'OPEN',
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
# rows it sits on. A unit that opens lowercase after a unit that ended without
# terminal punctuation is not doing that: the two are one sentence cut in half,
# and the second half describes nothing on its own. "Leave it alone while the
# grow animation still runs," / "and while the shrink animation still runs." is
# the shape — the reader of the second block is handed a subordinate clause.
#
# Both halves of the test are needed. Opening lowercase is not enough on its own
# (a unit may legitimately start with a symbol or a lowercased identifier), and
# an unterminated previous unit is not enough either. Together they are exact.
# A cross-reference between blocks is still allowed — it just has to be written
# as one, in a sentence of its own.
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

EULOGY_WORDS = 25
EULOGY_DETAIL = (
    "{} words on bytes nothing uses. An unused block owes 'Unused.' and, if one "
    "exists, the single thing worth knowing about it — bytes that decode to a "
    "message, padding an alignment the next table needs. It does not owe the "
    "proof that it is unused: no census of readers, no account of which fill "
    "stops short, no note on why no stride could be found"
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
    """Return the pitch a line states, or None when it states none."""
    for m in PITCH_RE.finditer(text):
        if not m.group('k') and m.group('n').replace(',', '') in ('50', '48'):
            continue
        return m.group(0).strip()
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


def splice_units(units):
    """Report each unit that completes the previous unit's unfinished sentence.

    `units` is (lineno, line, text) in file order, one per comment unit.
    """
    hits = []
    for (_, _, prev), (lineno, line, text) in zip(units, units[1:]):
        prev = prev.rstrip()
        if not prev or not text or not text[0].islower():
            continue
        if prev[-1] in '.!?:':
            continue
        hits.append((lineno, line, prev[-48:]))
    return hits


def base_echo(text):
    """Return the '$8A (138)' substring when one comment spells a value twice."""
    for m in BASE_PAIR_RE.finditer(text):
        hexed = m.group('hex') or m.group('hex2')
        dec = m.group('dec') or m.group('dec2')
        if int(hexed, 16) == int(dec):
            return m.group(0)
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
# (a record offset — "+1" names a field, not a value), and a word character.
# Excluded to the right: a word character, so "20th" is not a value, and a '.'
# followed by a digit, so "1.3 kHz" is one number rather than two. A '.' that
# ends a sentence is not part of the number, so "period: 50." still matches.
DECIMAL_RE = re.compile(r'(?<![\w$+.-])(\d{1,5})(?![\w])(?!\.\d)')
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
    r'\$([0-9A-Fa-f]{2})(?![0-9A-Fa-f])|(?<![\w$+.-])(\d{1,5})(?![\w])(?!\.\d)')


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


def unused_annotations(lines):
    """Yield (lineno, word count, first line) for every `u` entry's annotation.

    A `u` block is bytes nothing uses, so the only content that exists is that
    it is unused plus any one fact worth knowing. Everything a project writes
    past that is the proof, and the proof is what the reader did not come for.
    """
    index, total = 0, len(lines)
    while index < total:
        if not lines[index].startswith(';'):
            index += 1
            continue
        start = index
        block = []
        while index < total and lines[index].startswith(';'):
            block.append(lines[index][1:].strip())
            index += 1
        entry = index
        while entry < total and (lines[entry].startswith('@') or not lines[entry].strip()):
            entry += 1
        if entry >= total or not re.match(r'^u\$[0-9A-Fa-f]{4}', lines[entry]):
            continue
        gutter, row = [], entry
        while row < total and lines[row].strip() and not lines[row].startswith(';'):
            if ';' in lines[row]:
                gutter.append(lines[row].split(';', 1)[1])
            row += 1
        text = ' '.join(block + gutter).replace('{', ' ').replace('}', ' ')
        text = MACRO_SPAN_RE.sub(' ', text)
        text = MACRO_RE.sub(' ', text)
        first = next((b for b in block if b and b != '.'), '')
        yield start + 1, len(text.split()), first[:120]


def scan_prose(path):
    """Scan a reader-facing prose deliverable (.ref catalog, spec page) for
    investigation vocabulary. Only DIARY applies — the rest of the checks read
    an instruction column this file does not have."""
    violations = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # An entry that renders its sound owes the render and the meaning, not the
    # method. A page's shared model, stated once in a section that renders
    # nothing, is the one home for it and stays — so the signal is the #AUDIO
    # beside the prose, which is on the page and decidable.
    audio_lines = set()
    start, holds_audio = 0, False
    for index, raw in enumerate(lines):
        if raw.startswith('['):
            if holds_audio:
                audio_lines.update(range(start + 1, index + 1))
            start, holds_audio = index, False
        if '#AUDIO' in raw:
            holds_audio = True
    if holds_audio:
        audio_lines.update(range(start + 1, len(lines) + 1))

    for lineno, raw in enumerate(lines, 1):
            text = raw.strip()[:120]
            pair = base_echo(raw)
            if pair:
                violations.append((lineno, 'BASE_ECHO', text,
                                   BASE_ECHO_DETAIL.format(pair)))
            pitch = pitch_echo(raw)
            if pitch:
                violations.append((lineno, 'PITCH', text,
                                   PITCH_DETAIL.format(pitch)))
            for om in OPEN_MARKER_RE.finditer(raw):
                violations.append((lineno, 'OPEN', text,
                                   OPEN_DETAIL.format(om.group(0))))
            dm = DIARY_RE.search(OPEN_MARKER_RE.sub(' ', raw))
            if dm:
                violations.append((lineno, 'DIARY', text,
                                   diary_detail(dm.group(0))))
            if lineno in audio_lines and not raw.lstrip().startswith('#'):
                sm = SYNTH_RE.search(raw)
                if sm:
                    violations.append((lineno, 'SYNTH_ECHO', text,
                                       SYNTH_DETAIL.format(sm.group(0).strip())))
    return violations


def scan(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Which block comments render their sound. An entry's block comment is one
    # contiguous run of column-0 ';' lines, so the run is the unit and the
    # #AUDIO in it is the signal: prose sitting beside the clip that plays the
    # effect must not also say how the effect is made. Instruction comments are
    # not marked — the body is where the algorithm is explained, and it should
    # be. This is the same shape as LAYOUT_ECHO: decided by location, not by
    # reading the prose.
    audio_block_lines = set()
    run_start, run_audio = None, False
    for index, raw in enumerate(lines):
        if raw.startswith(';'):
            if run_start is None:
                run_start, run_audio = index, False
            if '#AUDIO' in raw:
                run_audio = True
            continue
        if run_start is not None and run_audio:
            audio_block_lines.update(range(run_start + 1, index + 1))
        run_start, run_audio = None, False
    if run_start is not None and run_audio:
        audio_block_lines.update(range(run_start + 1, len(lines) + 1))

    violations_pending = []

    for lineno, title in unrendered_elements(lines):
        violations_pending.append((lineno, 'UNRENDERED', title, UNRENDERED_DETAIL))

    # Unused blocks, and what they were given. A `u` entry's whole annotation is
    # its block comment plus whatever sits in its gutter, and both are where the
    # eulogy lands. Counted together, reported once, at the block.
    for lineno, words, first in unused_annotations(lines):
        if words > EULOGY_WORDS:
            violations_pending.append((lineno, 'EULOGY', first,
                                       EULOGY_DETAIL.format(words)))

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
            if para_lineno in audio_block_lines:
                sm = SYNTH_RE.search(joined)
                if sm:
                    add(para_lineno, 'SYNTH_ECHO', joined.strip()[:120],
                        SYNTH_DETAIL.format(sm.group(0).strip()))
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

        # Text-level checks apply to every comment, grouped or not.
        for slre in (SELFLINK_RE, SELFLINK_REV_RE):
            sm = slre.search(comment)
            if sm and labels.get(sm.group('addr').upper()) == sm.group('name'):
                add(lineno, 'SELFLINK', line.strip(),
                    f"'{sm.group('name')}' and '#R${sm.group('addr')}' render as "
                    f"\"{sm.group('name')} ({sm.group('name')})\" — link the first "
                    "mention only, drop the parenthetical")
                break
        pair = base_echo(comment)
        if pair:
            add(lineno, 'BASE_ECHO', line.strip(), BASE_ECHO_DETAIL.format(pair))
        pitch = pitch_echo(comment)
        if pitch:
            add(lineno, 'PITCH', line.strip(), PITCH_DETAIL.format(pitch))
        for om in OPEN_MARKER_RE.finditer(comment):
            add(lineno, 'OPEN', line.strip(), OPEN_DETAIL.format(om.group(0)))
        dm = DIARY_RE.search(OPEN_MARKER_RE.sub(' ', comment))
        if dm:
            add(lineno, 'DIARY', line.strip(), diary_detail(dm.group(0)))
        rm = REF_POINTER_RE.search(comment)
        if rm:
            add(lineno, 'REFPOINTER', line.strip(),
                f"points the reader at '{rm.group(0)}' — render the resource "
                'here (#UDG / #AUDIO); the .ref file is only the index')
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
