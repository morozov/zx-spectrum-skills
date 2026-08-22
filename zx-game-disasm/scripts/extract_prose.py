#!/usr/bin/env python3
"""
Lift a disassembly's prose into one Markdown file that Vale can read, and record
where every line came from.

Vale is the prose linter the technical-writing world uses, and it ships the
Microsoft and Google style guides as executable rules. It cannot read this
project's prose: a `.skool` is neither Markdown nor one of the 23 languages whose
comments Vale extracts, and `.vale.ini`'s `[formats]` section only renames an
extension, so mapping `.skool` to Markdown would lint the Z80 listing itself.

So this lifts the prose out. Every block comment, instruction comment, `.ctl`
annotation and `.ref` paragraph becomes a Markdown paragraph, and `prose.map.json`
records which source file and line each output line came from. `vale_report.py`
runs Vale over the result and translates the positions back, so a finding still
lands on `game.skool:7830`.

Emitted Markdown is deliberately plain: no headings, no lists, no tables. A
paragraph per prose unit, blank line between. Vale's `scope: sentence` then works
across SkoolKit's hard-wrapped lines, because Markdown joins them.

Usage:
    extract_prose.py --out prose.md --map prose.map.json FILE [FILE ...]
"""

import argparse
import json
import os
import re
import sys

# --- Macro scrubbing ---------------------------------------------------------
#
# SkoolKit macros are not prose and must not reach the linter, with one
# exception: the address in `#R$XXXX` is what AddressDensity and NamedHex count,
# so that macro is reduced to the bare address rather than removed. Everything
# else goes. Span macros are cleared first, and always to the same number of
# newlines, so the line map stays aligned.

# A span macro opens its own line in every SkoolKit file that uses one, so the
# open is anchored. Unanchored, a sentence that merely *mentions* `#TABLE` opens
# a span that swallows everything up to the next real `TABLE#` — which is one
# paragraph of prose about the macro eating six blocks of prose around it.
SPAN_MACRO_RE = re.compile(r'^[ \t]*(?:;[ \t]*)?#(?:UDGTABLE|TABLE|LIST)\b'
                           r'.*?(?:TABLE#|LIST#)', re.S | re.M)
HTML_MACRO_RE = re.compile(r'#HTML\[.*?\]', re.S)
REF_MACRO_RE = re.compile(r'#R\$?([0-9A-Fa-f]{4,5})')
REG_MACRO_RE = re.compile(r'#REG([a-z]+)')
NUM_MACRO_RE = re.compile(r'#N(\d+)(?:,[^ )]*)?')
# `#MACRO<params>(text)`: the parameter list carries no spaces and runs straight
# into the parenthesized arguments, so both have to go. Leaving the parameters
# behind turns `#UDGARRAY2,7($9000)(thing)` into `,7($9000)(thing)`.
WORD_MACRO_RE = re.compile(r'#[A-Z][A-Za-z0-9]*(?:[:#][A-Za-z0-9_]+)?'
                           r'[0-9A-Za-z,=$.+*-]*'
                           r'(?:\((?:[^()]|\([^()]*\))*\))*'
                           r'(?:\[[^\]]*\])?')
HTML_TAG_RE = re.compile(r'</?[a-zA-Z][^>]*>')
ENTITY_RE = re.compile(r'&[a-z]+;')


def blank_span(match):
    """Replace a matched span with the newlines it contained, and nothing else."""
    return '\n' * match.group(0).count('\n')


def scrub(text):
    """Strip markup from a whole document without changing its line count."""
    text = SPAN_MACRO_RE.sub(blank_span, text)
    text = HTML_MACRO_RE.sub(blank_span, text)
    text = REF_MACRO_RE.sub(lambda m: '$' + m.group(1), text)
    text = REG_MACRO_RE.sub(lambda m: m.group(1).upper(), text)
    text = NUM_MACRO_RE.sub(lambda m: m.group(1), text)
    text = WORD_MACRO_RE.sub('', text)
    text = HTML_TAG_RE.sub('', text)
    text = ENTITY_RE.sub(' ', text)
    return text


# --- Source formats ----------------------------------------------------------

SKOOL_BLOCK_RE = re.compile(r'^;\s?(?P<text>.*)$')
SKOOL_INSTR_RE = re.compile(r'^(?P<ctrl>[ cbtwsgi*@])?[$]?(?P<addr>[0-9A-Fa-f]{4})\s+(?P<body>.*)$')
CONTINUATION_RE = re.compile(r'^\s+;\s?(?P<text>.*)$')
CTL_PROSE_RE = re.compile(r'^(?P<kind>[DNRE]) \$[0-9A-Fa-f]{4}(?:,\S*)? (?P<text>.*)$')
CTL_TITLE_RE = re.compile(r'^(?P<kind>[cbgtuwsi]) \$[0-9A-Fa-f]{4} (?P<text>.+)$')
REF_SECTION_RE = re.compile(r'^\[[^\]]+\]\s*$')
REF_CONFIG_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*=')


def instruction_comment(body):
    """Return the comment text on an instruction row, or None."""
    # The operand field can carry a ';' only inside a string literal, which this
    # disassembly's rows do not use; splitting on the first ';' is therefore safe.
    if ';' not in body:
        return None
    return body.split(';', 1)[1].strip()


def units_from_skool(lines):
    """Yield (kind, [(lineno, text), ...]) prose units from a .skool file.

    Three shapes carry prose, and a sentence runs across the rows of any of them:
    a block comment at column 0, an instruction comment braced over several rows,
    and an instruction comment continued on indented `;` rows that carry no
    address. Dropping the third truncates sentences mid-clause, which makes every
    sentence-scoped check report on half a sentence.
    """
    para, kind, in_group = [], None, False

    def flush():
        return (kind, para) if para else None

    for n, raw in enumerate(lines, 1):
        block = SKOOL_BLOCK_RE.match(raw)
        if block:
            done = flush() if kind != 'block' else None
            if done:
                yield done
                para, kind, in_group = [], None, False
            text = block.group('text').rstrip()
            # A lone '.' is SkoolKit's paragraph break; a bare ';' separates the
            # entry title from its description. Both end the unit.
            if text in ('.', ''):
                if para:
                    yield kind, para
                para, kind = [], None
                continue
            if not para:
                kind = 'block'
            para.append((n, text))
            continue

        if kind == 'block' and para:
            yield kind, para
            para, kind = [], None

        if not raw.strip():
            if para:
                yield kind, para
            para, kind, in_group = [], None, False
            continue
        if raw.lstrip().startswith('@'):
            continue                      # a directive may sit inside a group

        instr = SKOOL_INSTR_RE.match(raw)
        if instr:
            comment = instruction_comment(instr.group('body'))
            if comment is None:
                if para and not in_group:
                    yield kind, para
                    para, kind = [], None
                continue
            opens = comment.startswith('{')
            closes = comment.rstrip().endswith('}')
            text = comment.strip('{}').strip()
            if opens or not in_group:
                if para:
                    yield kind, para
                para, kind = [], 'instr'
                in_group = opens and not closes
            if text:
                para.append((n, text))
            if closes and para:
                yield kind, para
                para, kind, in_group = [], None, False
            continue

        # An indented ';' row with no address continues the comment above it.
        cont = CONTINUATION_RE.match(raw)
        if cont:
            text = cont.group('text').strip()
            closes = text.endswith('}')
            text = text.strip('{}').strip()
            if not para:
                kind = 'instr'
            if text:
                para.append((n, text))
            if closes and para:
                yield kind, para
                para, kind, in_group = [], None, False
            continue

        if para:
            yield kind, para
        para, kind, in_group = [], None, False
    if para:
        yield kind, para


def units_from_ctl(lines):
    """Yield prose units from a .ctl control file, one per directive run."""
    para, kind = [], None
    for n, raw in enumerate(lines, 1):
        match = CTL_PROSE_RE.match(raw) or CTL_TITLE_RE.match(raw)
        if not match:
            if para:
                yield kind, para
            para, kind = [], None
            continue
        this = match.group('kind')
        if this != kind and para:
            yield kind, para
            para = []
        kind = this
        para.append((n, match.group('text').rstrip()))
    if para:
        yield kind, para


def units_from_ref(lines):
    """Yield prose units from a .ref page, skipping config and section headers."""
    para = []
    for n, raw in enumerate(lines, 1):
        text = raw.rstrip()
        if not text.strip() or REF_SECTION_RE.match(text) or REF_CONFIG_RE.match(text) \
                or text.lstrip().startswith(';'):
            if para:
                yield 'ref', para
            para = []
            continue
        para.append((n, text.strip()))
    if para:
        yield 'ref', para


def units_from_markdown(lines):
    """Yield prose units from a plain Markdown file, skipping fenced code."""
    para, fenced = [], False
    for n, raw in enumerate(lines, 1):
        text = raw.rstrip()
        if text.lstrip().startswith('```'):
            fenced = not fenced
            if para:
                yield 'spec', para
            para = []
            continue
        if fenced or not text.strip() or text.lstrip().startswith('#'):
            if para:
                yield 'spec', para
            para = []
            continue
        para.append((n, text.strip()))
    if para:
        yield 'spec', para


READERS = {
    '.skool': units_from_skool,
    '.ctl': units_from_ctl,
    '.ref': units_from_ref,
    '.md': units_from_markdown,
}


def read_units(path):
    """Return the prose units of one source file, with its markup already gone."""
    reader = READERS.get(os.path.splitext(path)[1])
    if reader is None:
        raise SystemExit('extract_prose: no reader for %s' % path)
    with open(path, encoding='utf-8', errors='replace') as handle:
        lines = scrub(handle.read()).split('\n')
    return reader(lines)


# --- Emission ----------------------------------------------------------------

def emit(paths, out_path, map_path, print_map=False):
    """Write the Markdown and its line map. Return the number of units emitted.

    `out_path` of '-' writes the Markdown to stdout and nothing else there, so a
    fixture can diff it. `print_map` writes the map as one sortable line per
    entry instead of JSON, for the same reason: the map is the half of this
    script a silent regression would land in, and JSON does not diff usefully.
    """
    out, mapping, units = [], {}, 0
    for path in paths:
        for kind, para in read_units(path):
            body = [(n, t) for n, t in para if t.strip()]
            if not body:
                continue
            units += 1
            for lineno, text in body:
                # A leading '>' or '-' would turn the line into Markdown
                # structure; the prose never means it as one.
                if text[:1] in '>-*+#|=':
                    text = '\\' + text
                out.append(text)
                mapping[str(len(out))] = [path, lineno, kind]
            out.append('')
    text = '\n'.join(out) + '\n'
    if out_path == '-':
        sys.stdout.write(text)
    else:
        with open(out_path, 'w', encoding='utf-8') as handle:
            handle.write(text)
    if print_map:
        for line in sorted(mapping, key=int):
            path, lineno, kind = mapping[line]
            sys.stdout.write('%s\t%s:%s\t%s\n' % (line, path, lineno, kind))
    elif map_path != '-':
        with open(map_path, 'w', encoding='utf-8') as handle:
            json.dump(mapping, handle)
    return units


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('--out', required=True, help='Markdown file to write')
    parser.add_argument('--map', required=True,
                        help="line map (JSON) to write; '-' to write none")
    parser.add_argument('--print-map', action='store_true',
                        help='write the map to stdout as text instead of JSON')
    parser.add_argument('sources', nargs='+', help='.skool, .ctl, .ref or .md files')
    args = parser.parse_args()

    present = [p for p in args.sources if os.path.exists(p)]
    if not present:
        raise SystemExit('extract_prose: none of the named sources exist')
    units = emit(present, args.out, args.map, args.print_map)
    if args.out != '-' and not args.print_map:
        print('extract_prose: %d prose units from %d files -> %s'
              % (units, len(present), args.out), file=sys.stderr)


if __name__ == '__main__':
    main()
