#!/usr/bin/env python3
"""Print each routine's block counts as the coverage gauge reads them."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import coverage_report  # noqa: E402

routines, _ = coverage_report.analyze(sys.argv[1])
for r in routines:
    print(f"{r['name']}: {r['blocks']} block(s), {r['bare_blocks']} bare")
