#!/usr/bin/env python3
"""
Run Vale over extracted prose and report its findings against the real sources.

`extract_prose.py` lifts the disassembly's prose into one Markdown file and
records where each line came from. Vale lints that file and reports positions in
it; this translates them back, so a finding reads `game.skool:7830: …` and not
`prose.md:4471: …`.

Findings are grouped by check and printed most-frequent first, because a prose
check almost never fires once: the useful question is which rule the project is
breaking, not which line broke it. `--detail` prints every instance.

Exit status is 1 when any finding is at or above `--fail-on` (default `error`),
so the Makefile can gate on the errors while still showing the warnings.

Usage:
    vale_report.py --map prose.map.json [--detail] [--fail-on warning] prose.md
"""

import argparse
import collections
import json
import os
import shutil
import subprocess
import sys

RANK = {'suggestion': 0, 'warning': 1, 'error': 2}


def run_vale(path, config):
    """Return Vale's findings for one file as a list of dicts."""
    if shutil.which('vale') is None:
        raise SystemExit(
            'vale_report: vale is not installed.\n'
            '  macOS:  brew install vale\n'
            '  other:  https://vale.sh/docs/install\n'
            'Then run `vale sync` in the project root to fetch the style packages.')
    command = ['vale', '--output=JSON']
    if config:
        command += ['--config', config]
    command.append(path)
    result = subprocess.run(command, capture_output=True, text=True)
    if not result.stdout.strip():
        # Vale writes nothing on a clean run, and diagnostics on a broken config.
        if result.returncode not in (0, 1) or result.stderr.strip():
            raise SystemExit('vale_report: vale failed:\n' + result.stderr.strip())
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit('vale_report: could not parse vale output:\n' + result.stdout[:2000])
    if isinstance(payload, dict) and payload.get('Code'):
        raise SystemExit('vale_report: vale error: %s' % payload.get('Text', payload))
    return [item for items in payload.values() for item in items]


def locate(mapping, line):
    """Map a line of the extracted file to (source path, source line, kind)."""
    entry = mapping.get(str(line))
    if entry is None:
        return None, None, None
    return entry[0], entry[1], entry[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('prose', help='the Markdown file extract_prose.py wrote')
    parser.add_argument('--map', required=True, help='the line map it wrote beside it')
    parser.add_argument('--config', default=None, help='.vale.ini to use')
    parser.add_argument('--detail', action='store_true',
                        help='print every instance, not just a count per check')
    parser.add_argument('--limit', type=int, default=6,
                        help='instances to show per check without --detail (default 6)')
    parser.add_argument('--fail-on', default='error', choices=sorted(RANK),
                        help='lowest severity that fails the run (default error)')
    args = parser.parse_args()

    with open(args.map, encoding='utf-8') as handle:
        mapping = json.load(handle)

    findings = run_vale(args.prose, args.config)
    by_check = collections.defaultdict(list)
    for item in findings:
        path, line, kind = locate(mapping, item.get('Line', 0))
        if path is None:
            continue                      # a blank separator line; nothing to report
        by_check[(item.get('Check', '?'), item.get('Severity', 'warning'))].append(
            (path, line, kind, item.get('Message', '')))

    if not by_check:
        print('PROSE OK - vale reports nothing over %s' % os.path.basename(args.prose))
        return 0

    worst = 0
    order = sorted(by_check.items(), key=lambda kv: (-len(kv[1]), kv[0][0]))
    total = sum(len(v) for v in by_check.values())
    print('PROSE: %d findings across %d checks' % (total, len(by_check)))
    for (check, severity), hits in order:
        worst = max(worst, RANK.get(severity, 1))
        print('\n%-9s %-34s %d' % (severity.upper(), check, len(hits)))
        shown = hits if args.detail else hits[:args.limit]
        for path, line, kind, message in shown:
            print('  %s:%d: [%s] %s' % (path, line, kind, message))
        if len(hits) > len(shown):
            print('  ... and %d more' % (len(hits) - len(shown)))

    return 1 if worst >= RANK[args.fail_on] else 0


if __name__ == '__main__':
    sys.exit(main())
