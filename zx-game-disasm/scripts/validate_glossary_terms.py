#!/usr/bin/env python3
"""
Hold the project to the terminology registry it publishes.

`references/prose-bar.md` says one term per thing and names `glossary.ref` as the
registry. A registry nothing reads is worse than none: a project can declare it
and violate it in the same build, and an author who believes the doctrine will
not sweep. The site then publishes a "Write X / Not Y" table beside headings
still reading Y.

The registry is any `#TABLE` in a `.ref` page under a `Write | Not` header:

    #TABLE(default)
    { =h Write | =h Not }
    { afterward | afterwards }
    { center, centered | centre, centred }
    TABLE#

Each row's right-hand cell lists the forms that must not appear; the left-hand
cell is what to write instead. Both cells may carry several comma-separated
forms.

**A form qualified in prose is not checked, and the report says how many were
skipped.** "zeros as the verb" and "front-end as a noun" name a form *in one
grammatical role*, and no regex decides the role. Reporting them would be the
Microsoft.Terms failure the glossary itself dismisses — rewriting one spelling to
the other without reading which is meant. Silently dropping them would be the
same false claim of enforcement this check exists to end, so the count is
printed.

Macro arguments are excluded. `centre` inside `#TABLE(default,centre,centre)` is
SkoolKit's own alignment keyword, not the project's prose.

Kinds:

  TERM        a banned form in a line of prose, matched as a whole word.
  TERM_LABEL  a banned form inside a label or an entry title, read as words. A
              label splits on `_` and `-`, so the banned form `enemy` matches
              `enemy_drone`; a title splits on everything but letters and digits,
              so it matches `Enemy-drone table`. Labels are read from `@ $X
              label=` in a `.ctl` and `@label=` in a `.skool`; titles from the
              `.ctl` entry directives. A title form that TERM already reports on
              the same line is not reported twice.

Usage: validate_glossary_terms.py <file …> [--registry glossary.ref] [--baseline FILE]
Exit 0 when no unbaselined violation stands, 1 otherwise.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'terms'

HEADER_RE = re.compile(r'\{\s*=h\s+Write\s*\|\s*=h\s+Not\s*\}', re.I)
TABLE_END_RE = re.compile(r'TABLE#')
ROW_RE = re.compile(r'^\{(?P<write>[^|}]+)\|(?P<not>[^|}]+)\}\s*$')
# A form the registry qualifies in prose, which no pattern can decide.
QUALIFIED_RE = re.compile(r'(?i)\bas (a|an|the)\b|\bthe (verb|noun|plural)\b| - ')
# Macro arguments are not prose: `#TABLE(default,centre,centre)` is SkoolKit's.
MACRO_ARGS_RE = re.compile(r'#[A-Za-z][A-Za-z0-9]*[0-9A-Za-z,=$.+*-]*(\([^)]*\))?')
# A label, in a `.ctl` (`@ $C44B label=enemy_drone`) or a `.skool` (`@label=…`).
LABEL_RE = re.compile(r'^@\s*(?:\$?[0-9A-Fa-f]+\s+)?label=(?P<label>\S+)')
# An entry directive's title in a `.ctl`.
TITLE_RE = re.compile(r'^[bcgistuw] +\$?[0-9A-Fa-f]+ +(?P<title>\S.*)$')
# A label's words: `enemy_drone` and `enemy-drone` both read `enemy drone`.
LABEL_SPLIT_RE = re.compile(r'[_-]+')
# A title's or a registry form's words: anything but a letter or digit splits.
NAME_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def registry(path):
    """Return (pairs, skipped): [(banned form, preferred form)] and a skip count."""
    pairs, skipped, inside = [], 0, False
    if not os.path.exists(path):
        return pairs, skipped
    with open(path, encoding='utf-8', errors='replace') as handle:
        for raw in handle:
            line = raw.strip()
            if HEADER_RE.search(line):
                inside = True
                continue
            if not inside:
                continue
            if TABLE_END_RE.search(line):
                inside = False
                continue
            row = ROW_RE.match(line)
            if not row:
                continue
            write, banned = row.group('write').strip(), row.group('not').strip()
            if QUALIFIED_RE.search(write) or QUALIFIED_RE.search(banned):
                skipped += 1
                continue
            preferred = write.split(',')[0].strip()
            for form in banned.split(','):
                form = form.strip()
                if form:
                    pairs.append((form, preferred))
    return pairs, skipped


def words(text, separators):
    """Return the lowercase words of a label or title."""
    return [w for w in re.split(separators, text.lower()) if w]


def runs(sequence, form_words):
    """Return the (start, end) of every contiguous run of `form_words` in `sequence`."""
    width = len(form_words)
    if not width:
        return []
    return [(i, i + width) for i in range(len(sequence) - width + 1)
            if sequence[i:i + width] == form_words]


def holds(sequence, form_words, preferred_words):
    """Whether `form_words` occurs in `sequence` outside the preferred form.

    Read as words, a banned form can sit inside the form that replaces it:
    `saw` inside `buzz_saw`, the label of the buzz saw, and `tile-state map`,
    whose hyphen a split drops, inside `Tile state map`. A run the preferred
    form covers is the preferred form, and is not reported.
    """
    allowed = runs(sequence, preferred_words)
    return any(not any(a <= start and end <= b for a, b in allowed)
               for start, end in runs(sequence, form_words))


def violations(path, pairs):
    """Yield (lineno, kind, banned form, preferred form, line, name) for one file.

    `name` is the label or title a TERM_LABEL finding read, and None for TERM.
    """
    patterns = [(re.compile(r'(?i)(?<![\w-])' + re.escape(form) + r'(?![\w-])'),
                 form, preferred, words(form, NAME_SPLIT_RE),
                 words(preferred, NAME_SPLIT_RE))
                for form, preferred in pairs]
    with open(path, encoding='utf-8', errors='replace') as handle:
        for lineno, raw in enumerate(handle, 1):
            label = LABEL_RE.match(raw)
            if label:
                name = label.group('label')
                parts = words(name, LABEL_SPLIT_RE)
                for _, form, preferred, form_words, preferred_words in patterns:
                    if holds(parts, form_words, preferred_words):
                        yield lineno, 'TERM_LABEL', form, preferred, raw.strip()[:120], name
                continue
            text = MACRO_ARGS_RE.sub(' ', raw)
            reported = set()
            for pattern, form, preferred, _, _ in patterns:
                if pattern.search(text):
                    reported.add(form)
                    yield lineno, 'TERM', form, preferred, raw.strip()[:120], None
            title = TITLE_RE.match(raw) if path.endswith('.ctl') else None
            if title:
                name = title.group('title').strip()
                parts = words(MACRO_ARGS_RE.sub(' ', name), NAME_SPLIT_RE)
                for _, form, preferred, form_words, preferred_words in patterns:
                    if form not in reported and holds(parts, form_words, preferred_words):
                        yield lineno, 'TERM_LABEL', form, preferred, raw.strip()[:120], name


def token(finding):
    """The baseline's third field: `<file>:<banned form>`.

    The file has to be in the key for the same reason `validate_prose_names.py`
    puts it there: an accepted form in one file and the same form newly written
    into another would otherwise share one key and one count, so fixing the first
    would pay for the second and the gate would stay green on the defect the
    check exists for.
    """
    return '%s:%s' % (os.path.basename(finding[3]), finding[4].lower())


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('files', nargs='+', help='the .skool, .ctl, .ref and spec files')
    parser.add_argument('--registry', help='the .ref page holding the Write/Not table')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    source = args.registry
    if source is None:
        beside = os.path.dirname(os.path.abspath(args.files[0])) or '.'
        source = os.path.join(beside, 'glossary.ref')

    pairs, skipped = registry(source)
    if not pairs:
        print('%s: no Write/Not registry in %s — nothing to hold the prose to'
              % (CHECK, os.path.basename(source)))
        return 0

    # The registry page names every banned form, because naming them is its job.
    # Scanning it reports the table that declares the rule and the prose that
    # explains an exemption, which is the check reading its own instructions
    # back as violations.
    registry_path = os.path.abspath(source)

    # Findings carry (lineno, kind, message, path, form) so the baseline can key
    # on the file and the form, the way every multi-file check here does.
    findings = []
    for path in args.files:
        if not os.path.exists(path) or os.path.abspath(path) == registry_path:
            continue
        for lineno, kind, form, preferred, line, name in violations(path, pairs):
            if kind == 'TERM':
                message = "write '%s', not '%s' – %s" % (preferred, form, line)
            else:
                message = ("TERM_LABEL – '%s' holds the banned form '%s': rename it "
                           "to use '%s' – %s" % (name, form, preferred, line))
            findings.append((lineno, kind, message, path, form))

    note = ('; %d qualified row(s) not checked — a form named in one grammatical '
            'role is a hand pass' % skipped) if skipped else ''

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
        # `Found N …` is the shape `lint_sweep.sh` reads a finding count from; a
        # check that prints its own phrasing is reported as "count unread".
        print('Found %d violation(s) of the registry in %s%s'
              % (len(new), os.path.basename(source), note))
        print()
        for lineno, _, message, path, _form in new:
            print('  %s:%d: %s' % (os.path.basename(path), lineno, message))
        print()
    elif not held and not stale:
        print('%s: %d registry term(s) enforced, none violated%s'
              % (CHECK, len(pairs), note))

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
