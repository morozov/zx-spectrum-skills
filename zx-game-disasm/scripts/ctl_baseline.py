#!/usr/bin/env python3
"""Known-failing baseline shared by the .ctl linters that gate on findings.

A check worth running is worth running in the gate, and a mature project has
findings the day the check is written. Left advisory, the check is never run and
the defect ships; made blocking with no escape, it is switched off. The baseline
is the third option: the project records what it already fails, the gate holds
that line, and shrinking the file is how the debt clears.

The file is TOML. It lists each accepted finding as one `[[finding]]` table:

    [[finding]]
    check = "identity"
    kind = "UNTITLED_ENTRY"
    at = "$F108"
    message = "the message as recorded"

`check`, `kind` and `at` are the key; the message is for the reader and is
ignored by the comparison. Regenerating rewrites the findings belonging to the
check that runs and leaves every other check's untouched, so a message that has
drifted shows up as a diff without failing anything.

Four rules give the file its shape:

- a finding whose key is absent fails the gate - that is the new defect;
- a key present for a check that ran, which the check no longer reports, fails
  the gate too - a fixed finding must leave the file in the commit that fixes
  it, so the baseline cannot rot into a permanent excuse;
- a key is only ever compared against the check that wrote it, so a project may
  baseline one check and gate another cleanly;
- a key may repeat, and the count is part of the comparison. Two findings of one
  kind at one address are two tables, and a third fails the gate.

The key is the address on the directive the finding points at, never the line
number: line numbers churn on every unrelated edit above them, and message text
changes when a neighboring directive resizes. Counting repeats is what keeps
that from swallowing a second finding at an address already listed - splitting
one undescribed directive into two undescribed directives adds a table, so the
gate sees it - while a directive that merely moves down the file does not.

A check whose findings do not live on a directive supplies its own `at` through
`token_of`. A phrase in a `.ref` catalog has no address to key on, and
the address of the `.ctl` line that happens to carry it is not its identity - the
phrase is. Counting repeats then reads as "13 occurrences of this phrase are
accepted", and the fourteenth fails the gate.

Regeneration is routine, which makes a silent regeneration the realistic way a
finding gets buried, and naming the keys it adds only tells an author who reads
the output. So `write` refuses: a rewrite that would add a key writes nothing,
names the keys and exits non-zero, because a file that grows is debt taken on,
not debt inherited. A rewrite that only drops keys, or only carries a reworded
message, writes and succeeds - message text is not part of a key.

One growth is not debt taken on: a project adopting a check that has never run
there, whose findings all predate it. That adoption is declared in the file's
`adopted` list, one line per declared entry, and `--adopt` writes the entry:

    adopted = [
      "identity",
      "publication CONTRADICTED",
    ]

The declaration is what the refusal reads, and it is why "has this check run
here" stops being guessed at. Owning no lines does not answer it - a check owns
no findings when it has never run here and equally when it ran and was clean - so
going by ownership, a clean check would be adoptable and the forbidden sequence
would work one flag deeper.
A declared check is refused instead, whatever it owns, and every successful
rewrite declares the check it rewrote: a check that regenerates cleanly here has
demonstrably run here.

The second granularity is for a check that grows a new finding kind after the
project adopted it. Those findings predate the kind by construction - the `.ctl`
was written before it existed - but they arrive under a check whose name is
already declared, so `--adopt` is closed to them and the rational move becomes
pinning the skill version. `--adopt-kind KIND` declares that one kind, once, and
leaves every other kind of the check refused.

So the file states its own invariant, decidable without a history: for every
declared entry the count is non-increasing, and the declared set grows only by a
line a reviewer reads in the diff.

The file also records the gate it was written under, in a `[gate]` table of its
`generation` and `digest`. `write` keeps it; `make lint-baseline` sets it
through `stamp`, and the gate reads it back through `gate`, which prints it as
`<generation>/<digest>` the way the verdict names a gate:

    ctl_baseline.py gate FILE
    ctl_baseline.py stamp FILE GENERATION DIGEST
"""

import argparse
import collections
import json
import os
import re
import sys
import tomllib

# Every .ctl directive line names its address in one of two shapes: a directive
# letter and the address (`b $F108`, `B $F108,1`, `@ $F108 label=`), or the
# two-space line comment (`  $F108 text`).
ADDRESS_RE = re.compile(r'^(?:[@A-Za-z] +|  )(\$?[0-9A-Fa-f]+)')

# The fields of one `[[finding]]` table, in the order the file writes them.
FIELDS = ('check', 'kind', 'at', 'message')

# The exit status `write` refuses with. `make lint-baseline` tells a refusal from
# a check that crashed or was called wrongly by this status alone, and reports
# them differently: a refusal is the mechanism working.
REFUSED_EXIT = 3

# `--adopt` and `--adopt-kind` are recorded here at parse time instead of being
# passed to `write`. Every check calls `write` from its own script, and an
# enforcement the caller has to opt into is an enforcement a caller can omit -
# which is the hole this guard closes. The flags reach every check because every
# check calls `add_arguments`.
#
# `None` when neither was given, `ADOPT_CHECK` for `--adopt`, and the kind's name
# for `--adopt-kind`.
ADOPT_CHECK = '*'
_ADOPT = None


class _Adopt(argparse.Action):
    """Record an adoption flag where `write` reads it."""

    def __call__(self, parser, namespace, values, option_string=None):
        global _ADOPT
        if option_string == '--adopt':
            _ADOPT = ADOPT_CHECK
            return
        _ADOPT = (values or '').strip()
        if not _ADOPT:
            parser.error('--adopt-kind needs the name of a finding kind, as the '
                         'baseline records it: `--adopt-kind CONTRADICTED`')


def add_arguments(parser):
    """Add the baseline options to a linter's argument parser."""
    parser.add_argument('--baseline',
                        help='file of accepted known-failing findings; findings it '
                             'lists do not fail the gate')
    parser.add_argument('--write-baseline', action='store_true',
                        help='rewrite this check\'s section of --baseline, rather '
                             'than gating on them; fails without writing if the '
                             'rewrite would add a key')
    # `default=SUPPRESS` keeps both flags off the namespace: `write` reads the
    # module state, and an attribute nothing reads invites a caller to test the
    # wrong thing.
    parser.add_argument('--adopt', action=_Adopt, nargs=0, default=argparse.SUPPRESS,
                        help='let --write-baseline record this check\'s findings on a '
                             'project whose .ctl predates the check, and declare the '
                             'check adopted in the baseline\'s adopted list. Refused for a '
                             'check the baseline already declares: a check is adopted '
                             'once, and from there its findings only shrink')
    parser.add_argument('--adopt-kind', metavar='KIND', action=_Adopt,
                        default=argparse.SUPPRESS,
                        help='the same, for one finding kind of a check this project '
                             'already adopted - a kind the check itself gained since, '
                             'whose findings predate it. Records that kind\'s findings '
                             'only, and declares the kind adopted')
    parser.add_argument('--ignore-stale', action='store_true',
                        help='do not fail on baseline entries this run no longer '
                             'reports; for a spliced fragment, whose .ctl is a '
                             'fraction of the one the baseline was written from')


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def finding_key(check, line_number, kind, lines):
    """Return `check KIND $ADDRESS` for a finding reported at a source line."""
    text = lines[line_number - 1] if 0 < line_number <= len(lines) else ''
    match = ADDRESS_RE.match(text)
    if not match:
        return f'{check} {kind} ?'
    return f'{check} {kind} ${parse_address(match.group(1)):04X}'


def key_for(check, finding, lines, token_of=None):
    """
    Return one finding's baseline key.

    `token_of`, when given, maps the finding to the key's third field, for a
    check whose findings are not located by a .ctl directive address.
    """
    if token_of is None:
        return finding_key(check, finding[0], finding[1], lines)
    return f'{check} {finding[1]} {token_of(finding)}'


def read(path):
    """Return the file as a dict of `gate`, `adopted` and `finding`; empty if absent."""
    data = {}
    if path and os.path.exists(path):
        with open(path, 'rb') as f:
            data = tomllib.load(f)
    return {'gate': data.get('gate'),
            'adopted': list(data.get('adopted', [])),
            'finding': [{k: str(f.get(k, '')) for k in FIELDS} for f in data.get('finding', [])]}


def dump(path, data):
    """Write the file, with each adoption and each finding field on a line of its own."""
    def q(text):
        return json.dumps(text, ensure_ascii=False)  # a JSON string is a TOML basic string
    out = []
    if data['adopted']:
        out.append('adopted = [')
        out += [f'  {q(entry)},' for entry in sorted(data['adopted'])]
        out.append(']')
    if data.get('gate'):
        generation, digest = data['gate']['generation'], data['gate']['digest']
        out += ['', '[gate]',
                f'generation = {generation if isinstance(generation, int) else q(generation)}',
                f'digest = {q(digest)}']
    for finding in sorted(data['finding'], key=lambda f: tuple(f[k] for k in FIELDS)):
        out += ['', '[[finding]]'] + [f'{k} = {q(finding[k])}' for k in FIELDS]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out).lstrip('\n') + '\n')


def key_of(finding):
    """Return a recorded finding's key, `check KIND at`."""
    return f'{finding["check"]} {finding["kind"]} {finding["at"]}'


def read_findings(path):
    """Return the file's findings, as dicts of `check`, `kind`, `at` and `message`."""
    return read(path)['finding']


def read_adoptions(path):
    """Return the entries the file declares adopted, as a set of strings."""
    return set(read(path)['adopted'])


def load(path, check):
    """Return how many times each key is recorded for one check, as a Counter."""
    return collections.Counter(key_of(f) for f in read_findings(path) if f['check'] == check)


def _adoption_for(check, added, declared):
    """
    Return the entry an adoption flag would declare, or a refusal to print.

    Exactly one of the two is a string: the entry to record as adopted, or the
    reason this rewrite is not an adoption. `--adopt` covers every kind the check
    reports and is the first adoption of that check; `--adopt-kind` covers one
    kind of a check the file already declares.
    """
    kinds = sorted({key.split()[1] for key in added})
    named = sorted(e for e in declared if e == check or e.startswith(f'{check} '))

    if _ADOPT is None:
        if not named:
            return None, (f'If {check} has never run on this project, adopt it once, '
                          f'deliberately, by running this check with --adopt.')
        return None, (f'The file declares {check} adopted, so its findings only shrink '
                      f'from here and nothing re-adopts it.')
    if _ADOPT == ADOPT_CHECK:
        if named:
            spelled = ', '.join(f'`"{entry}"`' for entry in named)
            return None, (f'--adopt declares a check the file does not, and its adopted '
                          f'list carries {spelled} already. A check is adopted once; after that its '
                          f'findings only shrink, whatever it currently lists — including '
                          f'nothing.')
        return check, None
    if check not in declared:
        return None, (f'--adopt-kind declares one kind of a check this project has already '
                      f'adopted, and the file does not declare {check} at all. Adopt the '
                      f'check itself with --adopt.')
    if f'{check} {_ADOPT}' in declared:
        return None, (f'`{check} {_ADOPT}` is declared in the file already, so that kind '
                      f'only shrinks from here.')
    if kinds != [_ADOPT]:
        return None, (f'--adopt-kind {_ADOPT} records that kind alone, and these keys are '
                      f'{", ".join(kinds)}. A kind is adopted because the check gained it '
                      f'after this project adopted the check; the others are findings to fix.')
    return f'{check} {_ADOPT}', None


def _guard_growth(path, check, added, declared):
    """
    Return the entry a legitimate adoption declares; refuse anything else, exit 3.

    Refusing beats writing and exiting non-zero. The file is left saying what it
    said, so the gate that runs next still fails on the finding: the tree and the
    verdict agree, and a rerun of anything reaches the same answer. A written
    file that failed once has already buried the finding - the exit status is
    gone by the next command, the gate is green, and only a revert undoes it.
    """
    adoption, refusal = _adoption_for(check, added, declared)
    if adoption:
        return adoption
    print(f'{check}: REFUSED to write {path} — {len(added)} key(s) it does not list, '
          f'and a key this file gains is debt taken on, not debt inherited:')
    for key in added:
        print(f'  + {key}')
    print(f'{path} is unchanged, so the gate still fails on them. Fix the finding, '
          f'then re-run.')
    print(refusal)
    sys.exit(REFUSED_EXIT)


def write(path, check, findings, lines, token_of=None):
    """
    Rewrite one check's findings in the baseline, leaving every other check's alone.

    `findings` are (line_number, kind, message, ...) tuples. Returns
    (recorded, added, dropped, adopted): how many findings this check now owns, the
    keys that appeared and disappeared since the file was last written, and the
    adopted entry this run declared, if it declared one.

    Writes nothing and exits `REFUSED_EXIT` when the rewrite would add a key,
    unless an adoption flag declares an entry the file does not carry yet. A
    rewrite that only drops keys, or that carries a message reworded since the
    file was written, is not growth: the message is not part of the key.

    A successful rewrite declares the check, because a check that regenerates
    here has run here - which is what stops a check that is merely clean from
    being adoptable later. The one file this does not create is a baseline that
    would hold nothing: a project with no findings and no baseline keeps neither.
    """
    existed = bool(path) and os.path.exists(path)
    data = read(path)
    previous = load(path, check)
    declared = set(data['adopted'])
    kept = [f for f in data['finding'] if f['check'] != check]

    current = collections.Counter()
    recorded = []
    for finding in findings:
        key = key_for(check, finding, lines, token_of)
        current[key] += 1
        _, kind, at = key.split(' ', 2)
        recorded.append({'check': check, 'kind': kind, 'at': at, 'message': finding[2]})

    added = sorted((current - previous).elements())
    adopted = _guard_growth(path, check, added, declared) if added else None

    if not existed and not recorded and not adopted:
        return 0, [], [], None

    if adopted:
        declared.add(adopted)
    if check not in declared:
        adopted = adopted or check
        declared.add(check)

    dump(path, {'gate': data['gate'], 'adopted': declared, 'finding': kept + recorded})

    return len(recorded), added, sorted((previous - current).elements()), adopted


def partition(path, check, findings, lines, report_stale=True, token_of=None):
    """
    Split findings against the baseline.

    `findings` are (line_number, kind, ...) tuples. Returns (new, held, stale):
    the findings the baseline does not cover, the ones it does, and the keys it
    records for this check that the check no longer reports. A key recorded N
    times covers the first N findings that carry it; the N+1st is new.
    """
    accepted = load(path, check)
    new, held = [], []
    seen = collections.Counter()
    for finding in findings:
        key = key_for(check, finding, lines, token_of)
        seen[key] += 1
        (held if seen[key] <= accepted[key] else new).append(finding)
    stale = sorted((accepted - seen).elements()) if report_stale else []
    return new, held, stale


def report(path, check, held, stale):
    """Print the baseline's own verdict: what it held, and what it no longer covers."""
    if held:
        print(f'{check}: {len(held)} known finding(s) held by {path}')
    if stale:
        print(f'{check}: {len(stale)} baseline entry(ies) in {path} no longer reported — '
              f'the finding is fixed, so drop the line (`make lint-baseline`):')
        for key, count in sorted(collections.Counter(stale).items()):
            print(f'  {key}' + (f'  (x{count})' if count > 1 else ''))


def report_write(path, check, recorded, added, dropped, adopted=None):
    """
    Print what a regeneration recorded, naming every key it added and dropped.

    A regeneration that reaches here and added keys is an adoption - `write`
    refuses every other kind - so the added keys are this check's whole starting
    debt, named once, in the commit that takes it on. `adopted` is the
    entry it declared, which is the line that says the debt stops there.
    """
    if not os.path.exists(path):
        print(f'{check}: nothing to record, and {path} does not exist — a project '
              f'with no findings keeps no baseline')
        return
    print(f'{check}: recorded {recorded} finding(s) in {path}')
    if adopted:
        print(f'{check}: declared adopted in {path} — `"{adopted}"`. '
              f'From here that entry only shrinks; nothing re-adopts it.')
    if added:
        print(f'{check}: adopted — {len(added)} key(s) recorded that {path} listed '
              f'none of:')
        for key in added:
            print(f'  + {key}')
    if dropped:
        print(f'{check}: {len(dropped)} key(s) dropped, now clean:')
        for key in dropped:
            print(f'  - {key}')


def main():
    """`gate FILE` prints the gate the file was recorded under; `stamp` sets it."""
    parser = argparse.ArgumentParser(description='Read or set the gate a baseline was recorded under.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('gate').add_argument('file')
    stamp = sub.add_parser('stamp')
    stamp.add_argument('file')
    stamp.add_argument('generation')
    stamp.add_argument('digest')
    args = parser.parse_args()
    if not os.path.exists(args.file):
        return 0
    data = read(args.file)
    if args.command == 'gate':
        if data['gate']:
            print(f'{data["gate"]["generation"]}/{data["gate"]["digest"]}')
        return 0
    generation = int(args.generation) if args.generation.isdigit() else args.generation
    data['gate'] = {'generation': generation, 'digest': args.digest}
    dump(args.file, data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
