#!/usr/bin/env python3
"""
Validate that every image macro put an image on the site.

`make` checks that the HTML *builds*, and `coverage` counts the image macros in
the source. Both stay true when an image-file macro `(name)` is rewritten into
the frame-only form `(*name)`, which defines a frame and writes no file: the
source still holds its macros, the site still builds, and the count does not
move, while the image is gone from the site.

Counting macros is the proxy; the files under `html/` are the outcome. This check
reads the outcome.

## The invariant

**Every image macro names an output file, and every named output file exists.**

Not "as many files as macros". Those two numbers differ for reasons that are all
legitimate: one macro can write one file while several macros write the same one
(a sprite rendered at its data block and again in the `.ref` catalog is two
macros and one file), a `#FRAMES` macro writes one animation out of frames other
macros defined, and a frame-only macro writes nothing at all. An inequality
between the totals is therefore not a defect, and equality is not proof.

What does not legitimately differ is the per-macro claim. A macro that names
`player` claims `player.png` is on the site, and either it is there or it is not.
That claim is checkable one macro at a time, and it fails the moment a single
macro stops rendering - which the aggregate cannot do.

Two kinds, because the failure this exists to catch removes the claim along with
the file:

  UNRENDERED  the macro names a file and the built site has no such image. The
              macro's extent, its address, or the build is wrong; the reader gets
              a broken image or a blank where the sprite should be.

  NOFILE      the macro names no file. `(*name)` defines a frame and writes
              nothing, and `()` writes nothing either. The block it stands on
              publishes no picture. A frame is legitimate only as an ingredient:
              some `#FRAMES`, `#UDGS` or `#COPY` macro must consume it, and the
              macro that does must itself name a file, so the picture reaches
              the reader one step removed. An unconsumed frame renders nowhere.

UNRENDERED alone is silent when every macro is rewritten into the frame-only
form: no macro names a file, so no named file is missing. NOFILE is what refuses
a macro that claims nothing.

The baseline keys on the file or frame name rather than on an address: these
findings live in `.ref` catalogs as often as in the `.ctl`, and a sprite that
moves down a catalog table is the same sprite.

Usage: validate_rendered_images.py --html DIR CTL [PROSE ...]
Exit 0 when clean, 1 when a macro rendered nothing.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'images'

# The macro names this reads. The parameters that follow a name are word
# characters (`#UDGARRAY2,…`), so no word boundary can end it and the longer
# alternatives must come first, or `#UDG` claims the first four characters of
# `#UDGARRAY`. `#UDGTABLE` opens a table, not a picture, and is dropped below.
MACRO_RE = re.compile(r'#(?:UDGTABLE|UDGARRAY|UDGS|UDG|FRAMES|FONT|SCR|COPY)')

# Where each file-writing macro states its filename, checked against SkoolKit's
# own parsers: (the number of top-level `(...)` groups the macro must have for
# one of them to be the filename, which group that is, the name SkoolKit writes
# when the macro states none).
#
# The group index is not "the last one" for every macro, and reading it that way
# misreads three legal forms. `#UDGSw,h(fname)(uframe)` puts the filename first
# and a frame reference last. `#FONTaddr[,…][(message)][(fname)]` with one group
# has stated a message and no filename. `#UDG` and `#SCR` name `udg.png` and
# `scr.png` when they state nothing.
FNAME_GROUP = {
    '#UDG':      (1, -1, 'udg'),
    '#UDGARRAY': (2, -1, None),
    '#UDGS':     (1, 0, None),
    '#SCR':      (1, -1, 'scr'),
    '#FONT':     (2, -1, 'font'),
    '#FRAMES':   (2, 1, None),
}

# Where each macro that draws on already-defined frames states them.
# `#FRAMES(a,12;b,12)(fname)` lists them first; `#UDGSw,h(fname)(uframe)` names
# one last; `#COPY[…](old,new)` copies `old` and writes no file at all.
FRAME_GROUP = {'#FRAMES': (2, 0), '#UDGS': (2, 1), '#COPY': (1, -1)}

IMAGE_EXTENSIONS = ('.png', '.gif')

# SkoolKit appends `.png` to a filename that does not already end with it, so
# `(player)` and `(player.png)` name the same file.
PNG_SUFFIX = '.png'

BRACKETS = {'(': ')', '{': '}', '[': ']'}


def macro_extent(text, start):
    """
    Return the index just past the macro whose name starts at `start`.

    A macro ends at whitespace, except inside a bracketed group: alt text and a
    `#FONT` message are prose and carry spaces. Stopping at the first space
    would truncate `(player|the player sprite)` mid-group, leaving the macro with
    no parsable filename and dropping it from the survey without a word.
    """
    index = start
    while index < len(text):
        char = text[index]
        if char in BRACKETS:
            closing, depth = BRACKETS[char], 0
            while index < len(text):
                if text[index] == char:
                    depth += 1
                elif text[index] == closing:
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            else:
                return index          # unterminated: the macro runs to the end
        elif char.isspace():
            break
        else:
            index += 1
    return index


def top_level_groups(body):
    """Return the contents of each top-level `(...)` group of a macro, in order."""
    groups, index = [], 0
    while index < len(body):
        char = body[index]
        if char == '(':
            depth, end = 1, index + 1
            while end < len(body) and depth:
                depth += (body[end] == '(') - (body[end] == ')')
                end += 1
            if depth:
                break
            groups.append(body[index + 1:end - 1])
            index = end
        elif char in '{[':
            end = body.find(BRACKETS[char], index)
            index = len(body) if end < 0 else end + 1
        else:
            index += 1
    return groups


def select(groups, spec):
    """Return the group a macro's `(minimum, index)` spec points at, or None."""
    minimum, position = spec[0], spec[1]
    return groups[position] if len(groups) >= minimum else None


def parse_spec(spec):
    """
    Return (filename, frame) for a macro's parenthesized filename spec.

    The spec is `fname[*[frame]][|alt]`, and SkoolKit splits it in that order:
    alt text off the end first, then the frame. `fname*` names the frame after
    the file. The `.png` SkoolKit would append is dropped, so a spec that spells
    it out names the same file as one that does not.
    """
    name = spec.split('|', 1)[0]
    name, star, frame = name.partition('*')
    frame = frame.split(',')[0].strip()
    if star and not frame:
        frame = name
    name = name.strip()
    if name.lower().endswith(PNG_SUFFIX):
        name = name[:-len(PNG_SUFFIX)]
    return name, (frame.strip() if star else '')


def consumed_frames(name, groups):
    """
    Return the frame names one macro draws from.

    `#FRAMES(a,12;b,12)(fname)` lists them semicolon-separated, each with an
    optional `,delay,x,y` tail; `#UDGS`'s last group is one frame name;
    `#COPY(old,new)` copies the first of two.
    """
    spec = FRAME_GROUP.get(name)
    if spec is None:
        return []
    body = select(groups, spec)
    if body is None:
        return []
    if name == '#COPY':
        return [body.split(',')[0].strip()]
    if name == '#UDGS':
        return [body.strip()]
    return [part.split(',')[0].strip() for part in body.split(';') if part.strip()]


def parse_macros(paths):
    """
    Return every image macro in the given files.

    Each is (path, line, name, groups, spec), where `spec` is the filename spec
    the macro states, or None when it states none and SkoolKit falls back to a
    default name.
    """
    macros = []
    for path in paths:
        try:
            with open(path, encoding='utf-8', errors='ignore') as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            for match in MACRO_RE.finditer(line):
                name = match.group(0)
                if name == '#UDGTABLE':
                    continue
                groups = top_level_groups(line[match.end():macro_extent(line, match.end())])
                spec = FNAME_GROUP.get(name)
                macros.append((path, number, name, groups,
                               select(groups, spec) if spec else None))
    return macros


def rendered_images(html_dir):
    """Return the stem of every image file the built site holds."""
    stems = set()
    for root, _, names in os.walk(html_dir):
        for name in names:
            stem, extension = os.path.splitext(name)
            if extension.lower() in IMAGE_EXTENSIONS:
                stems.add(stem)
    return stems


def survey(html_dir, paths):
    """
    Measure the macros against the built site.

    Returns a dict with the macro count, the distinct filenames declared, the
    ones rendered, and the findings - so `coverage_report` reports the same
    outcome the gate holds, rather than its own count of the source.
    """
    macros = parse_macros(paths)
    stems = rendered_images(html_dir)

    consumed = set()
    for _, _, name, groups, _ in macros:
        consumed.update(consumed_frames(name, groups))

    declared, findings = {}, []
    for path, number, macro, _, spec in macros:
        if spec is None:
            continue          # no filename spec: SkoolKit writes its default name
        name, frame = parse_spec(spec)
        if name:
            declared.setdefault(os.path.basename(name), []).append((path, number))
            continue
        if frame and frame in consumed:
            continue          # an ingredient of an animation that does name a file
        findings.append((number, 'NOFILE',
                         f'`{macro}…({spec})` names no output file, so this macro writes no '
                         f'image — '
                         + (f'it defines the frame `{frame}`, and no `#FRAMES`, `#UDGS` or '
                            f'`#COPY` macro consumes it' if frame else 'and it defines no frame')
                         + '. Give it a filename: `(name)` writes the image, `(name*frame)` '
                           'writes it and defines the frame',
                         path, frame or spec))

    missing = sorted(name for name in declared if name not in stems)
    for name in missing:
        path, number = declared[name][0]
        findings.append((number, 'UNRENDERED',
                         f'names the image `{name}`, and the built site under {html_dir} has no '
                         f'such file. The macro rendered nothing a reader can see',
                         path, name))

    findings.sort(key=lambda f: (f[3], f[0]))
    return {'macros': sum(1 for m in macros if m[2] in FNAME_GROUP),
            'declared': declared, 'rendered': stems,
            'missing': missing, 'findings': findings}


def token(finding):
    """The baseline's third field: the file or frame the macro failed to render."""
    return finding[4] or '?'


def main():
    parser = argparse.ArgumentParser(
        description='Validate that every image macro put an image on the site.')
    parser.add_argument('ctl', help='the .ctl file')
    parser.add_argument('prose', nargs='*', help='the .ref catalogs to sweep too')
    parser.add_argument('--html', default='html',
                        help='the built site directory (default html)')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    if not os.path.isdir(args.html):
        print(f'Error: no built site at {args.html} — this check reads the images the '
              f'build produced, so it needs the build')
        return 1

    result = survey(args.html, [args.ctl] + args.prose)
    findings = result['findings']

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, findings, [], token_of=token))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, findings, [],
                                              report_stale=not args.ignore_stale,
                                              token_of=token)

    if new:
        print(f'Found {len(new)} image macro(s) that rendered nothing:')
        print()
        for number, kind, message, path, _ in new:
            print(f'  {os.path.basename(path)}:{number}: {kind} — {message}')
            print()
    elif not held and not stale:
        print(f"rendered images: {result['macros']} image macro(s) declare "
              f"{len(result['declared'])} file(s), all {len(result['declared'])} present under "
              f"{args.html}")

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
