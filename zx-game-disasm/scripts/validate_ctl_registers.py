#!/usr/bin/env python3
"""
Validate the register rows (`R` directives) of a .ctl: one register per row, and
one style for what the row says.

REG_MULTI - a row that names more than one register.

  `R $9100 I:HL destination, DE source, B byte count` is three rows. The register
  column is what a reader scans, so each register gets its own row, and a second
  register inside a description (", DE source", " and BC count") never gets one.

REG_STYLE - a description that is not written as a phrase.

  A row says what the register holds as a noun phrase that starts in lower case
  and carries no final full stop: "pointer to the string (bit 7 set marks the
  final character)". A leading digit, `$`, `#R` or an acronym such as `Z` or `HL`
  is not a capitalized word and passes. A capitalized first word or a trailing
  period reads as a sentence, and a table of rows in two styles reads as careless.

REG_EMPTY - a row with a direction but no register.

  `R $F100 O: updates the heading` has nothing in the register column. A result
  with no register belongs in the entry's description, not in a row.

REG_BARE - a description of one word.

  "destination", "source" and "attribute" name a role and tell the reader nothing:
  not what the register holds, not its encoding or limit. The one exception is
  "unchanged", which is the whole statement on a register a routine preserves.

Usage: validate_ctl_registers.py CTL [--baseline FILE] [--write-baseline]
Exit 0 when clean, 1 when a row breaks the rule.
"""

import argparse
import os
import re
import sys

import ctl_baseline

CHECK = 'registers'

ROW_RE = re.compile(r'^R \$?[0-9A-Fa-f]+ (?P<dir>[IO]):(?P<reg>\S*)(?: (?P<text>.*))?$')
WORD_RE = re.compile(r"[A-Za-z']+")
# A second register inside a description: ", DE ..." or " and BC ...".
SECOND_REG_RE = re.compile(r'(?:,| and| \+)\s+(?:HL|DE|BC|IX|IY|AF|SP)\b(?!\')')


def scan(path):
    """Return the register-row findings in one .ctl, as (lineno, kind, message)."""
    findings = []
    with open(path, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            match = ROW_RE.match(raw.rstrip('\n'))
            if not match:
                continue
            reg = match.group('reg')
            text = (match.group('text') or '').strip()
            if not reg:
                findings.append((lineno, 'REG_EMPTY',
                                 f"the row has no register ('{match.group('dir')}:'): say it in the "
                                 'entry description and delete the row'))
            elif re.search(r'[,/&]', reg) or re.search(r'\b[IO]:', text):
                findings.append((lineno, 'REG_MULTI',
                                 f"the row names more than one register ('{match.group('dir')}:{reg}'): "
                                 'give each register its own row'))
            elif SECOND_REG_RE.search(text):
                findings.append((lineno, 'REG_MULTI',
                                 'the description names a second register: give it its own row'))
            if not text:
                continue
            first = WORD_RE.match(text)
            if first:
                word = first.group(0)
                if len(word) > 1 and word[0].isupper() and word[1:].islower():
                    findings.append((lineno, 'REG_STYLE',
                                     f"'{word}' starts the description in capitals: write it as a "
                                     'lower-case phrase'))
            if text.endswith('.') and not text.endswith('..'):
                findings.append((lineno, 'REG_STYLE',
                                 'the description ends in a full stop: it is a phrase, not a sentence'))
            if len(text.split()) == 1 and text.lower() != 'unchanged':
                findings.append((lineno, 'REG_BARE',
                                 f"'{text}' names a role and says nothing about what the register "
                                 'holds: give its meaning, encoding or limit'))
    return findings


def main():
    parser = argparse.ArgumentParser(
        description='Validate that register rows name one register each and share one style.')
    parser.add_argument('ctl', help='the .ctl file to check')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    try:
        with open(args.ctl, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f'Error: File not found: {args.ctl}')
        return 1

    findings = scan(args.ctl)

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, findings, lines))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, findings, lines,
                                              report_stale=not args.ignore_stale)

    if new:
        print(f'Found {len(new)} register row finding(s):')
        print()
        for lineno, kind, message in new:
            print(f'  {os.path.basename(args.ctl)}:{lineno}: {kind} — {message}')
            print(f'    {lines[lineno - 1].strip()[:120]}')
            print()
    elif not held and not stale:
        print('registers: every row names one register, as a lower-case phrase')

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
