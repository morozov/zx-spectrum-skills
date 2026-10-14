#!/usr/bin/env python3
"""
Every piece of reader-facing prose in a project, as one stream of units.

A unit is one thing a reader meets as a whole: an entry title, a description
paragraph, a row comment or a '{ }' comment group, a register row, a `.ref`
paragraph, a heading, one table cell, a glossary term's title or its body. Each
carries the surface it came from, so a check declares the surfaces it reads and
runs over every unit of those surfaces in every file. A check that reads only
`.skool` block comments, or only `.ref` lines that are not table rows, misses the
same defect on the surfaces it skips, and the gate passes over it.

Surfaces:

  title        an entry title (`.skool` header, `.ctl` entry line)
  block        a description paragraph, start comment or mid-entry note
  register     one register row of an entry header
  row          an instruction comment or '{ }' group over code
  data-row     an instruction comment or group over data directives only
  ref-para     a `.ref` or Markdown paragraph
  ref-heading  a page heading: `<hN>`, `[Page:]`, `SectionName=`, an entry
               section's title, a `[PageHeaders]`/`[Titles]`/`[Links]` value
  table-cell   one cell of a `#TABLE`, `#UDGTABLE` or HTML table
  list-item    one item of a `#LIST`
  term-title   a glossary term's title
  term-body    a glossary term's definition

A unit's `text` has its SkoolKit macros and HTML scrubbed: render and sound
macros go entirely, with their parameters, and leave a flag; a link keeps its
link text; `#R$XXXX` stays as written, so a check can tell a reference to code
from a word. `.ref` lines starting with ';' are not published and are not units.

Usage as a script: prose_units.py FILE … prints one line per unit, for a fixture.
"""

import html
import os
import re
import sys
from bisect import bisect_right

PROSE_SURFACES = frozenset((
    'title', 'block', 'register', 'row', 'data-row', 'ref-para', 'ref-heading',
    'table-cell', 'list-item', 'term-title', 'term-body'))

RENDER_MACROS = frozenset(('UDG', 'UDGARRAY', 'FONT', 'SCR', 'FRAMES', 'PLOT', 'COPY'))
SPAN_OPEN_RE = re.compile(r'#(TABLE|UDGTABLE|LIST)\b(?:\([^)]*\)|<[^>]*>)?')
SPAN_CLOSE_RE = re.compile(r'(TABLE|LIST)#')


class Unit:
    """One prose unit. `segs` maps offsets in `raw` back to source lines."""

    __slots__ = ('surface', 'path', 'raw', 'text', 'posmap', 'segs', 'ctx',
                 'render', 'audio')

    def __init__(self, surface, path, raw, segs, ctx):
        self.surface = surface
        self.path = path
        self.raw = raw
        self.segs = segs            # [(raw offset, lineno, display)], sorted
        self.ctx = ctx
        self.text, self.posmap, flags = scrub(raw)
        self.render = 'render' in flags
        self.audio = 'audio' in flags

    @property
    def lineno(self):
        return self.segs[0][1]

    @property
    def display(self):
        return self.segs[0][2]

    def locate(self, text_offset):
        """Return (lineno, display) for an offset into `text`."""
        if not self.posmap:
            return self.segs[0][1], self.segs[0][2]
        raw_offset = self.posmap[min(max(text_offset, 0), len(self.posmap) - 1)]
        starts = [s[0] for s in self.segs]
        index = max(0, bisect_right(starts, raw_offset) - 1)
        return self.segs[index][1], self.segs[index][2]

    def __repr__(self):
        return f'Unit({self.surface}, {self.path}:{self.lineno}, {self.text!r})'


# --- Macro and markup scrubbing ----------------------------------------------

MACRO_NAME_RE = re.compile(r'[A-Z]+')
REF_ARG_RE = re.compile(r'(\$[0-9A-Fa-f]+|\d+)(@[\w-]+)?(#[\w-]+)?')
NUM_ARG_RE = re.compile(r'(\$[0-9A-Fa-f]+|\d+)(?:,[^\s()]*)?')
GENERIC_PARAM_RE = re.compile(r'[^\s()\[\]{}|]*')
TAG_RE = re.compile(r'</?[A-Za-z][^>]*>')
SAMP_TAG_RE = re.compile(r'</?samp\b', re.I)
ENTITY_RE = re.compile(r'&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z]+);')


def balanced(s, i, open_ch='(', close_ch=')'):
    """Return the index past the group opening at s[i], or None."""
    if i >= len(s) or s[i] != open_ch:
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == open_ch:
            depth += 1
        elif s[j] == close_ch:
            depth -= 1
            if depth == 0:
                return j + 1
    return None


def scrub(s):
    """Strip macros and markup from `s`.

    Returns (text, posmap, flags): `posmap[i]` is the offset in `s` that
    produced `text[i]`, and `flags` holds 'render' or 'audio' when the unit
    carried such a macro.
    """
    out, pos, flags = [], [], set()

    def emit(chunk, at):
        for ch in chunk:
            out.append(ch)
            pos.append(at)

    def emit_scrubbed(inner, base):
        text, inner_pos, inner_flags = scrub(inner)
        flags.update(inner_flags)
        out.extend(text)
        pos.extend(base + p for p in inner_pos)

    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '#' and i + 1 < n and s[i + 1].isupper():
            m = MACRO_NAME_RE.match(s, i + 1)
            name = m.group(0)
            j = m.end()
            if name.startswith('REG') and j < n and (s[j].islower() or s[j] == "'"):
                rm = re.compile(r"[a-z']+").match(s, j)
                emit(rm.group(0).upper(), i)
                i = rm.end()
                continue
            if name == 'R':
                am = REF_ARG_RE.match(s, j)
                if am:
                    k = am.end()
                    end = balanced(s, k)
                    if end:
                        emit_scrubbed(s[k + 1:end - 1], k + 1)
                        i = end
                    else:
                        token = am.group(1)
                        addr = (token[1:].upper() if token.startswith('$')
                                else f'{int(token):04X}')
                        emit('#R$' + addr, i)
                        i = k
                    continue
            if name == 'N':
                am = NUM_ARG_RE.match(s, j)
                if am:
                    emit(am.group(1), i)
                    i = am.end()
                    continue
            if name == 'CHR':
                am = re.compile(r'\(?(\d+)\)?').match(s, j)
                if am:
                    emit(chr(int(am.group(1))), i)
                    i = am.end()
                    continue
            if name == 'LINK':
                k = j
                if k < n and s[k] == ':':
                    k = re.compile(r':[\w#.-]+').match(s, k).end()
                else:
                    k = balanced(s, k) or k
                end = balanced(s, k)
                if end:
                    emit_scrubbed(s[k + 1:end - 1], k + 1)
                    i = end
                else:
                    i = k
                continue
            if name == 'HTML':
                for o, cl in (('(', ')'), ('[', ']')):
                    end = balanced(s, j, o, cl)
                    if end:
                        emit_scrubbed(s[j + 1:end - 1], j + 1)
                        i = end
                        break
                else:
                    i = j
                continue
            if name == 'SPACE':
                am = re.compile(r'\d*').match(s, j)
                emit(' ', i)
                i = am.end()
                continue
            if name in RENDER_MACROS:
                flags.add('render')
            elif name == 'AUDIO':
                flags.add('audio')
            k = GENERIC_PARAM_RE.match(s, j).end()
            while k < n and s[k] in '([':
                end = balanced(s, k, s[k], ')' if s[k] == '(' else ']')
                if not end:
                    break
                k = end
            emit(' ', i)
            i = k
            continue
        if c in 'TL':
            cm = SPAN_CLOSE_RE.match(s, i)
            if cm and (i == 0 or not s[i - 1].isalnum()):
                emit(' ', i)
                i = cm.end()
                continue
        if c == '<':
            tm = TAG_RE.match(s, i)
            if tm:
                # A <samp> element holds the game's own text, so it reads as
                # quoted game text, which keeps its bytes (TYPO-2).
                emit('"' if SAMP_TAG_RE.match(tm.group(0)) else ' ', i)
                i = tm.end()
                continue
        if c == '&':
            em = ENTITY_RE.match(s, i)
            if em:
                emit(html.unescape(em.group(0)), i)
                i = em.end()
                continue
        emit(c, i)
        i += 1
    return ''.join(out), pos, flags


# --- Tables inside a paragraph -----------------------------------------------

def split_depth0(s, sep, start, end):
    """Split s[start:end] on `sep` at parenthesis depth 0; return (a, b) spans."""
    parts, depth, last = [], 0, start
    for k in range(start, end):
        ch = s[k]
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth = max(0, depth - 1)
        elif ch == sep and depth == 0:
            parts.append((last, k))
            last = k + 1
    parts.append((last, end))
    return parts


CELL_MARKUP_RE = re.compile(r'\s*=([\w,]+)\s')


def table_rows(s, start, end):
    """Yield the (start, end) spans of the '{ … }' rows in s[start:end]."""
    depth, k = 0, start
    while k < end:
        ch = s[k]
        if ch == '{' and depth == 0:
            inner, d = k + 1, 0
            m = k + 1
            while m < end:
                if s[m] in '([':
                    d += 1
                elif s[m] in ')]':
                    d = max(0, d - 1)
                elif s[m] == '}' and d == 0:
                    break
                m += 1
            yield inner, m
            k = m + 1
            continue
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth = max(0, depth - 1)
        k += 1


def paragraph_units(path, raw, segs, surface, ctx, cell_surface='table-cell'):
    """Split one paragraph into its prose unit and its table cells.

    `raw` is the paragraph's text, `segs` its line map. Text outside a
    `#TABLE`/`#UDGTABLE`/`#LIST` span is one unit of `surface`; each cell is a
    unit of its own.
    """
    units = []
    outside, cursor = [], 0
    for om in SPAN_OPEN_RE.finditer(raw):
        if om.start() < cursor:
            continue
        cm = SPAN_CLOSE_RE.search(raw, om.end())
        close = cm.start() if cm else len(raw)
        outside.append((cursor, om.start()))
        kind = om.group(1)
        for row_index, (rs, re_) in enumerate(table_rows(raw, om.end(), close)):
            cells = split_depth0(raw, '|', rs, re_)
            for col, (cs, ce) in enumerate(cells):
                header = False
                mm = CELL_MARKUP_RE.match(raw, cs)
                if mm and mm.start() == cs:
                    header = 'h' in mm.group(1).split(',')
                    cs = mm.end()
                cell_ctx = dict(ctx, table=kind, col=col, row=row_index, header=header)
                unit_surface = 'list-item' if kind == 'LIST' else cell_surface
                units.append(make_unit(unit_surface, path, raw, cs, ce, segs, cell_ctx))
        cursor = cm.end() if cm else len(raw)
    outside.append((cursor, len(raw)))
    pieces = [(a, b) for a, b in outside if raw[a:b].strip()]
    if pieces:
        # The text either side of a table is one unit: the sentence introducing
        # a table and the one after it sit in one paragraph on the page. The
        # table itself is blanked to spaces, so offsets still map to lines.
        units.insert(0, make_unit(surface, path, _blank_spans(raw, outside),
                                  pieces[0][0], pieces[-1][1], segs, ctx))
    return [u for u in units if u.text.strip()]


def _blank_spans(raw, outside):
    """`raw` with everything but the `outside` spans blanked to spaces."""
    chars = [' '] * len(raw)
    for a, b in outside:
        chars[a:b] = raw[a:b]
    return ''.join(chars)


def make_unit(surface, path, raw, start, end, segs, ctx):
    """A unit over raw[start:end], with the line map rebased onto the slice."""
    starts = [s[0] for s in segs]
    first = max(0, bisect_right(starts, start) - 1)
    kept = []
    for offset, lineno, display in segs[first:]:
        if offset >= end and kept:
            break
        kept.append((max(0, offset - start), lineno, display))
    return Unit(surface, path, raw[start:end], kept, ctx)


def join_lines(lines):
    """Join [(lineno, text, display)] into (raw, segs), one space per break."""
    raw, segs = '', []
    for lineno, text, display in lines:
        if raw:
            raw += ' '
        segs.append((len(raw), lineno, display))
        raw += text
    return raw, segs


# --- .skool ------------------------------------------------------------------

INSTR_RE = re.compile(
    r'^(?P<ctrl>[ bcgistuw*])(?P<addr>\$[0-9A-Fa-f]{4}|\d{5})\s(?P<body>.*)$')
CONT_RE = re.compile(r'^\s+;(?P<text>.*)$')
REGISTER_RE = re.compile(r'^\s*[IO]:')
GENERATED_RE = re.compile(r'(?i)^this entry point is used by the routines? at\b')
DATA_DIRECTIVE_RE = re.compile(r'^(DEFB|DEFW|DEFM|DEFS)\b', re.I)
ENTRY_CTRLS = 'bcgistuw'


class Entry:
    """One `.skool` entry: what its units need to know about it."""

    __slots__ = ('type', 'addr', 'label', 'title', 'audio', 'rows', 'length')

    def __init__(self):
        self.type = None
        self.addr = None
        self.label = None
        self.title = ''
        self.audio = False
        self.rows = []          # (addr, instruction)
        self.length = 0

    def __repr__(self):
        return f'Entry({self.type}{self.addr} {self.label})'


def split_instruction(body):
    """Split an instruction body into (instruction, comment or None)."""
    in_quote = False
    for k in range(len(body)):
        ch = body[k]
        if ch == '"':
            in_quote = not in_quote
        elif ch == ';' and not in_quote and (k == 0 or body[k - 1] == ' '):
            return body[:k].rstrip(), body[k + 1:].strip()
    return body.rstrip(), None


def directive_length(instr):
    """The number of bytes a data directive assembles to, or 0."""
    parts = instr.split(None, 1)
    if not parts:
        return 0
    op = parts[0].upper()
    args = parts[1] if len(parts) > 1 else ''
    if op == 'DEFS':
        first = args.split(',')[0].strip()
        try:
            return int(first[1:], 16) if first.startswith('$') else int(first)
        except ValueError:
            return 0
    if op not in ('DEFB', 'DEFW', 'DEFM'):
        return 0
    total = 0
    for item in re.findall(r'"(?:[^"\\]|\\.)*"|[^,]+', args):
        item = item.strip()
        if item.startswith('"'):
            total += len(item) - 2
        elif item:
            total += 2 if op == 'DEFW' else 1
    return total


def skool_units(path, lines):
    """Yield the prose units of a `.skool` file, with each entry's context."""
    units = []
    labels = {}             # address -> label
    entries = []            # every Entry, in file order
    pending_label = None
    entry = None
    group = None            # the open '{ }' group or row unit being built
    index, total = 0, len(lines)

    def ctx_for(e, **extra):
        d = {'entry': e}
        d.update(extra)
        return d

    def close_group():
        nonlocal group
        if group and group['lines']:
            surface = 'data-row' if group['data'] else 'row'
            raw, segs = join_lines(group['lines'])
            ctx = ctx_for(group['entry'], instrs=group['instrs'], addrs=group['addrs'],
                          grouped=group['braced'])
            units.extend(paragraph_units(path, raw, segs, surface, ctx))
        group = None

    def header_units(block, e, is_header):
        """Units of one run of column-0 comment lines.

        `run_audio` marks every unit of a run that renders a sound, because the
        prose beside a clip is the prose the clip already speaks for.
        """
        run_audio = any('#AUDIO' in t for _, t in block)
        if run_audio:
            e.audio = True
        if not is_header:
            paragraphs, para = [], []
            for lineno, text in block:
                if text.strip() in ('', '.'):
                    if para:
                        paragraphs.append(para)
                    para = []
                else:
                    para.append((lineno, text))
            if para:
                paragraphs.append(para)
            for para in paragraphs:
                joined = ' '.join(t for _, t in para)
                if GENERATED_RE.match(joined.strip()):
                    continue
                raw, segs = join_lines([(l, t, t.strip()) for l, t in para])
                units.extend(paragraph_units(path, raw, segs, 'block',
                                             ctx_for(e, note=True, run_audio=run_audio)))
            return
        sections, section = [], []
        for lineno, text in block:
            if text.strip() == '':
                sections.append(section)
                section = []
            else:
                section.append((lineno, text))
        sections.append(section)
        for number, section in enumerate(sections):
            if not section:
                continue
            if number == 0:
                e.title = ' '.join(t.strip() for _, t in section)
                raw, segs = join_lines([(l, t, t.strip()) for l, t in section])
                units.extend(paragraph_units(path, raw, segs, 'title',
                                             ctx_for(e, run_audio=run_audio)))
                continue
            paragraph = []
            for lineno, text in section + [(None, '.')]:
                register = number == 2 and len(sections) > 2 or REGISTER_RE.match(text)
                if text.strip() == '.' or register:
                    if paragraph:
                        joined = ' '.join(t for _, t in paragraph)
                        if not GENERATED_RE.match(joined.strip()):
                            raw, segs = join_lines([(l, t, t.strip()) for l, t in paragraph])
                            units.extend(paragraph_units(
                                path, raw, segs, 'block',
                                ctx_for(e, header_section=number, run_audio=run_audio)))
                        paragraph = []
                    if register and lineno is not None and text.strip() != '.':
                        units.append(Unit('register', path, text.strip(),
                                          [(0, lineno, text.strip())],
                                          ctx_for(e, run_audio=run_audio)))
                    continue
                paragraph.append((lineno, text))

    while index < total:
        line = lines[index].rstrip('\n')
        if line.startswith(';'):
            close_group()
            block = []
            while index < total and lines[index].startswith(';'):
                text = lines[index].rstrip('\n')[1:]
                block.append((index + 1, text[1:] if text.startswith(' ') else text))
                index += 1
            # A header is attached to the entry row that follows it, with only
            # directives between. A run followed by a blank line is a comment
            # SkoolKit does not publish.
            look = index
            while look < total and lines[look].startswith('@'):
                look += 1
            nxt = lines[look].rstrip('\n') if look < total else ''
            im = INSTR_RE.match(nxt)
            if im and im.group('ctrl') in ENTRY_CTRLS:
                new = Entry()
                header_units(block, new, True)
                entry = new
                entries.append(new)
            elif im and entry is not None:
                header_units(block, entry, False)
            # A run attached to no row is not published, so it is not a unit.
            continue
        if line.startswith('@'):
            lm = re.match(r'^@label=(\S+)', line)
            if lm:
                pending_label = lm.group(1)
            index += 1
            continue
        im = INSTR_RE.match(line)
        if im:
            ctrl, addr = im.group('ctrl'), im.group('addr')
            hexaddr = (addr[1:].upper() if addr.startswith('$') else f'{int(addr):04X}')
            if ctrl in ENTRY_CTRLS:
                close_group()
                if entry is None or entry.addr is not None:
                    entry = Entry()
                    entries.append(entry)
                entry.type, entry.addr = ctrl, hexaddr
                entry.label = pending_label
            if pending_label:
                labels[hexaddr] = pending_label
                pending_label = None
            instr, comment = split_instruction(im.group('body'))
            if entry is not None:
                entry.rows.append((hexaddr, instr))
                entry.length += directive_length(instr)
            is_data = bool(DATA_DIRECTIVE_RE.match(instr.strip()))
            display = line.strip()
            if comment is None:
                if group and not group['braced']:
                    close_group()
                elif group:
                    group['instrs'].append(instr)
                    group['addrs'].append(hexaddr)
                    group['data'] = group['data'] and is_data
                index += 1
                continue
            opens = comment.startswith('{')
            closes = comment.endswith('}')
            text = comment.lstrip('{').rstrip('}').strip()
            if group and group['braced'] and not opens:
                group['instrs'].append(instr)
                group['addrs'].append(hexaddr)
                group['data'] = group['data'] and is_data
                if text:
                    group['lines'].append((index + 1, text, display))
            else:
                close_group()
                group = {'entry': entry, 'lines': [], 'instrs': [instr],
                         'addrs': [hexaddr], 'data': is_data, 'braced': opens}
                if text:
                    group['lines'].append((index + 1, text, display))
            if closes:
                close_group()
            index += 1
            continue
        cm = CONT_RE.match(line)
        if cm and group is not None:
            text = cm.group('text').strip()
            closes = text.endswith('}')
            text = text.lstrip('{').rstrip('}').strip()
            if text:
                group['lines'].append((index + 1, text, line.strip()))
            if closes:
                close_group()
            index += 1
            continue
        # A blank line, or anything else, ends the group and the entry.
        close_group()
        if not line.strip():
            entry = None
        index += 1
    close_group()
    return units, labels, entries


# --- .ctl --------------------------------------------------------------------

CTL_TITLE_RE = re.compile(r'^(?P<type>[bcgistuw]) (?P<addr>\$[0-9A-Fa-f]{4}|\d{5}) (?P<text>.+)$')


def ctl_units(path, lines):
    """A `.ctl` file's entry titles. Its other prose reaches the `.skool`."""
    units = []
    for lineno, raw in enumerate(lines, 1):
        m = CTL_TITLE_RE.match(raw.rstrip('\n'))
        if not m:
            continue
        e = Entry()
        e.type, e.addr = m.group('type'), m.group('addr').lstrip('$').upper()
        e.title = m.group('text').strip()
        units.append(Unit('title', path, e.title, [(0, lineno, raw.strip())],
                          {'entry': e}))
    return units


# --- .ref --------------------------------------------------------------------

SECTION_RE = re.compile(r'^\[(?P<name>[^\]]+)\]\s*$')
CONFIG_RE = re.compile(r'^(?P<key>[A-Za-z][A-Za-z0-9_-]*)=(?P<value>.*)$')
HEADING_TAG_RE = re.compile(r'<h([1-6])[^>]*>(?P<text>.*?)</h\1>')
CELL_TAG_RE = re.compile(r'<(?P<tag>td|th|caption)\b[^>]*>(?P<text>.*?)</(?P=tag)>')
# Sections SkoolKit reads as configuration, not as page text. Their values are
# keys, file names, templates and page ids; the heading-valued ones are read
# separately. `TerminologyRegistry` is the registry `validate_glossary_terms.py`
# reads, which renders nothing.
CONFIG_SECTIONS = frozenset((
    'Config', 'Game', 'ImageWriter', 'Resources', 'Index', 'Paths', 'Colours',
    'Colors', 'OtherCode', 'Template', 'MemoryMap', 'Expand', 'Replace',
    'PageHeaders', 'Titles', 'Links', 'TerminologyRegistry', 'Page'))
HEADING_VALUE_SECTIONS = frozenset(('PageHeaders', 'Titles', 'Links'))
GLOSSARY_PREFIXES = {'Glossary', 'Term'}
# A line opening on one of these is running text that starts with markup, such
# as `<i>every</i> frame…`, and continues the paragraph.
INLINE_TAG_RE = re.compile(
    r'^<(?:i|b|em|strong|code|a|span|sup|sub|kbd|var|small|abbr|br|tt|u)\b', re.I)


def ref_units(path, lines):
    """Yield the prose units of a `.ref` page."""
    units = []
    # Prefixes declared by a glossary page are glossary entries wherever they sit.
    glossary = set(GLOSSARY_PREFIXES)
    audio_sections = set()
    current = None
    for raw in lines:
        sm = SECTION_RE.match(raw.strip())
        if sm:
            current = sm.group('name')
            continue
        if '#AUDIO' in raw and not raw.lstrip().startswith(';'):
            audio_sections.add(current)
        cm = CONFIG_RE.match(raw.strip())
        if current and current.startswith('Page:') and cm and cm.group('key') == 'SectionPrefix':
            if 'gloss' in current.lower():
                glossary.add(cm.group('value').strip())

    section, parts = None, []
    para = []                 # [(lineno, text, display)]
    open_span = False
    in_row, col = False, 0

    def flush(surface):
        nonlocal para
        if para:
            raw_text, segs = join_lines(para)
            units.extend(paragraph_units(path, raw_text, segs, surface,
                                         {'section': section}))
        para = []

    def body_surface():
        return 'term-body' if parts and parts[0] in glossary and len(parts) >= 2 else 'ref-para'

    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip('\n')
        stripped = line.strip()
        sm = SECTION_RE.match(stripped)
        if sm:
            flush(body_surface())
            section = sm.group('name')
            parts = section.split(':')
            open_span = False
            if parts[0] == 'Page' and len(parts) > 1:
                units.append(Unit('ref-heading', path, parts[1],
                                  [(0, lineno, stripped)], {'section': section}))
            elif parts[0] == 'Index' and len(parts) > 2:
                units.append(Unit('ref-heading', path, parts[2],
                                  [(0, lineno, stripped)], {'section': section}))
            elif parts[0] not in CONFIG_SECTIONS and len(parts) >= 2:
                title = parts[-1] if len(parts) >= 3 else parts[1]
                surface = 'term-title' if parts[0] in glossary else 'ref-heading'
                units.append(Unit(surface, path, title, [(0, lineno, stripped)],
                                  {'section': section}))
            continue
        if section is None:
            continue
        if stripped.startswith(';'):
            continue                      # not published
        head = parts[0]
        if head in CONFIG_SECTIONS:
            cm = CONFIG_RE.match(stripped)
            if not cm:
                continue
            value = cm.group('value').strip()
            if (head in HEADING_VALUE_SECTIONS or cm.group('key') == 'SectionName') \
                    and value and '{' not in value and '#' not in value:
                units.append(Unit('ref-heading', path, value, [(0, lineno, stripped)],
                                  {'section': section}))
            continue
        if not stripped:
            if not open_span:
                flush(body_surface())
            continue
        if not re.search(r'[A-Za-z]', stripped):
            continue                      # a delay list, a bare number run
        if not open_span and stripped.startswith('<') and not INLINE_TAG_RE.match(stripped):
            flush(body_surface())
            hm = HEADING_TAG_RE.search(stripped)
            if hm:
                start = hm.start('text')
                units.append(make_unit('ref-heading', path, stripped, start,
                                       hm.end('text'), [(0, lineno, stripped)],
                                       {'section': section}))
                continue
            if re.match(r'<tr\b', stripped):
                in_row, col = True, 0
            cells = list(CELL_TAG_RE.finditer(stripped))
            if cells:
                for cmatch in cells:
                    tag = cmatch.group('tag')
                    ctx = {'section': section, 'table': 'HTML',
                           'col': col if tag != 'caption' else 1,
                           'header': tag == 'th'}
                    units.append(make_unit('table-cell', path, stripped,
                                           cmatch.start('text'), cmatch.end('text'),
                                           [(0, lineno, stripped)], ctx))
                    if tag != 'caption':
                        col += 1
                continue
            if re.match(r'</tr\b', stripped):
                in_row, col = False, 0
            # A markup line carrying text of its own: a caption, a card label.
            if TAG_RE.sub('', stripped).strip():
                units.extend(paragraph_units(path, stripped, [(0, lineno, stripped)],
                                             body_surface(),
                                             {'section': section, 'markup': True}))
            continue
        para.append((lineno, stripped, stripped))
        opens = len(SPAN_OPEN_RE.findall(stripped))
        closes = len(SPAN_CLOSE_RE.findall(stripped))
        if opens > closes:
            open_span = True
        elif closes > opens:
            open_span = False
    flush(body_surface())
    for unit in units:
        unit.ctx['section_audio'] = unit.ctx.get('section') in audio_sections
    return [u for u in units if u.text.strip()]


# --- Markdown ----------------------------------------------------------------

def markdown_units(path, lines):
    units, para, fenced = [], [], False

    def flush():
        nonlocal para
        if para:
            raw, segs = join_lines(para)
            units.extend(paragraph_units(path, raw, segs, 'ref-para', {}))
        para = []

    for lineno, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if stripped.startswith('```'):
            flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        if stripped.startswith('#'):
            flush()
            text = stripped.lstrip('#').strip()
            if text:
                units.append(Unit('ref-heading', path, text, [(0, lineno, stripped)], {}))
            continue
        if not stripped:
            flush()
            continue
        para.append((lineno, stripped, stripped))
    flush()
    return units


def read_units(path):
    """Return (units, labels, entries) for one file.

    `labels` maps an address (upper-case hex) to its `@label`, and `entries`
    lists the `.skool` entries; both are empty for a file that is not a `.skool`.
    """
    with open(path, encoding='utf-8', errors='replace') as handle:
        lines = handle.readlines()
    ext = os.path.splitext(path)[1]
    if ext == '.skool':
        return skool_units(path, lines)
    if ext == '.ctl':
        return ctl_units(path, lines), {}, []
    if ext == '.md':
        return markdown_units(path, lines), {}, []
    return ref_units(path, lines), {}, []


def main(argv):
    for path in argv:
        units = read_units(path)[0]
        for unit in units:
            extra = ''
            entry = unit.ctx.get('entry')
            if entry is not None:
                extra = f' entry={entry.type}{entry.addr}'
            if 'col' in unit.ctx:
                extra += f" col={unit.ctx['col']}"
            print(f'{os.path.basename(path)}:{unit.lineno}\t{unit.surface}{extra}\t'
                  f'{unit.text.strip()}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
