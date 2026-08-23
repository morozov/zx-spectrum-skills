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


def violations(path, pairs):
    """Yield (lineno, banned form, preferred form, line) for one file."""
    patterns = [(re.compile(r'(?i)(?<![\w-])' + re.escape(form) + r'(?![\w-])'),
                 form, preferred) for form, preferred in pairs]
    with open(path, encoding='utf-8', errors='replace') as handle:
        for lineno, raw in enumerate(handle, 1):
            text = MACRO_ARGS_RE.sub(' ', raw)
            for pattern, form, preferred in patterns:
                if pattern.search(text):
                    yield lineno, form, preferred, raw.strip()[:120]


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
        for lineno, form, preferred, line in violations(path, pairs):
            findings.append((lineno, 'TERM',
                             "write '%s', not '%s' — %s" % (preferred, form, line),
                             path, form))

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
        print('%s: %d violation(s) of the registry in %s%s'
              % (CHECK, len(new), os.path.basename(source), note))
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
