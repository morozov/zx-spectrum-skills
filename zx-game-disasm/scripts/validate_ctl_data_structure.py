#!/usr/bin/env python3
"""
Validate that every b/s block in a SkoolKit .ctl file declares a checkable schema.

A data block must say what its bytes mean. The machine-checkable form of that
claim is a tiling: starting at the block's address, the sub-directives cover
every byte exactly once and sum to the block's size. A block that states nothing
about its bytes is not documented data — it is a region nobody has digested, and
code modeled as an undifferentiated byte span reads as clean under every other
check while relocating nothing.

Five checks, all arithmetic over directives the .ctl already carries:

  UNTYPED      a block with no sub-directives, or a B/W/T span carrying no
               sublength, over the scalar threshold (default 8 bytes)
  ZEROFILL     (needs --bin) an all-zero span enumerated as a stride instead of
               declared a buffer — nothing checks a stride over zeros
  TILING       sub-directive lengths sum to the block size, contiguous from its
               address — no gaps, no overlaps, no leftovers
  DIVISIBILITY len % sublen == 0; a list of 2-byte words cannot be 7 bytes long
  POINTER      (needs --bin) a B span whose byte pairs land in-image at/above
               the relocatability floor is a pointer table typed as bytes

A block drawn by an image or audio macro is exempt from UNTYPED: the macro is
the schema and the render is its proof. The macro may sit in the block's own
prose, or on a partner block the two name each other through — a beeper sound is
code plus data, so its #AUDIO lives on the player, not on the period table. The
exemption reads a macro's presence, not its extent, so a macro covering part of a
block clears the whole of it. Computing #UDGARRAY extents would close that, and
would be the stronger form.

Tiling proves accounting, not meaning: a wrong stride that happens to divide
passes, and a mis-typed field tiles. The check is necessary, not sufficient. Its
job is to make an unparsed span impossible to leave behind.
"""

import argparse
import re
import sys

# Block-level directives. A b/s block is data this script checks; any other
# block type (code, text, words, ignored) only serves to bound the one above it.
BLOCK_TYPES = 'bcgistuw'
DATA_BLOCK_TYPES = 'bs'

# Sub-directives that cover a span of bytes. M groups sub-blocks that are
# themselves declared, so counting it as well would double-count the span.
SPAN_TYPES = 'BCSTW'

# Directives whose text is prose about the block, where a render macro may sit.
TEXT_TYPES = 'DNRE'
TEXT_RE = re.compile(r'^[%s] ' % TEXT_TYPES)

# A block drawn by one of these has declared its bytes in the strongest available
# form: the render is exercised, and a wrong extent draws visibly wrong.
RENDER_MACRO_RE = re.compile(r'#(UDGARRAY|UDGTABLE|UDG|FRAMES|FONT|AUDIO|SCR)')

# A #R cross-reference. A data table and the routine that renders it name each
# other through these, which is how a table reaches a render it does not hold.
REF_RE = re.compile(r'#R(\$?[0-9A-Fa-f]{4,5})\b')

BLOCK_RE = re.compile(r'^([%s]) +(\$?[0-9A-Fa-f]+) *(.*)$' % BLOCK_TYPES)
LABEL_RE = re.compile(r'^@ +(\$?[0-9A-Fa-f]+) +label=')
SPAN_RE = re.compile(r'^([%s]) +(\$?[0-9A-Fa-f]+),([^ ]+)' % SPAN_TYPES)


def parse_address(text):
    """Return the integer value of a ctl address, hex with `$` or plain decimal."""
    if text.startswith('$'):
        return int(text[1:], 16)
    return int(text, 10)


def parse_sublengths(spec):
    """
    Return the byte size of each sublength spec in a directive's operand tail.

    The tail of `B $F000,64,8` is `64,8`: a length followed by sublength specs.
    A spec may be a plain size (`8`), a colon-joined mix summing to one
    statement (`21:1` is 22), or either with a `*N` repeat (`c1*3` is 3). A
    leading type letter is SkoolKit's per-statement type override and carries no
    size, so it is dropped.

    Returns (length, [sublength, ...]) or None if the tail is not parseable.
    """
    parts = spec.split(',')
    try:
        length = int(parts[0])
    except ValueError:
        return None

    sublengths = []
    for part in parts[1:]:
        total = 0
        for item in part.split(':'):
            item = re.sub(r'^[bcdhmnBCDHMNtT]', '', item)
            repeat = 1
            if '*' in item:
                item, _, mult = item.partition('*')
                try:
                    repeat = int(mult)
                except ValueError:
                    return None
            if not item:
                continue
            try:
                total += int(item) * repeat
            except ValueError:
                return None
        if total:
            sublengths.append(total)
    return (length, sublengths)


def parse_ctl(path):
    """
    Return (data_blocks, addresses) for a .ctl.

    data_blocks are its b/s blocks in file order. Each carries its address,
    type, title, source line number, size (the next block's address minus its
    own; None for the last block, whose extent the file does not state), the
    span sub-directives inside it, and the text of its prose directives.

    addresses is every address the file names — block starts of any type, plus
    `@ addr label=` entry points. A pointer table points at what the .ctl has
    named, and a real one often targets a labeled entry mid-block rather than
    a block start.
    """
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    blocks = []
    labeled = set()
    for i, line in enumerate(lines):
        label_match = LABEL_RE.match(line)
        if label_match:
            labeled.add(parse_address(label_match.group(1)))

        block_match = BLOCK_RE.match(line)
        if block_match:
            blocks.append({
                'type': block_match.group(1),
                'address': parse_address(block_match.group(2)),
                'title': block_match.group(3).strip(),
                'line_number': i + 1,
                'spans': [],
                'text': '',
            })
            continue

        if TEXT_RE.match(line) and blocks:
            blocks[-1]['text'] += line
            continue

        span_match = SPAN_RE.match(line)
        if span_match and blocks:
            parsed = parse_sublengths(span_match.group(3))
            if parsed is None:
                continue
            length, sublengths = parsed
            blocks[-1]['spans'].append({
                'type': span_match.group(1),
                'address': parse_address(span_match.group(2)),
                'length': length,
                'sublengths': sublengths,
                'line_number': i + 1,
            })

    for block, following in zip(blocks, blocks[1:]):
        block['size'] = following['address'] - block['address']
    if blocks:
        blocks[-1]['size'] = None

    for block in blocks:
        block['prose'] = block['title'] + '\n' + block['text']

    addresses = labeled | {b['address'] for b in blocks}
    by_address = {b['address']: b for b in blocks}
    return ([b for b in blocks if b['type'] in DATA_BLOCK_TYPES], addresses, by_address)


def is_rendered_asset(block, by_address):
    """
    Whether a block's bytes are declared by a render, its own or a partner's.

    A render is the strongest declaration available: it is exercised, and a wrong
    byte draws or sounds wrong. Usually the macro sits in the block's own prose.

    A beeper sound effect is the case where it cannot. Such a sound is code plus
    data — the table holds the pitch periods, the routine holds the cadence and
    the cycle counts — so only the routine can produce it, and the #AUDIO lives
    there. The table reaches its render through the `#R` the author already wrote.

    Two conditions keep that from becoming a loophole:

    - the link is mutual, because prose names a routine for all sorts of reasons
      and an incidental one-way `#R` would exempt a real blob;
    - the partner is a *code* block, because a render on code cannot be drawing
      its own bytes — code is not a bitmap — so it must be rendering the data it
      reads. A render on a *data* block draws that block's own bytes and says
      nothing about anyone else's. Without this, a working copy would be exempted
      by the source bank it is filled from: they name each other, the source is
      drawn, and the copy still holds whatever the capture caught.
    """
    if RENDER_MACRO_RE.search(block['prose']):
        return True

    for ref in REF_RE.findall(block['prose']):
        partner = by_address.get(parse_address(ref))
        if partner is None or partner['type'] != 'c':
            continue
        if not RENDER_MACRO_RE.search(partner['prose']):
            continue
        if any(parse_address(back) == block['address']
               for back in REF_RE.findall(partner['prose'])):
            return True
    return False


def reads_all_zero(address, length, image, origin):
    """
    Whether a span is entirely zero in the image, or None if it is not covered.

    All-zero is a fact about the snapshot, never about the data: a live variable
    the game writes at runtime reads zero in a cold capture, and so does a
    structured map before a level loads. It narrows the question, it does not
    answer it.
    """
    if image is None or length is None or length <= 0:
        return None
    start = address - origin
    if start < 0 or start + length > len(image):
        return None
    return not any(image[start:start + length])


def check_untyped(block, threshold, by_address):
    """
    Report a block that declares no structure over the scalar threshold.

    This is the first failing case, and the one that matters: the defect this
    gate exists for is a byte span with no sub-directives at all, which a check
    written as "sub-directives must be typed" sails straight past.
    """
    violations = []
    size = block['size']

    # A rendered asset: the macro is the schema, and drawing it is the proof.
    # Nobody should index 6144 screen pixels or 50 pitch periods to satisfy a
    # linter — the bytes are already declared by something that is exercised.
    if is_rendered_asset(block, by_address):
        return violations

    if not block['spans']:
        if size is None or size > threshold:
            extent = 'unbounded' if size is None else f'{size} bytes'
            violations.append((block['line_number'], 'UNTYPED',
                               f"{extent} with no sub-directives — declare the stride, "
                               f"cover it with a render, or model it as code"))
        return violations

    for span in block['spans']:
        if span['type'] == 'S':
            # A skip block's size is its whole claim: N bytes of buffer.
            continue
        if span['length'] > threshold and not span['sublengths']:
            violations.append((span['line_number'], 'UNTYPED',
                               f"{span['type']} ${span['address']:04X},{span['length']} "
                               f"has no sublength — {span['length']} bytes of what?"))
    return violations


def check_zerofill(block, threshold, image, origin):
    """
    Report an all-zero span that is enumerated instead of declared a buffer.

    Over a span of zeros there is nothing for a stride to be checked against —
    `162 % 2 == 0` passes for any even length — so laying one out at
    `B addr,len,sublen` renders a wall of identical `DEFB $00` rows, buys no
    verification, and crowds the page. `S` states the one claim the image can
    settle: the size. The runtime layout belongs in the block's prose.

    Scoped to the span, never the block, because a listing line is earned by what
    it documents: a per-byte scalar carrying its own comment is a length-1 span
    and stays, while one undifferentiated 162-byte span is the defect.
    """
    violations = []
    for span in block['spans']:
        if span['type'] == 'S' or span['length'] <= threshold:
            continue
        if reads_all_zero(span['address'], span['length'], image, origin):
            rows = span['length'] // (span['sublengths'][0] if span['sublengths'] else 8)
            violations.append((span['line_number'], 'ZEROFILL',
                               f"{span['type']} ${span['address']:04X},{span['length']} "
                               f"is all-zero in the image but enumerated as ~{rows} rows "
                               f"— compact it to `S ${span['address']:04X},"
                               f"{span['length']}` and put the layout in the prose "
                               f"(make the block `s` if that is all it holds)"))
    return violations


def check_tiling(block):
    """Report gaps, overlaps and leftovers between a block's spans."""
    violations = []
    if not block['spans'] or block['size'] is None:
        return violations

    cursor = block['address']
    for span in block['spans']:
        if span['address'] > cursor:
            violations.append((span['line_number'], 'TILING',
                               f"gap of {span['address'] - cursor} byte(s) before "
                               f"${span['address']:04X} — ${cursor:04X} is undeclared"))
        elif span['address'] < cursor:
            violations.append((span['line_number'], 'TILING',
                               f"${span['address']:04X} overlaps the preceding span, "
                               f"which runs to ${cursor - 1:04X}"))
        cursor = span['address'] + span['length']

    end = block['address'] + block['size']
    if cursor < end:
        violations.append((block['line_number'], 'TILING',
                           f"{end - cursor} byte(s) undeclared at ${cursor:04X} — the "
                           f"block runs to ${end - 1:04X}"))
    elif cursor > end:
        violations.append((block['line_number'], 'TILING',
                           f"spans run {cursor - end} byte(s) past the block, which "
                           f"ends at ${end - 1:04X}"))
    return violations


def check_divisibility(block):
    """Report a span whose length is not a whole number of its own elements."""
    violations = []
    for span in block['spans']:
        for sublength in span['sublengths']:
            if sublength and span['length'] % sublength:
                violations.append((span['line_number'], 'DIVISIBILITY',
                                   f"{span['type']} ${span['address']:04X}: "
                                   f"{span['length']} bytes is not a whole number of "
                                   f"{sublength}-byte elements "
                                   f"({span['length'] % sublength} left over)"))
    return violations


def check_pointers(block, image, origin, floor, targets):
    """
    Report a B span that reads as a table of in-image pointers.

    Heuristic: every byte pair in the span resolves to an address at/above the
    relocatability floor that some block in the .ctl actually starts at. Typed
    B, those addresses are literal bytes that no shifted build relocates — the
    same defect as code modeled as data, wearing a different hat.

    Landing in-image is far too weak a test on its own: a bit-reverse lookup
    table is bytes whose every pair reads as a plausible high address. Requiring
    the target to be a declared block start is what separates a pointer from a
    coincidence.
    """
    violations = []
    for span in block['spans']:
        # A single 2-byte B counts: an enumerated table is one directive per
        # entry, and one pointer typed as bytes is already the defect.
        if span['type'] != 'B' or span['length'] < 2 or span['length'] % 2:
            continue
        start = span['address'] - origin
        if start < 0 or start + span['length'] > len(image):
            continue
        words = [image[start + i] | (image[start + i + 1] << 8)
                 for i in range(0, span['length'], 2)]
        # A uniform run is a bitmap or a fill, not a table: every pair reads as
        # the same address, so one coincidence would otherwise count many times.
        if len(words) > 1 and len(set(words)) == 1:
            continue
        if all(w >= floor and w in targets for w in words):
            violations.append((span['line_number'], 'POINTER',
                               f"B ${span['address']:04X},{span['length']}: every byte "
                               f"pair resolves to a declared address at/above "
                               f"${floor:04X} — a pointer table typed as bytes; "
                               f"W makes it relocate"))
    return violations


def main():
    parser = argparse.ArgumentParser(
        description='Validate that b/s blocks in a .ctl declare a checkable schema.')
    parser.add_argument('ctl', help='the .ctl file to validate')
    parser.add_argument('--threshold', type=lambda s: int(s, 0), default=8,
                        help='scalar threshold: a block at or under this many bytes is '
                             'named rather than tiled (default 8)')
    parser.add_argument('--bin', dest='binary',
                        help='the game image, enabling the pointer-table check')
    parser.add_argument('--org', type=lambda s: int(s, 0), default=0x4000,
                        help='address the --bin image loads at (default $4000)')
    parser.add_argument('--reloc-floor', type=lambda s: int(s, 0), default=0x5B00,
                        help='addresses at/above this are the game region (default $5B00)')
    args = parser.parse_args()

    try:
        blocks, addresses, by_address = parse_ctl(args.ctl)
    except FileNotFoundError:
        print(f"Error: File not found: {args.ctl}")
        return 1

    image = None
    if args.binary:
        try:
            with open(args.binary, 'rb') as f:
                image = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.binary}")
            return 1

    violations = []
    for block in blocks:
        found = check_untyped(block, args.threshold, by_address)
        found += check_tiling(block)
        found += check_divisibility(block)
        if image is not None:
            found += check_zerofill(block, args.threshold, image, args.org)
            found += check_pointers(block, image, args.org, args.reloc_floor, addresses)
        for line_number, kind, message in found:
            violations.append((line_number, kind, block, message))

    if not violations:
        return 0

    print(f"Found {len(violations)} data-block schema violation(s) "
          f"in {len(blocks)} b/s block(s):")
    print()
    for line_number, kind, block, message in sorted(violations):
        print(f"  Line {line_number}: {kind} — {message}")
        print(f"    in {block['type']} ${block['address']:04X} {block['title']}")
        print()
    return 1


if __name__ == '__main__':
    sys.exit(main())
