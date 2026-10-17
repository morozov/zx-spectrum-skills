#!/usr/bin/env python3
"""Wrap every label and constant name in the built site's prose in <span class="sym">.

A label that a comment links renders as a link, which the theme sets in the
monospace face; the same label named without a link would otherwise sit in the
reading face beside it. This sets both alike, and sets a constant (an @equ name
such as ATTR_BASE) the same way. The label names come from the listing's own
label cells (td.asm-label on every entry page), and the constant names from the
skool file's @equ directives. Only names holding an underscore or a digit are
taken, so a label that is also an English word ("lives", "level") is never
wrapped in a sentence that uses the word.

Text already set apart is left alone: links, code and pre blocks, the listing's
instruction and label cells, an entry page's title bar (div.description),
span.hex, and the head. Running it twice changes nothing, because text inside a
span.sym is skipped.

Usage: sym_mono.py <site-dir> <skool-file>

The framework runs it after hex_mono.py, in the site stamp recipe.
"""
import re
import sys
from pathlib import Path

from hex_mono import CLASS, NAME, TOKEN, VOID

SKIP_TAGS = {'script', 'style', 'title', 'head', 'code', 'pre', 'textarea', 'a'}
SKIP_CLASSES = {'instruction', 'asm-label', 'hex', 'sym', 'description'}
LABEL_CELL = re.compile(r'<td class="asm-label">([^<]+)</td>')
EQU = re.compile(r'^@equ=([A-Za-z_]\w*)=', re.M)


def label_pattern(site, skool):
    """Return a regex matching any wrappable label or constant as a whole word, or None."""
    found = set()
    for f in site.rglob('*.html'):
        found.update(m.group(1).strip() for m in LABEL_CELL.finditer(f.read_text(encoding='utf-8')))
    found.update(EQU.findall(skool.read_text(encoding='utf-8')))
    names = {n for n in found if re.fullmatch(r'\w+', n) and re.search(r'[_0-9]', n)}
    if not names:
        return None
    alternation = '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(r'(?<![\w$#])(?:%s)(?!\w)' % alternation)


def convert(page, pattern):
    out = []
    stack = []
    for part in TOKEN.split(page):
        if part.startswith('<!--'):
            out.append(part)
        elif part.startswith('<'):
            out.append(part)
            m = NAME.match(part)
            if not m:
                continue
            closing, name = m.group(1), m.group(2).lower()
            if closing:
                while stack and stack.pop()[0] != name:
                    pass
            elif name not in VOID and not part.endswith('/>'):
                c = CLASS.search(part)
                classes = set(c.group(1).split()) if c else set()
                skip = (stack[-1][1] if stack else False) or name in SKIP_TAGS or bool(classes & SKIP_CLASSES)
                stack.append((name, skip))
        elif stack and stack[-1][1]:
            out.append(part)
        else:
            out.append(pattern.sub(lambda m: '<span class="sym">%s</span>' % m.group(0), part))
    return ''.join(out)


def main():
    site = Path(sys.argv[1])
    pattern = label_pattern(site, Path(sys.argv[2]))
    changed = 0
    if pattern is not None:
        for f in sorted(site.rglob('*.html')):
            before = f.read_text(encoding='utf-8')
            after = convert(before, pattern)
            if after != before:
                f.write_text(after, encoding='utf-8')
                changed += 1
    print('sym_mono: %d page(s) rewritten' % changed)


if __name__ == '__main__':
    main()
