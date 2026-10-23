#!/usr/bin/env python3
"""Wrap every $-hex value in the built site's text in <span class="hex">.

The theme (theme/theme.css) sets .hex in the monospace face. A value is two or four hex digits
after a dollar sign. Text already monospace is left alone: the listing's
instruction and label cells, code and pre blocks, and the head. Running it twice
changes nothing, because text inside a span.hex is skipped.

Usage: hex_mono.py <site-dir>

The framework runs it after skool2html, in the site stamp recipe.
"""
import re
import sys
from pathlib import Path

HEX = re.compile(r'(?<![0-9A-Za-z_$])\$(?:[0-9A-Fa-f]{4}|[0-9A-Fa-f]{2})(?![0-9A-Za-z_])')
# A tag is a name, then optional attributes, then an optional slash. An attribute
# value may hold a '>' when quoted. Anything else that starts with '<', such as
# the comparison in a script body, is text.
TAG = r'</?[A-Za-z][A-Za-z0-9]*(?:\s(?:[^>"\']|"[^"]*"|\'[^\']*\')*)?/?>'
TOKEN = re.compile(r'(<!--.*?-->|%s)' % TAG, re.S)
NAME = re.compile(r'<(/?)([A-Za-z][A-Za-z0-9]*)')
CLASS = re.compile(r'class="([^"]*)"')
VOID = {'br', 'img', 'hr', 'meta', 'link', 'input', 'col', 'area', 'base', 'wbr'}
SKIP_TAGS = {'script', 'style', 'title', 'head', 'code', 'pre', 'textarea'}
SKIP_CLASSES = {'instruction', 'asm-label', 'hex'}


def wrap(text):
    return HEX.sub(lambda m: '<span class="hex">%s</span>' % m.group(0), text)


def convert(page):
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
        else:
            out.append(part if (stack and stack[-1][1]) else wrap(part))
    return ''.join(out)


def main():
    site = Path(sys.argv[1])
    changed = 0
    for f in sorted(site.rglob('*.html')):
        before = f.read_text(encoding='utf-8')
        after = convert(before)
        if after != before:
            f.write_text(after, encoding='utf-8')
            changed += 1
    print('hex_mono: %d page(s) rewritten' % changed)


if __name__ == '__main__':
    main()
