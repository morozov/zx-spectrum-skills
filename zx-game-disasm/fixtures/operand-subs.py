#!/usr/bin/env python3
"""Print each instruction's operand text as the site would render it.

Expected: both listings read as the .asm does - `@ssub` and labels in the main
one, labels in the [OtherCode] one, which skool2html parses through
`SkoolParser.clone`.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'site', 'html'))
import operand_subs  # noqa: E402,F401  (installs the wrappers)
from skoolkit import skool2html  # noqa: E402

main = skool2html.SkoolParser(os.path.join(HERE, 'operand-subs-main.skool'), html=True)
other = main.clone(os.path.join(HERE, 'operand-subs-other.skool'))
for name, parser in (('main', main), ('other', other)):
    for entry in parser.memory_map:
        for instruction in entry.instructions:
            print(f'{name} ${instruction.address:04X} {instruction.operation}')
