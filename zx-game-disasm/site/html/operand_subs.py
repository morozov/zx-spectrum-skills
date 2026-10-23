"""Render skool2html operands in the form the ASM output carries.

`skool2html` constructs its `SkoolParser` with no `asm_mode`, so `@isub` and
`@ssub` are never read and `substitute_labels` — the pass that turns an address
into an `@equ` name — is never run. The published listing therefore shows a raw
number wherever the ASM shows a named constant, and no command-line option,
`[Config]` key or `-c`/`-I` parameter reaches `asm_mode`.

Naming this module as `[Config] InitModule` replaces the `SkoolParser` name that
`skool2html` holds with a wrapper. The wrapper parses the skool a second time in
ASM mode and copies each instruction's operand text onto the parse the site is
built from, so the page and the `.asm` read alike.

Only `instruction.operation` and `instruction.reference` are touched, and only
after the parse has finished. The snapshot, the instruction byte values, the
entry sizes and the reference graph are all computed before this runs and are
left as they were, so nothing here can change what the disassembly assembles to
or what the image macros read.

The second parse is in @ssub mode, the mode the build renders the `.asm` in.
"""

import html as _html

from skoolkit import skool2html
from skoolkit.skoolparser import SkoolParser

# SkoolParser's asm_mode for @ssub, the mode `skool2asm -s` renders in.
SSUB_MODE = 2


def asm_operations(skoolfile, case, base, create_labels, asm_labels, label_fmt, variables):
    """Return {address: operand text} as the ASM output would spell it.

    Addresses carrying more than one instruction are left out: a sub directive
    that inserts or overwrites instructions makes the two parses disagree about
    what lives at that address, and there is then no one operand to copy.
    """
    parser = SkoolParser(skoolfile, case=case, base=base, asm_mode=SSUB_MODE,
                         create_labels=create_labels, asm_labels=asm_labels,
                         label_fmt=label_fmt, variables=variables)
    operations = {}
    for entry in parser.memory_map:
        for instruction in entry.instructions:
            if instruction.address is not None:
                operations.setdefault(instruction.address, []).append(instruction.operation)
    return {a: ops[0] for a, ops in operations.items() if len(ops) == 1}


def substituted_addr_str(old, new, addr_str):
    """Return the text `new` carries where `old` carried `addr_str`, or None.

    The two operations differ only in how their operands are spelled, so the
    text that replaced `addr_str` is what `new` holds between the parts of `old`
    that surround it. None means the correspondence is not unambiguous.
    """
    if old.count(addr_str) != 1:
        return None
    head, _, tail = old.partition(addr_str)
    if len(new) < len(head) + len(tail) or not new.startswith(head) or not new.endswith(tail):
        return None
    return new[len(head):len(new) - len(tail)] or None


def substitute_operands(parser, operations):
    """Rewrite each instruction's operand text, keeping its operand link.

    `HtmlWriter` builds an operand link by replacing `reference.addr_str` in the
    operation, so an address that has become a name would leave the link with
    nothing to wrap. Each reference is re-pointed at the text that took the
    address's place, and told to use that text rather than the target's label,
    so the link ends up around the name the reader now sees.
    """
    for entry in parser.memory_map:
        for instruction in entry.instructions:
            if instruction.address is None:
                continue
            new = operations.get(instruction.address)
            if new is None:
                continue
            new = _html.escape(new, False)
            if new == instruction.operation:
                continue
            reference = instruction.reference
            if reference is not None:
                addr_str = substituted_addr_str(instruction.operation, new, reference.addr_str)
                if addr_str is not None:
                    instruction.reference = reference._replace(addr_str=addr_str, use_label=False)
            instruction.operation = new


def _parse(skoolfile, **kwargs):
    parser = SkoolParser(skoolfile, **kwargs)
    if kwargs.get('html') and skoolfile != '-':
        substitute_operands(parser, asm_operations(
            skoolfile,
            kwargs.get('case', 0),
            kwargs.get('base', 0),
            kwargs.get('create_labels', False),
            kwargs.get('asm_labels', True),
            kwargs.get('label_fmt'),
            kwargs.get('variables', ())
        ))
    return parser


skool2html.SkoolParser = _parse
