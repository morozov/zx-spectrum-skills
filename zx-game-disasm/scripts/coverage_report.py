#!/usr/bin/env python3
"""
Measure how far a disassembly is from the documentation bar — so "is it done?"
is a measured claim, not an impression.

A green build and a label on every routine is *breadth*, not depth. The bar is a
comment on ~40% of instructions, every
sound effect rendered with #AUDIO, data tables laid out with #TABLE, and no
placeholder labels. An agent must not call a project "mature"/"done" while this
report shows it far below the bar.

Reports, from the generated .skool (plus the .ctl and .ref files when given):

  - LINE DENSITY   % of real instructions (not DEFB/DEFW/...) carrying a comment,
                   overall and as a count of code routines below the threshold.
                   The default target is 35%.
  - SUMMARY-ONLY   code routines that have a description/title but almost no
                   line-level comments — the "breadth done, depth not done" trap.
  - AUDIO          #AUDIO count; a game with sound and zero #AUDIO is undocumented.
  - DATA TABLES    #TABLE count (the bar lays bitfields/tables out as #TABLE).
  - PLACEHOLDERS   @label values that name nothing (work_b, helper_8e3a, L5B50).
  - PROSE          the lint_comments counts, over the .skool and over the .ref
                   catalogs and spec/*.md beside it. RET_GROUP / SELFLINK /
                   DIARY / OPERAND_ECHO / ELLIPSIS are precise detections of
                   always-wrong patterns, so they gate the verdict; OPEN gates it
                   too, for the opposite reason — the marker is right where it
                   stands, and it says the claim under it is not derived yet.
                   STAMP / RET / RESTATE are advisory (a formula can be
                   legitimate). This is how a project built under older
                   requirements surfaces its gap to the current bar.

Exit 0 always — this is a yardstick the Manager and Challenger read, not a gate
that fails the build.

The `.ctl` and every `.ref` beside the skool are auto-discovered (catalog/audio
content is found by section type wherever it lives, under any filename), so just
point it at the skool. `--ctl`/`--ref` override the discovery.

Usage: coverage_report.py <file.skool> [--ctl FILE] [--ref FILE ...] [--min-density 0.35]
"""

import argparse
import re
import sys

INSTR_RE = re.compile(r'^(?P<ctrl>[ cbtwsgi*])\$(?P<addr>[0-9A-Fa-f]{4}) (?P<body>.*)$')
DATA_MNEMONIC = re.compile(r'^\s*(DEFB|DEFW|DEFM|DEFS)\b')
LABEL_RE = re.compile(r'^@label=(?P<label>\S+)\s*$')
PLACEHOLDER_LABEL_RE = re.compile(
    r'(?i)^(l|loc|sub|loop|data|byte|word|var|tmp|temp|work|helper|routine|'
    r'unknown|todo|fixme|xxx|placeholder)[_]?[0-9a-f]{0,4}$'
)


def comment_raw(body):
    """Return the raw comment text of a skool instruction body, braces kept."""
    in_q = False
    for i in range(len(body) - 1):
        ch = body[i]
        if ch == '"':
            in_q = not in_q
        elif ch == ';' and not in_q and body[i - 1] == ' ':
            return body[i + 1:].strip()
    return ''


def comment_of(body):
    """The comment text with `{ }` group markers stripped."""
    return comment_raw(body).replace('{', '').replace('}', '').strip()


def analyze(skool):
    """Walk the .skool into code routines, counting instructions and comments.

    Only `c` (code) entry blocks are counted; `b`/`t`/`w`/`s`/`g` data blocks (the
    loading screen, level data, tables, ...) are excluded entirely, as are DEF*
    data sub-blocks inside code. Data is documented by structure, labels, and
    native devices (#UDGARRAY/#TABLE/#AUDIO), not by per-line comments, so it does
    not belong in a line-density figure.
    """
    routines = []
    cur = None
    pending_label = None
    desc_text = False                       # did `;`-comment text precede this entry?
    in_group = False                        # inside an open `{ }` block comment
    placeholders = []
    with open(skool, encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if line.startswith(';'):
                if line[1:].strip():
                    desc_text = True
                continue
            lm = LABEL_RE.match(line)
            if lm:
                pending_label = lm.group('label')
                if PLACEHOLDER_LABEL_RE.match(pending_label):
                    placeholders.append(pending_label)
                continue
            m = INSTR_RE.match(line)
            if not m:
                if line.strip() == '':
                    desc_text = False        # blank line ends a description block
                continue
            ctrl, addr, body = m.group('ctrl'), m.group('addr'), m.group('body')
            if ctrl in 'cbtwsgi':           # a new entry block starts here
                if ctrl == 'c':
                    cur = {'name': pending_label or f'${addr}', 'instr': 0,
                           'cmt': 0, 'desc': desc_text}
                    routines.append(cur)
                else:
                    cur = None              # data block — not a code routine
                pending_label = None
                desc_text = False
                in_group = False            # a group cannot span blocks
            if cur is None:
                continue
            if DATA_MNEMONIC.match(body.split(';')[0]):
                continue                    # SMC data sub-block inside code: skip
            # A `{ }` block comment documents its whole span at the right altitude,
            # so credit every instruction inside a text-bearing group, not just the
            # opening line — otherwise the gauge penalizes the comment style the
            # skill recommends (state a formula once; leave the arithmetic bare).
            raw = comment_raw(body)
            text = raw.replace('{', '').replace('}', '').strip()
            covered = bool(text) or in_group
            if '{' in raw and (text or in_group):
                in_group = True
            if '}' in raw:
                in_group = False
            cur['instr'] += 1
            if covered:
                cur['cmt'] += 1
    return routines, placeholders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('skool')
    ap.add_argument('--ctl')
    ap.add_argument('--ref', action='append', default=[])
    ap.add_argument('--min-density', type=float, default=0.35)
    ap.add_argument('--reloc-floor', type=lambda s: int(s, 0), default=0x5B00,
                    help='lowest game-owned address; raw operands at/above it must be labels (default $5B00)')
    args = ap.parse_args()

    # Auto-discover the project's `.ref` and `.ctl` from the skool's directory, so
    # the catalog/audio metrics never read as zero just because a caller forgot to
    # pass `graphics.ref`. Catalog content can live in *any* .ref file under any
    # name; scan them all. Explicit --ref/--ctl override the discovery.
    import glob
    import os
    proj = os.path.dirname(os.path.abspath(args.skool)) or '.'
    refs = args.ref or sorted(glob.glob(os.path.join(proj, '*.ref')))
    ctl = args.ctl
    if not ctl:
        guess = os.path.splitext(args.skool)[0] + '.ctl'
        ctl = guess if os.path.exists(guess) else None
    print(f"Scanned: {os.path.basename(args.skool)}"
          + (f", {os.path.basename(ctl)}" if ctl else "")
          + (", " + ", ".join(os.path.basename(r) for r in refs) if refs else " (no .ref files found)"))

    routines, placeholders = analyze(args.skool)

    # Prose quality, from the bundled linter (same directory). The gating kinds
    # feed the verdict; the rest are advisory.
    # The catalogs and the spec pages are swept too — they are the same
    # deliverable, and the vocabulary settles wherever nothing looks.
    try:
        from lint_comments import scan as lint_scan
        from lint_comments import scan_prose as lint_scan_prose
        prose = {}
        found = list(lint_scan(args.skool))
        for path in refs + sorted(glob.glob(os.path.join(proj, 'spec', '*.md'))):
            found += lint_scan_prose(path)
        for v in found:
            prose[v[1]] = prose.get(v[1], 0) + 1
    except Exception as e:
        print(f"  (prose linter unavailable: {e})")
        prose = {}
    ret_group = prose.get('RET_GROUP', 0)
    selflink = prose.get('SELFLINK', 0)
    diary = prose.get('DIARY', 0)
    op_echo = prose.get('OPERAND_ECHO', 0)
    ellipsis = prose.get('ELLIPSIS', 0)
    stamp = prose.get('STAMP', 0)
    # A typed uncertainty marker is legitimate text and unfinished work at the
    # same time: it says a claim is not derived yet, so it holds the project
    # short of the bar until the dig-task behind it lands.
    open_markers = prose.get('OPEN', 0)
    prose_hard = ret_group + selflink + diary + op_echo + ellipsis

    # The honest unit is the routine, not the averaged line. A routine's body is
    # "explained" when it carries comments at roughly the right altitude — a low
    # bar of one comment per ~7 instructions catches the genuinely-bare bodies
    # without demanding a comment on every line (which the comment style forbids).
    EXPLAINED = 0.15
    sized = [r for r in routines if r['instr'] >= 5]

    def explained(r):
        return r['cmt'] / r['instr'] >= EXPLAINED

    documented = [r for r in sized if explained(r)]
    under = [r for r in sized if not explained(r)]
    bare = [r for r in under if r['cmt'] == 0 and not r['desc']]
    skeletal = [r for r in under if r not in bare]      # a one-line summary, no depth
    doc_frac = len(documented) / max(len(sized), 1)

    # Secondary, with the caveat: code instructions only, all data excluded.
    total = sum(r['instr'] for r in routines)
    commented = sum(r['cmt'] for r in routines)
    density = commented / total if total else 0.0

    def read(p):
        try:
            return open(p, errors='ignore').read()
        except OSError:
            return ''
    ctl_text = read(ctl) if ctl else ''
    ref_text = ''.join(read(r) for r in refs)
    blob = ctl_text + ref_text
    # Graphics belong inline in the .ctl — each sprite/frame rendered at its own
    # data block, so reading the disassembly there *shows* it — with the .ref as
    # the index over them. A project whose sprites live only in the .ref renders
    # 0 inline. Count each home apart.
    GFX = r'#UDGARRAY|#UDG\b|#UDGTABLE|#FONT|#SCR|#FRAMES'
    inline_gfx = len(re.findall(GFX, ctl_text))
    catalog_gfx = len(re.findall(GFX, ref_text))
    audio = blob.count('#AUDIO')
    # Audio follows the same source-of-truth rule as graphics: the #AUDIO belongs
    # inline at the block that owns the sound, with sound.ref as the index over it.
    inline_audio = ctl_text.count('#AUDIO')
    tables = blob.count('#TABLE')
    audio_sections = blob.count('[Audio:')
    graphic_sections = blob.count('[Graphic:')
    # Catalog entries still identified by an auto-label (f9440, a9440, L5B50) rather
    # than named for what the thing is, plus textual admissions of being unfinished.
    # Anchored to identifier positions and requiring 4 upper-hex so hex-looking
    # English ("face", "fade") does not match.
    auto_ids = len(re.findall(r'(?:\(\*?|\[Graphic:|\[Audio:)[aflL][0-9A-F]{4}\b', blob))
    admissions = len(re.findall(
        r'not yet|to be (?:named|identified)|\bTODO\b|unnamed|as identified|provisional',
        blob, re.I))
    # Unindexed arrays: a single B/W run spanning many records inside a block with
    # no commented element sub-lines and no inline render is an opaque blob — a
    # reader must count bytes to find record N. Advisory (a uniform blob can be
    # legitimate); blocks whose content is rendered by an image macro are exempt.
    unindexed = []
    RUN_RE = re.compile(r'^([BW]) \$?[0-9A-Fa-f]+,(\d+),(\d+)\s*$')
    ELEM_RE = re.compile(r'^  \$[0-9A-Fa-f]+,[0-9:,*bcdhn]+ +\S')
    LABEL_LINE_RE = re.compile(r'^@ \$?[0-9A-Fa-f]+ label=(\S+)')
    cur_name, pend_name = None, None
    cur_max_records, cur_elem_comments, cur_has_macro = 0, 0, False

    def flush_block():
        if cur_name and cur_max_records >= 10 and not cur_elem_comments and not cur_has_macro:
            unindexed.append((cur_name, cur_max_records))

    for ln in ctl_text.splitlines():
        lm = LABEL_LINE_RE.match(ln)
        if lm:
            pend_name = lm.group(1)
            continue
        if re.match(r'^[bcgistuwz] \$', ln):
            flush_block()
            cur_name = pend_name or ln.split()[1]
            pend_name = None
            cur_max_records, cur_elem_comments, cur_has_macro = 0, 0, False
            continue
        if not cur_name:
            continue
        rm = RUN_RE.match(ln)
        if rm and int(rm.group(3)):
            cur_max_records = max(cur_max_records, int(rm.group(2)) // int(rm.group(3)))
        if ELEM_RE.match(ln):
            cur_elem_comments += 1
        if re.search(GFX, ln):
            cur_has_macro = True
    flush_block()

    # Sound footprint: the ULA speaker ($FE) and the AY-3 sound chip ($FFFD/$BFFD,
    # used for tunes). If there is sound code and no #AUDIO, the audio is undocumented
    # — and a tune (AY) is easy to miss after the beeper effects are done.
    skool_text = open(args.skool, encoding='utf-8', errors='ignore').read()
    sound = len(re.findall(r'OUT\s*\(\$(FE|FFFD|BFFD)', skool_text))

    # Relocatability and naming, read from the generated .asm (post --create-labels):
    # an `L####:` auto-label is a block SkoolKit had to name because the .ctl did not
    # — an unnamed block; the bar is zero.
    # A raw $XXXX program-address operand is a non-relocatable reference; some are
    # legitimate (fixed hardware, EQU), so it is a soft signal reported for context.
    # ORG is skipped: it sets the assembler's location counter rather than referring
    # to an address, so pinning a fixed-placement buffer is the opposite of a
    # relocatability defect and must not score as one.
    # A raw operand below the game floor (default $5B00) is fixed hardware — ROM
    # ($0000-$3FFF) and the screen/attributes ($4000-$5AFF) — and stays absolute.
    # At/above the floor is the game's own region (printer buffer it repurposes,
    # its variables and code), and every reference there must be a label. The floor
    # is per-game; $5B00 is the standard "above screen + printer buffer" line.
    floor = args.reloc_floor
    asm_path = os.path.splitext(args.skool)[0] + '.asm'
    auto_labels = raw_ops = total_labels = 0
    if os.path.exists(asm_path):
        asm = open(asm_path, encoding='utf-8', errors='ignore').read()
        auto_labels = len(re.findall(r'(?m)^L[0-9A-Fa-f]{4}:', asm))
        total_labels = len(re.findall(r'(?m)^[A-Za-z_][A-Za-z0-9_]*:', asm))
        for ln in asm.splitlines():
            code = ln.split(';', 1)[0]
            tokens = code.split()
            if ' EQU ' in code or (tokens and tokens[0].upper() == 'ORG'):
                continue
            for hx in re.findall(r'\$([0-9A-Fa-f]{4})\b', code):
                if int(hx, 16) >= floor:
                    raw_ops += 1
    named_pct = 100 * (total_labels - auto_labels) / total_labels if total_labels else 100.0

    print(f"Documentation coverage for {args.skool}")
    print(f"  ROUTINES     : {len(sized)} sized code routines (≥5 instructions)")
    print(f"    documented : {len(documented)} ({100*doc_frac:.0f}%) — body explained")
    print(f"    skeletal   : {len(skeletal)} — a description/summary but the body is bare")
    print(f"    bare       : {len(bare)} — no description and no line comments")
    print(f"  line density : {100*density:.0f}% of code instructions (data excluded)"
          " — a rough cross-check, not the bar")
    print(f"  CATALOG      : {graphic_sections} [Graphic:] section(s); {auto_ids} auto-label"
          f" identifier(s); {admissions} 'not-yet/unnamed' admission(s)")
    print(f"  INLINE GFX   : {inline_gfx} image macro(s) rendered in the .ctl; {catalog_gfx} in the .ref catalog"
          + ("  — sprites cataloged but NOT rendered inline at their blocks" if catalog_gfx and not inline_gfx else ""))
    print(f"  AUDIO        : {audio} #AUDIO in {audio_sections} [Audio:] section(s);"
          f" {sound} speaker/AY write(s) in code"
          + ("  — sound code present, none rendered" if sound and audio == 0 else ""))
    print(f"  INLINE AUDIO : {inline_audio} #AUDIO rendered in the .ctl"
          + ("  — all audio lives only in the .ref index; render each at its"
             " owning block" if audio and inline_audio == 0 else ""))
    print(f"  DATA TABLES  : {tables} #TABLE{'  — none documented' if tables == 0 else ''}")
    print(f"  NAMING       : {named_pct:.0f}% of labels named ({total_labels - auto_labels}/{total_labels});"
          f" {auto_labels} auto-label(s) (L####) remain — reach 100% before done")
    print(f"  RELOCATABLE  : {raw_ops} raw operand(s) into the game region (>= ${floor:04X})"
          + ("  — must be labels; the bar is ~0." if raw_ops else "")
          + " (Static proxy only — 0 here is label-clean, not proven: an absolute"
            " pointer in a data table passes every operand check. Relocatability is"
            " claimed only after the shifted program runs identically under"
            " zx-fuse-driver, recorded as its own commit. Shift the program alone,"
            " by 257 — not the whole image, and not by a multiple of 256; see"
            " references/build-verify.md.)")
    print(f"  PLACEHOLDERS : {len(placeholders)} placeholder labels"
          + (f" (e.g. {', '.join(sorted(set(placeholders))[:5])})" if placeholders else ""))
    print(f"  PROSE        : {ret_group} RET_GROUP, {selflink} SELFLINK, {diary} DIARY,"
          f" {op_echo} OPERAND_ECHO, {ellipsis} ELLIPSIS,"
          f" {open_markers} OPEN (gate the verdict); {stamp} STAMP (advisory)"
          + ("  — run `make lint-comments` for the line-level list" if prose else ""))
    print(f"  ARRAYS       : {len(unindexed)} unindexed array run(s) of >=10 records"
          + (" — " + ", ".join(f"{n} ({r} records)" for n, r in unindexed[:4])
             + (", …" if len(unindexed) > 4 else "")
             + "  (advisory: mark up record-by-record, one commented sub-line per element)"
             if unindexed else ""))

    gaps = []
    if sound and audio == 0:
        gaps.append(f"sound code present ({sound} speaker/AY writes) but 0 #AUDIO")
    if auto_ids or admissions:
        gaps.append(f"draft catalog: {auto_ids} auto-label + {admissions} unnamed/not-yet entries")
    if catalog_gfx and not inline_gfx:
        gaps.append(f"{catalog_gfx} sprites in the .ref but 0 rendered inline in the .ctl")
    if raw_ops:
        gaps.append(f"{raw_ops} raw operand(s) into the game region (non-relocatable)")
    if tables == 0:
        gaps.append("no #TABLE")
    if placeholders:
        gaps.append(f"{len(placeholders)} placeholder label(s)")
    if stamp:
        gaps.append(f"{stamp} STAMP flag(s) — review for family-head refactors")
    if unindexed:
        gaps.append(f"{len(unindexed)} unindexed array run(s) (e.g. {unindexed[0][0]}) — element-index them")

    # NOT done if most routines are unexplained, sound is unrendered or lives
    # only in the .ref index, the catalog is auto-labeled, the generated .asm
    # still has L#### auto-labels (unnamed blocks), the prose carries
    # always-wrong patterns (a RET swallowed by a comment group, a name(name)
    # self-link, investigation vocabulary in the deliverable), or a typed
    # uncertainty marker still stands — the marker is the project saying so.
    far = (doc_frac < 0.60 or (sound and audio == 0) or auto_ids > 0
           or auto_labels > 0 or (catalog_gfx and not inline_gfx)
           or (audio and inline_audio == 0) or prose_hard > 0
           or open_markers > 0)
    print()
    if far:
        reasons = []
        if doc_frac < 0.60:
            reasons.append(f"only {100*doc_frac:.0f}% of routines explained ({len(skeletal)} skeletal)")
        if catalog_gfx and not inline_gfx:
            reasons.append(f"{catalog_gfx} sprites only in the .ref, none rendered inline in the .ctl")
        if sound and audio == 0:
            reasons.append("sound code unrendered (0 #AUDIO)")
        if auto_ids > 0:
            reasons.append(f"{auto_ids} catalog entries still auto-labeled, not named")
        if auto_labels > 0:
            reasons.append(f"labels {named_pct:.0f}% named — {auto_labels} L#### auto-labels remain")
        if audio and inline_audio == 0:
            reasons.append(f"{audio} #AUDIO only in the .ref index, none inline at their blocks")
        if prose_hard:
            reasons.append(f"prose not at the bar ({ret_group} RET_GROUP, {selflink} SELFLINK,"
                           f" {diary} DIARY, {op_echo} OPERAND_ECHO, {ellipsis} ELLIPSIS)")
        if open_markers:
            reasons.append(f"{open_markers} typed uncertainty marker(s) still standing "
                           "— each is an underived claim with a dig-task owed")
        print("VERDICT: NOT at the bar — " + "; ".join(reasons)
              + ". Do not call it mature/done; this is the upgrade backlog.")
    else:
        print(f"VERDICT: {100*doc_frac:.0f}% of routines explained, sound rendered, catalog named"
              " — at or near the bar.")
    if gaps and not far:
        print("Residual gaps: " + "; ".join(gaps) + ".")
    elif gaps:
        print("Open gaps: " + "; ".join(gaps) + ".")
    print("(This is a floor check. Whether each comment is correct, whether the"
          " catalogs and behavior spec are complete and code-derived, and whether the"
          " code is *actually* relocatable — proven by reassembling at a shifted ORG and"
          " running it under the emulator (zx-fuse-driver), not by a label-clean static"
          " read — is beyond this gauge.)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
