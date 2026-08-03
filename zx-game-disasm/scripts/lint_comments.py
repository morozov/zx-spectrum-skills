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
  - OPERAND_ECHO   a comment #R-referencing the very address its own
                   instruction's operand carries — label-rendered operands
                   already show and link that symbol on the same row
  - ELLIPSIS       a comment spliced across instructions with '...' — one
                   thought spanning rows is a '{ }' comment group, not chained
                   fragments
  - REFPOINTER     a comment pointing the reader at a `.ref` index file
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
instruction with its comment and resolves #R references and data sub-blocks. Per-
instruction checks skip any comment that is part of a multi-line '{ }' group.

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


def diary_detail(hit):
    """The DIARY message, sharpened for a runtime citation."""
    if RUNTIME_HIT_RE.fullmatch(hit):
        return (f"the deliverable rests on a run ('{hit}') — a run is how you "
                'got the evidence, not what supports the claim: re-derive the '
                'fact from the code and state it flat, or drop it')
    return (f"investigation vocabulary ('{hit}') — state the game fact flat; "
            "type real uncertainty (trailing '?', TODO:) or file a dig-task")


def scan_prose(path):
    """Scan a reader-facing prose deliverable (.ref catalog, spec page) for
    investigation vocabulary. Only DIARY applies — the rest of the checks read
    an instruction column this file does not have."""
    violations = []
    with open(path, 'r', encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            dm = DIARY_RE.search(raw)
            if dm:
                violations.append((lineno, 'DIARY', raw.strip()[:120],
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

    def close_para():
        nonlocal para_lineno, para_text
        if para_text:
            units.append((para_lineno, normalize_tokens(' '.join(para_text))))
        para_lineno, para_text = None, []

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
        else:
            close_para()
            in_group = False        # a group cannot span a non-instruction line

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
            if '{' in comment and (comment_body(comment) or in_group):
                in_group = True
            if '}' in comment:
                in_group = False
        else:
            in_group = False        # a block-comment line breaks any group

        # Text-level checks apply to every comment, grouped or not.
        for slre in (SELFLINK_RE, SELFLINK_REV_RE):
            sm = slre.search(comment)
            if sm and labels.get(sm.group('addr').upper()) == sm.group('name'):
                add(lineno, 'SELFLINK', line.strip(),
                    f"'{sm.group('name')}' and '#R${sm.group('addr')}' render as "
                    f"\"{sm.group('name')} ({sm.group('name')})\" — link the first "
                    "mention only, drop the parenthetical")
                break
        dm = DIARY_RE.search(comment)
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
        # scriptable one — so the per-instruction checks skip these entirely.
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
            op_addrs = {a.upper() for a in re.findall(r'\$([0-9A-Fa-f]{4})\b', operands)}
            op_addrs |= {f'{int(n):04X}' for n in re.findall(r'\b(\d{4,5})\b', operands)
                         if 16384 <= int(n) <= 65535}
            for cm in COMMENT_REF_RE.finditer(comment):
                ref = (cm.group('hex') or f"{int(cm.group('dec')):04X}").upper()
                if ref in op_addrs:
                    add(lineno, 'OPERAND_ECHO', line.strip(),
                        'the comment re-references its own operand — the '
                        'instruction already shows and links that symbol; '
                        'say the action, drop the echo')
                    break
            stripped = comment.strip()
            if stripped.startswith(('...', '…')) or stripped.endswith(('...', '…')):
                add(lineno, 'ELLIPSIS', line.strip(),
                    "a '...'-spliced continuation — one thought spanning "
                    "instructions is a '{ }' comment group, not chained fragments")

    close_para()
    for lineno, phrase, count in find_stamps(units):
        add(lineno, 'STAMP', f'"{phrase[:100]}…"' if len(phrase) > 100 else f'"{phrase}"',
            f'phrase stamped across {count} block comments — write it once at '
            'the family head (dispatcher/primitive/table), keep only deltas here')

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
