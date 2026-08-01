#!/usr/bin/env python3
"""
Validate that labels assigned in a SkoolKit .ctl file stay within the length cap.

Labels never wrap in the HTML listing, so an over-long label opens a wide gutter
on every page that lists it. The cap is 24 characters; a violation is fixed by
renaming the label, never by clipping the column.
"""

import re
import sys

MAX_LABEL_LENGTH = 24

LABEL_RE = re.compile(r'^@ \$[0-9A-Fa-f]+ label=(\S+)')


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <ctl-file>", file=sys.stderr)
        return 2

    violations = []
    with open(sys.argv[1], encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            match = LABEL_RE.match(line)
            if match:
                label = match.group(1)
                if len(label) > MAX_LABEL_LENGTH:
                    violations.append((lineno, label))

    if violations:
        print(f"Found {len(violations)} label(s) over {MAX_LABEL_LENGTH} chars:")
        for lineno, label in violations:
            print(f"  Line {lineno}: {label} ({len(label)} chars)"
                  f" — rename it, never clip the column")
        return 1

    print(f"All labels within {MAX_LABEL_LENGTH} chars.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
