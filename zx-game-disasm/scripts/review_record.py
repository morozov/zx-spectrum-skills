#!/usr/bin/env python3
"""The review record: a Challenger verdict bound to one exact diff.

A record lives at `build/review/<diffhash>.json` in the repo under review. The
diff hash covers every change against HEAD that a commit could carry, so any
edit after approval produces a new hash, and the old record no longer applies.

The working-tree hash stages every change, untracked non-ignored files included,
into a throwaway index and hashes `git diff --cached --binary HEAD` over it. The
staged hash runs the same command over the real index. Staging every change
therefore turns the working hash into the staged hash, byte for byte, and a
record written before `git add` verifies at commit time.

Subcommands:

  hash [--cached]        Print the diff hash of the working tree or of the index.
  status [--cached]      Print approved, none, stale or rejected, then the reason.
                         Exit 0 for approved, 1 otherwise.
  verdict --checks PASS|FAIL [--rules-file F]
                         The gate's tail: the REVIEW clause, READY TO COMMIT when
                         the checks pass and the review is approved, and the
                         review-only rule IDs for the changed file types. Always exit 0.
  write --verdict V --reviewer R --rules F.json [--scope S]... [--screenshot P]...
        [--appeasement A]...
                         Write the record for the working-tree diff. The
                         Challenger runs this, never the author of the diff.
  verify                 The pre-commit check: a COMMIT record for the staged
                         diff. Exit 0 when it holds, 1 with what is missing.
  rules-for-diff [--cached] [--rules-file F]
                         Print the review-only rule IDs for the changed files.

Record fields: diffhash, base, verdict (COMMIT, SPLIT or REJECT), reviewer,
rules (a list of {id, result, quote, location}, result one of pass, fail, n.a.),
scope, screenshots, appeasement.

A COMMIT record for a diff that touches a stylesheet or a theme file needs at
least one screenshot, and every listed screenshot must exist.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERDICTS = ('COMMIT', 'SPLIT', 'REJECT')
RESULTS = ('pass', 'fail', 'n.a.')
# Paths that never count as part of the diff: the records themselves and the
# build output.
EXCLUDE = (':(exclude)build',)
VISUAL_RE = re.compile(r'(\.css$|(^|/)theme\.[^/]+$)')
SKILL_HOME = Path(__file__).resolve().parent.parent
DEFAULT_RULES = SKILL_HOME / 'references' / 'rules.md'

# Which rule families a changed file type can break. A family missing here
# applies to every file type.
FAMILIES = {
    'ctl': ('AUD', 'EVID', 'HOME', 'DEF', 'ROW', 'UNU', 'ENT', 'GFX', 'REG', 'NAME', 'HEAD',
            'PROSE', 'TYPO', 'VIS', 'WORK'),
    'ref': ('AUD', 'EVID', 'HOME', 'DEF', 'ROW', 'GFX', 'NAME', 'HEAD', 'PROSE', 'TYPO', 'VIS',
            'WORK'),
    'css': ('VIS', 'WORK'),
    'md': ('AUD', 'EVID', 'HOME', 'PROSE', 'TYPO', 'WORK'),
    'code': ('WORK',),
}


def git(*args, env=None, check=True):
    run = subprocess.run(('git',) + args, capture_output=True, env=env)
    if check and run.returncode != 0:
        raise SystemExit('review_record: git %s failed: %s'
                         % (' '.join(args), run.stderr.decode(errors='replace').strip()))
    return run.stdout


def toplevel():
    return Path(git('rev-parse', '--show-toplevel').decode().strip())


def head():
    out = git('rev-parse', '--verify', '-q', 'HEAD', check=False).decode().strip()
    return out or git('hash-object', '-t', 'tree', '/dev/null').decode().strip()


def staged_diff(env=None):
    return git('diff', '--cached', '--binary', '--no-color', '--no-ext-diff', head(),
               '--', '.', *EXCLUDE, env=env)


def working_diff():
    """Stage every change into a copy of the index and diff that against HEAD."""
    top = toplevel()
    real = os.environ.get('GIT_INDEX_FILE') or git('rev-parse', '--git-path', 'index').decode().strip()
    real = Path(real) if os.path.isabs(real) else top / real
    with tempfile.TemporaryDirectory() as tmp:
        idx = Path(tmp, 'index')
        if real.exists():
            shutil.copyfile(real, idx)
        env = dict(os.environ, GIT_INDEX_FILE=str(idx))
        # The exclusions apply to the diff below: naming an ignored path in an
        # `add` pathspec is an error.
        git('-C', str(top), 'add', '-A', '--', '.', env=env)
        return git('-C', str(top), 'diff', '--cached', '--binary', '--no-color', '--no-ext-diff',
                   head(), '--', '.', *EXCLUDE, env=env)


def diff_bytes(cached):
    return staged_diff() if cached else working_diff()


def diff_hash(cached=False):
    return hashlib.sha256(diff_bytes(cached)).hexdigest()


def changed_files(cached=False):
    names = re.findall(rb'^diff --git a/(.*?) b/', diff_bytes(cached), re.M)
    return sorted({n.decode(errors='replace') for n in names})


def record_dir():
    """build/review in this repo, or $REVIEW_RECORD_DIR (`make gate-index` sets it)."""
    override = os.environ.get('REVIEW_RECORD_DIR')
    return Path(override) if override else toplevel() / 'build' / 'review'


def rel(path):
    try:
        return path.relative_to(toplevel())
    except ValueError:
        return path


def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        return {'_error': str(e)}


RULE_ID_RE = re.compile(r'^\|\s*([A-Z]+-\d+)\s*\|', re.M)


def required_ids():
    """Every rule ID a COMMIT record must answer: the rulebook's."""
    rules = Path(os.environ.get('REVIEW_RULES_MD') or
                 Path(__file__).resolve().parent.parent / 'references' / 'rules.md')
    try:
        return sorted(set(RULE_ID_RE.findall(rules.read_text(encoding='utf-8'))))
    except OSError:
        return []


def problems(rec, files):
    """What makes a record unusable as approval, as a list of sentences."""
    out = []
    if rec.get('_error'):
        return ['the record is not readable JSON (%s)' % rec['_error']]
    if rec.get('verdict') not in VERDICTS:
        out.append('its verdict is %r, which is none of %s' % (rec.get('verdict'), ', '.join(VERDICTS)))
    if not str(rec.get('reviewer') or '').strip():
        out.append('it names no reviewer')
    rules = rec.get('rules')
    if not isinstance(rules, list) or not rules:
        out.append('it answers no rule IDs')
    else:
        for r in rules:
            if not isinstance(r, dict) or not r.get('id') or r.get('result') not in RESULTS:
                out.append('a rule entry lacks an ID or a result of pass, fail or n.a.: %r' % (r,))
                break
            if r['result'] == 'fail' and not (r.get('quote') and r.get('location')):
                out.append('failing rule %s carries no quote and location' % r['id'])
                break
        if rec.get('verdict') == 'COMMIT' and any(isinstance(r, dict) and r.get('result') == 'fail' for r in rules):
            out.append('it says COMMIT over a failing rule')
        if rec.get('verdict') == 'COMMIT':
            answered = {r.get('id') for r in rules if isinstance(r, dict)}
            missing = [i for i in required_ids() if i not in answered]
            if missing:
                out.append('it leaves %d rule ID(s) unanswered: %s' % (
                    len(missing), ', '.join(missing[:12]) + (' …' if len(missing) > 12 else '')))
    if rec.get('verdict') == 'COMMIT' and any(VISUAL_RE.search(f) for f in files):
        screenshots = rec.get('screenshots') or []
        if not screenshots:
            out.append('the diff changes a stylesheet or theme file and the record lists no screenshot')
        else:
            missing = [s for s in screenshots if not (toplevel() / s).exists() and not Path(s).exists()]
            if missing:
                out.append('screenshot(s) missing on disk: %s' % ', '.join(missing))
    return out


def status(cached=False):
    """Return (word, reason, path)."""
    h = diff_hash(cached)
    files = changed_files(cached)
    if not files:
        return 'none', 'no changes against HEAD, so there is nothing to review', None
    d = record_dir()
    path = d / ('%s.json' % h)
    if path.exists():
        rec = load(path)
        bad = problems(rec, files)
        if rec.get('diffhash') not in (None, h):
            bad.insert(0, 'its diffhash field does not match its file name')
        if bad:
            return 'rejected', 'the record for this diff is unusable: %s' % '; '.join(bad), path
        if rec['verdict'] != 'COMMIT':
            return 'rejected', 'the reviewer (%s) returned %s for this diff' % (rec['reviewer'], rec['verdict']), path
        return 'approved', 'reviewer %s, %d rule(s) answered' % (rec['reviewer'], len(rec['rules'])), path
    base = head()
    older = []
    if d.is_dir():
        for p in d.glob('*.json'):
            if not re.fullmatch(r'[0-9a-f]{64}', p.stem):
                continue
            rec = load(p)
            if rec.get('base') == base:
                older.append(p)
    if older:
        newest = max(older, key=lambda p: p.stat().st_mtime)
        return 'stale', ('the newest record on this base, %s, was written for an earlier diff; '
                         'the diff changed after that review' % rel(newest)), newest
    return 'none', 'no review record exists for this diff (%s)' % h[:12], None


def parse_rules(path):
    """Rows of every rulebook table whose header has an ID and an Enforcer column."""
    rows = []
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except OSError:
        return None
    header = None
    for line in lines:
        s = line.strip()
        if not s.startswith('|'):
            header = None
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set('-: ') for c in cells):
            continue
        if 'id' not in header or 'enforcer' not in header:
            continue
        row = dict(zip(header, cells))
        if row.get('id'):
            rows.append(row)
    return rows


def kind_of(path):
    if path.endswith('.ctl') or path.endswith('.skool'):
        return 'ctl'
    if path.endswith('.ref'):
        return 'ref'
    if VISUAL_RE.search(path):
        return 'css'
    if path.endswith('.md'):
        return 'md'
    return 'code'


def review_only_rules(files, rules_file):
    rows = parse_rules(rules_file)
    if rows is None:
        return None
    kinds = {kind_of(f) for f in files}
    fams = set()
    for k in kinds:
        fams.update(FAMILIES[k])
    known = set().union(*FAMILIES.values())
    out = []
    for r in rows:
        if not re.search(r'\breview\b', r.get('enforcer', ''), re.I):
            continue
        fam = r['id'].split('-')[0]
        if fam in fams or fam not in known:
            out.append(r['id'])
    return sorted(set(out), key=lambda i: (i.split('-')[0], int(re.sub(r'\D', '', i) or 0)))


def cmd_verdict(a):
    word, reason, _ = status()
    print('REVIEW: %s – %s.' % (word, reason))
    if a.checks == 'PASS' and word == 'approved':
        print('READY TO COMMIT')
    elif a.checks == 'PASS':
        print('NOT READY TO COMMIT: the checks pass and the review is %s. The checks cover only '
              'what a pattern can decide; a Challenger review of this exact diff is required.' % word)
    else:
        print('NOT READY TO COMMIT: the checks fail.')
    h = diff_hash()
    files = changed_files()
    if files:
        ids = review_only_rules(files, a.rules_file)
        kinds = ', '.join(sorted({kind_of(f) for f in files}))
        if ids is None:
            print('Review-only rules: %s is unreadable, so this gate cannot list them.' % a.rules_file)
        elif ids:
            print('Review-only rules for the changed %s files, which no check above enforces: %s'
                  % (kinds, ' '.join(ids)))
    return 0


def cmd_write(a):
    files = changed_files()
    if not files:
        raise SystemExit('review_record: nothing changed against HEAD, so there is nothing to record.')
    try:
        rules = json.loads(Path(a.rules).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise SystemExit('review_record: cannot read the rules list %s: %s' % (a.rules, e))
    if isinstance(rules, dict):
        rules = rules.get('rules')
    h = diff_hash()
    rec = {
        'diffhash': h,
        'base': head(),
        'verdict': a.verdict,
        'reviewer': a.reviewer,
        'rules': rules,
        'scope': a.scope,
        'screenshots': a.screenshot,
        'appeasement': a.appeasement,
    }
    bad = problems(rec, files)
    if bad:
        raise SystemExit('review_record: refusing to write: %s.' % '; '.join(bad))
    d = record_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / ('%s.json' % h)
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('review_record: wrote %s (%s, %d rule(s), %d file(s) in the diff).'
          % (rel(path), a.verdict, len(rules), len(files)))
    return 0


def cmd_verify(a):
    word, reason, path = status(cached=True)
    if word == 'approved':
        print('review_record: staged diff approved (%s).' % reason)
        return 0
    if word == 'none' and not changed_files(cached=True):
        return 0
    h = diff_hash(cached=True)
    print('Commit refused: review %s. %s.' % (word, reason[0].upper() + reason[1:]), file=sys.stderr)
    print('Needed: build/review/%s.json with verdict COMMIT, written by a Challenger through '
          '`review_record.py write` over exactly the staged diff. Stage every change the review '
          'covered, or have the Challenger review what is staged.' % h, file=sys.stderr)
    return 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('hash')
    s.add_argument('--cached', action='store_true')
    s = sub.add_parser('status')
    s.add_argument('--cached', action='store_true')
    s = sub.add_parser('verdict')
    s.add_argument('--checks', choices=('PASS', 'FAIL'), required=True)
    s.add_argument('--rules-file', default=str(DEFAULT_RULES))
    s = sub.add_parser('write')
    s.add_argument('--verdict', choices=VERDICTS, required=True)
    s.add_argument('--reviewer', required=True)
    s.add_argument('--rules', required=True, help='JSON file: a list of {id, result, quote, location}')
    s.add_argument('--scope', action='append', default=[])
    s.add_argument('--screenshot', action='append', default=[])
    s.add_argument('--appeasement', action='append', default=[])
    sub.add_parser('verify')
    s = sub.add_parser('rules-for-diff')
    s.add_argument('--cached', action='store_true')
    s.add_argument('--rules-file', default=str(DEFAULT_RULES))
    a = p.parse_args()

    if a.cmd == 'hash':
        print(diff_hash(a.cached))
        return 0
    if a.cmd == 'status':
        word, reason, _ = status(a.cached)
        print('%s: %s' % (word, reason))
        return 0 if word == 'approved' else 1
    if a.cmd == 'verdict':
        return cmd_verdict(a)
    if a.cmd == 'write':
        return cmd_write(a)
    if a.cmd == 'verify':
        return cmd_verify(a)
    if a.cmd == 'rules-for-diff':
        ids = review_only_rules(changed_files(a.cached), a.rules_file)
        if ids is None:
            raise SystemExit('review_record: cannot read %s' % a.rules_file)
        print(' '.join(ids))
        return 0


if __name__ == '__main__':
    sys.exit(main())
