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
  - REFPOINTER     a comment pointing the reader at a `.ref` index file
  - OPEN           a typed uncertainty marker ("(unverified)", "TODO:") — the one
                   legitimate way to leave a doubt in the text, and a standing
                   statement that the work is not finished
  - STAMP          the same >=8-word phrase (addresses normalized) in 3+ block
                   comments — family text stamped per sibling instead of written
                   once at the family head

This is deliberately a *small, high-precision* pre-filter, not the review. The
checks that matter most are not scriptable and belong to the Challenger:

  - whether a comment adds what the code cannot show (needs comprehension), and
  - whether a multi-line '{ }' comment spans exactly the instructions it
    describes (needs an expert reading of the routine).

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

Usage: lint_comments.py <file.skool> [prose-file …]
Exit 0 if clean, 1 if any violation is found.
"""

import re
import sys

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

# A comment that sends the reader to a `.ref` index instead of carrying the fact
# (or its rendered macro) where the reader already is. Scoped to the .skool: a
# `.ref` file naming its siblings is the index doing its job.
REF_POINTER_RE = re.compile(r'(?i)\b(graphics|sound)\.ref\b')

# STAMP tuning: a phrase of at least STAMP_WORDS normalized words appearing in
# STAMP_MIN_BLOCKS or more distinct block comments. Addresses are normalized so
# a sentence stamped with only the address swapped still matches. Deliberate
# scannable formulas are whitelisted.
STAMP_WORDS = 8
STAMP_MIN_BLOCKS = 3
STAMP_WHITELIST = ('used by the routine',)
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
#     interface a reader needs to use the code, not an internal name;
#   - an arithmetic/logic mnemonic against an immediate is a classifier testing
#     a value or a dispatcher naming its case, which is where the code IS the
#     subject.
#
# These three are the whole exclusion list, and nothing else needs one. Self-
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
CLASSIFIER_MNEMONICS = frozenset((
    'CP', 'AND', 'OR', 'XOR', 'BIT', 'SET', 'RES', 'SUB', 'ADD', 'ADC', 'SBC'
))


def operand_literals(mnemonic, operands):
    """Return the immediate values in `operands` whose echo is worth reporting.

    Empty for the three row shapes whose subject is the byte itself, so a
    catalog row, a record walk and a classifier test are never reported.
    """
    m = (mnemonic or '').upper()
    if m in DATA_DIRECTIVES or m in CLASSIFIER_MNEMONICS:
        return set()
    if INDEXED_RE.search(operands):
        return set()
    return {int(v, 16) for v in IMMEDIATE_RE.findall(operands)}


def comment_literals(comment):
    """Return the values a comment spells out, in either base.

    Values, not spellings. The base is a notation and the echo is the value, so
    "28" beside `LD B,$1C` restates the row exactly as "$1C" would.

    A decimal that looks like a false positive is usually the rule biting. The
    repair for `LD D,$64  ; start period $64 (100)` is not "start period 100" —
    that is still the operand, in the other base. It is the intent, or the
    derived fact the row cannot show: "~660 Hz". See "Derived facts stay,
    restatements go" in `references/comment-style.md`.
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

    Scoping it to the whole group instead — every #R in the group's text against
    every operand anywhere under it — reports the prose doing its job. A group
    comment names the things its span touches; that is what a paragraph over
    five instructions is for, and "Seed #R$9A10 to 9" over a span ending in
    `LD (obj_count),A` is not an echo. Only the row where
    the symbol lands beside its own operand is the duplicate the rule names.

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


def normalize_tokens(text):
    """Lowercase words with every address-like token collapsed to '§', so a
    sentence stamped across blocks with only the address swapped still matches.
    Macro spans are dropped first — they repeat by nature, not by laziness."""
    text = MACRO_SPAN_RE.sub(' ', text)
    text = ADDR_TOKEN_RE.sub('§', text)
    text = MACRO_RE.sub(' ', text)
    return WORD_RE.findall(text.lower())


def find_stamps(units):
    """Find maximal phrases of >=STAMP_WORDS words shared by >=STAMP_MIN_BLOCKS
    distinct block comments. units: list of (lineno, tokens)."""
    n = STAMP_WORDS
    shingles = {}
    for uid, (lineno, toks) in enumerate(units):
        for i in range(len(toks) - n + 1):
            shingles.setdefault(tuple(toks[i:i + n]), set()).add(uid)
    qualifying = {sh for sh, uids in shingles.items() if len(uids) >= STAMP_MIN_BLOCKS}
    results, reported = [], set()
    for uid, (lineno, toks) in enumerate(units):
        i = 0
        while i <= len(toks) - n:
            sh = tuple(toks[i:i + n])
            if sh in qualifying and sh not in reported:
                j = i
                while j + 1 <= len(toks) - n and tuple(toks[j + 1:j + 1 + n]) in qualifying:
                    j += 1
                for k in range(i, j + 1):
                    reported.add(tuple(toks[k:k + n]))
                phrase = ' '.join(toks[i:j + n])
                if not any(w in phrase for w in STAMP_WHITELIST):
                    results.append((lineno, phrase, len(shingles[sh])))
                i = j + n
            else:
                i += 1
    return results


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


def scan_prose(path):
    """Scan a reader-facing prose deliverable (.ref catalog, spec page) for
    investigation vocabulary. Only DIARY applies — the rest of the checks read
    an instruction column this file does not have."""
    violations = []
    with open(path, 'r', encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            text = raw.strip()[:120]
            for om in OPEN_MARKER_RE.finditer(raw):
                violations.append((lineno, 'OPEN', text,
                                   OPEN_DETAIL.format(om.group(0))))
            dm = DIARY_RE.search(OPEN_MARKER_RE.sub(' ', raw))
            if dm:
                violations.append((lineno, 'DIARY', text,
                                   diary_detail(dm.group(0))))
    return violations


def scan(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    violations = []

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

    # Block-comment paragraphs (consecutive ';' lines), for the STAMP check.
    units = []
    para_lineno, para_text = None, []
    in_group = False  # inside an open '{ }' instruction-comment group
    group_rows = []   # the open group's (lineno, line, comment, operand addresses)

    def close_para():
        nonlocal para_lineno, para_text
        if para_text:
            units.append((para_lineno, normalize_tokens(' '.join(para_text))))
        para_lineno, para_text = None, []

    def close_group():
        """Report the open group's operand echoes, then forget the group."""
        nonlocal group_rows
        for lineno, text in echo_rows(group_rows):
            add(lineno, 'OPERAND_ECHO', text, OPERAND_ECHO_DETAIL)
        group_rows = []

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
            close_para()
        elif line.startswith('@'):
            # An @isub/@ofix/@label directive sits between two instructions of a
            # group without interrupting it, so it must not close one.
            continue
        else:
            close_para()
            in_group = False        # a group cannot span a non-instruction line
            close_group()

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
            if opens:
                in_group = True
            if '}' in comment:
                in_group = False
                close_group()
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
            stripped = comment.strip()
            if stripped.startswith(('...', '…')) or stripped.endswith(('...', '…')):
                add(lineno, 'ELLIPSIS', line.strip(),
                    "a '...'-spliced continuation — one thought spanning "
                    "instructions is a '{ }' comment group, not chained fragments")

    close_para()
    close_group()
    for lineno, phrase, count in find_stamps(units):
        add(lineno, 'STAMP', f'"{phrase[:100]}…"' if len(phrase) > 100 else f'"{phrase}"',
            f'phrase stamped across {count} block comments — write it once at '
            'the family head (dispatcher/primitive/table), keep only deltas here')

    # A group's findings are raised when the group closes, and STAMP's when the
    # file ends, so report order follows the file rather than the check.
    violations.sort(key=lambda v: v[0])
    return violations


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.skool> [prose-file …]")
        return 1

    total = 0
    for path in sys.argv[1:]:
        try:
            violations = scan(path) if path.endswith('.skool') else scan_prose(path)
        except FileNotFoundError:
            print(f"Error: File not found: {path}")
            return 1
        if not violations:
            continue
        total += len(violations)

        by_kind = {}
        for v in violations:
            by_kind.setdefault(v[1], []).append(v)

        print(f"{path}: {len(violations)} comment-quality violation(s):")
        for kind in sorted(by_kind):
            items = by_kind[kind]
            print(f"\n[{kind}] {len(items)}")
            for lineno, _, text, detail in items:
                print(f"  Line {lineno}: {detail}")
                print(f"    {text}")
        print()

    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
