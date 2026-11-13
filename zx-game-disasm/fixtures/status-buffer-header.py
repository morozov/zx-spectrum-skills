#!/usr/bin/env python3
"""Lint the `g` page names assets/game.ref.template gives a new project's site.

A heading the template does not set is SkoolKit's, and SkoolKit's is "Game
status buffer", storage vocabulary for what the reader browses as the game's
variables (HEAD-2). Linting the template's text alone cannot see that: drop its
[PageHeaders] lines and the default comes back while the template holds no
words to report. So this writes the names the site would draw - SkoolKit's
defaults for the `g` pages, overlaid with the template's own values - into a
ref of their own, and lints that, beside the bad case written out by hand.

Usage: status-buffer-header.py   (prints lint_comments.py's report)
"""
import os
import re
import subprocess
import sys
import tempfile

from skoolkit import defaults

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL, 'assets', 'game.ref.template')
KEYS = ('Asm-g', 'GameStatusBuffer')
SECTIONS = ('PageHeaders', 'Titles', 'Links')
SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*$')


def values(text):
    """Return {key: value} for the non-comment `key=value` lines of a section."""
    found = {}
    for line in text.splitlines():
        if line.startswith(';') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        found[key] = value
    return found


def template_sections():
    """Return {section name: body} for the template."""
    sections, name, body = {}, None, []
    with open(TEMPLATE, encoding='utf-8') as f:
        for line in f.read().splitlines():
            m = SECTION_RE.match(line)
            if m:
                if name:
                    sections[name] = '\n'.join(body)
                name, body = m.group(1), []
            else:
                body.append(line)
    if name:
        sections[name] = '\n'.join(body)
    return sections


def effective_ref():
    """The `g` names the site draws, as a ref: SkoolKit's, then the template's."""
    template = template_sections()
    out = ['; The g page names assets/game.ref.template leaves the site with.']
    for section in SECTIONS:
        merged = {k: v for k, v in values(defaults.SECTIONS.get(section, '')).items()
                  if k in KEYS}
        merged.update({k: v for k, v in values(template.get(section, '')).items()
                       if k in KEYS})
        out += ['', f'[{section}]'] + [f'{k}={merged[k]}' for k in KEYS if k in merged]
    # The home page's group that lists the variables, under the template's
    # heading or SkoolKit's.
    group = next((s for s in template if s.startswith('Index:DataTables:')),
                 next(s for s in defaults.SECTIONS if s.startswith('Index:DataTables:')))
    out += ['', f'[{group}]', 'GameStatusBuffer']
    return '\n'.join(out) + '\n'


def main():
    with tempfile.TemporaryDirectory() as work:
        path = os.path.join(work, 'game.ref.template-effective.ref')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(effective_ref())
        result = subprocess.run(
            [sys.executable, os.path.join(SKILL, 'scripts', 'lint_comments.py'),
             os.path.join(HERE, 'no-code.skool'), path,
             os.path.join(HERE, 'status-buffer-header.ref')],
            capture_output=True, text=True)
        sys.stdout.write((result.stdout + result.stderr).replace(work + os.sep, ''))
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
