#!/usr/bin/env python3
"""
Validate that every data entry in a SkoolKit .ctl file declares a checkable schema.

A data block must say what its bytes mean. The machine-checkable form of that
claim is a tiling: starting at the block's address, the sub-directives cover
every byte exactly once and sum to the block's size. A block that states nothing
about its bytes is not documented data — it is a region nobody has digested, and
code modeled as an undifferentiated byte span reads as clean under every other
check while relocating nothing.

Five checks, all arithmetic over directives the .ctl already carries:

  UNTYPED      a block with no sub-directives, a B/T span carrying no
               sublength, or the part of a block no render macro reaches, over
               the scalar threshold (default 8 bytes). `w` and `W` state the
               element size themselves and are exempt.
  ZEROFILL     (needs --bin) an all-zero span enumerated as a stride instead of
               declared a buffer — nothing checks a stride over zeros
  TILING       sub-directive lengths sum to the block size, contiguous from its
               address — no gaps, no overlaps, no leftovers
  DIVISIBILITY len % sublen == 0; a list of 2-byte words cannot be 7 bytes long
  POINTER      (needs --bin) a B span whose byte pairs land in-image at/above
               the relocatability floor is a pointer table typed as bytes

An unused entry (`u`) is exempt from every check here: its bytes have no layout
to declare.

A block drawn by an image or audio macro is exempt from UNTYPED: the macro is
the schema and the render is its proof. The macro may sit in the block's own
prose, or on a partner block the two name each other through — a beeper sound is
code plus data, so its #AUDIO lives on the player, not on the period table.

The exemption discharges over the bytes a macro actually reads, not over the
block a macro appears in. #UDGARRAY, #UDG and #FONT state their addresses, so
the covered set is arithmetic over the macro text: an array's UDG specs are
address ranges, each UDG is 8 bytes at its own step, and an attribute spec adds
one byte per cell. What those cover is discharged; what they leave is reported
as the remainder, because a block holding one sprite and 900 undescribed bytes
is the blob this check exists to catch.

#FRAMES, #SCR, #AUDIO and #UDGS state no byte range: a frame is defined by some
other macro elsewhere, a #SCR reads a display file at its `df`/`af` bases, and an
#AUDIO's delays come out of a simulated run. Their extent is not derivable from
the macro text, so they keep the whole-block exemption — the coverage they claim
is unmeasured, not assumed empty, and a block one of them draws stays exempt
as a whole. That is the blind spot this check carries.

Tiling proves accounting, not meaning: a wrong stride that happens to divide
passes, and a mis-typed field tiles. The check is necessary, not sufficient. Its
job is to make an unparsed span impossible to leave behind.
"""

import argparse
import re
import sys

import ctl_baseline

CHECK = 'data-structure'

# Block-level directives. Every entry that publishes bytes is checked, whatever
# letter groups its page. What an undeclared byte renders as differs by type —
# `DEFS` under `s`, `DEFB` under `b`, `g` and `u`, `DEFM` under `t`, `DEFW` under
# `w` — and only under `s` is it unused space. Under the rest it is published
# data the .ctl never declared, which is the same defect wearing a page title.
# Only `c` (it disassembles, and the round-trip proves it) and `i` (it publishes
# nothing) are outside the contract; they serve to bound the entry above them.
BLOCK_TYPES = 'bcgistuw'
DATA_BLOCK_TYPES = 'bgstuw'

# Sub-directives that cover a span of bytes. M groups sub-blocks that are
# themselves declared, so counting it as well would double-count the span.
SPAN_TYPES = 'BCSTW'

# Directives whose text is prose about the block, where a render macro may sit.
TEXT_TYPES = 'DNRE'
TEXT_RE = re.compile(r'^[%s] ' % TEXT_TYPES)

# A block drawn by one of these has declared its bytes in the strongest available
# form: the render is exercised, and a wrong extent draws visibly wrong. Macro
# parameters are word characters, so no word boundary ends a name and the longer
# alternatives must come first — otherwise `UDG` claims the first three letters
# of `UDGARRAY` and the rest of the macro reads as an address.
RENDER_MACRO_RE = re.compile(r'#(UDGARRAY|UDGTABLE|UDGS|UDG|FRAMES|FONT|AUDIO|SCR)')

# A macro parameter list outside parentheses, as SkoolKit's `parse_ints` reads
# it: comma-separated values, each positional or `name=value`, each a decimal or
# `$`-prefixed hex literal, and each omittable in favor of its default.
MACRO_INT = r'(?:\d+|\$[0-9A-Fa-f]+)'
MACRO_INT_RE = re.compile(MACRO_INT)
NAMED_PARAM = r'(?:[a-z]+=)?%s' % MACRO_INT
PARAM_LIST_RE = re.compile(r'(?:%s)?(?:,(?:%s)?)*' % (NAMED_PARAM, NAMED_PARAM))

# Parameter names, in SkoolKit's order, for the macros whose extent is
# arithmetic over their own text. Order is what makes a positional parameter
# readable, so the names that carry no address — scale, flip, rotate, tindex,
# alpha — are listed to hold their places rather than to be read.
UDGARRAY_PARAMS = ('width', 'attr', 'scale', 'step', 'inc', 'flip', 'rotate',
                   'mask', 'tindex', 'alpha')
UDG_PARAMS = ('addr',) + UDGARRAY_PARAMS[1:]
FONT_PARAMS = ('addr', 'chars', 'attr', 'scale', 'tindex', 'alpha')
UDG_SPEC_PARAMS = ('attr', 'step', 'inc')
MASK_SPEC_PARAMS = ('addr', 'step')

# A UDG is eight rows of eight pixels: eight bytes, one per row.
UDG_HEIGHT = 8

# The most characters #FONT draws, from character 32 up. SkoolKit clamps to this.
FONT_CHARS = 96

# A ceiling on the addresses one range spec may yield. A step that does not
# advance makes SkoolKit's own walk unbounded; a linter must stop instead.
RANGE_LIMIT = 0x10000

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

    data_blocks are its data entries in file order — every block type but `c` and
    `i`. Each carries its address, type, title, source line number, size (the next
    block's address minus its own; None for the last block, whose extent the file
    does not state), the span sub-directives inside it, and the text of its prose
    directives.

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


def bracketed(text, index, opening='(', closing=')'):
    """
    Return (body, end) for the bracketed group at `index`, or (None, index).

    `end` is the index just past the closing bracket. Nesting counts, so a
    filename group carrying alt text in parentheses comes back whole.
    """
    if index >= len(text) or text[index] != opening:
        return None, index
    depth = 0
    for end in range(index, len(text)):
        if text[end] == opening:
            depth += 1
        elif text[end] == closing:
            depth -= 1
            if depth == 0:
                return text[index + 1:end], end + 1
    return None, index


def macro_params(text, index, names):
    """
    Return ({name: value}, end) for a macro's parameter list, or (None, index).

    A parameter is positional or `name=value`, and one written empty is absent
    from the mapping so the caller's default stands. A parenthesized list may
    hold arithmetic and nested macros, which no read of the text resolves; that
    comes back None, and so does a name the macro does not take.
    """
    if index < len(text) and text[index] == '(':
        return None, index
    match = PARAM_LIST_RE.match(text, index)
    values = {}
    position = 0
    for part in (match.group().split(',') if match.group() else []):
        keyword, _, literal = part.rpartition('=')
        if keyword:
            if keyword not in names:
                return None, index
            position = names.index(keyword)
        else:
            literal = part
        if literal:
            if position >= len(names):
                return None, index
            values[names[position]] = parse_address(literal)
        position += 1
    return values, match.end()


def address_range(spec, index, width):
    """
    Return (addresses, end) for a UDG address range spec, or (None, index).

    The spec is `a[-b[-h[-v]]][xN]`, read as SkoolKit reads it: `a` alone is one
    address, `a-b` runs to `b`, `h` steps from one UDG to the next along a row of
    `width`, and `v` from the start of one row to the start of the next.

    `xN` appends N copies of the range, exactly as SkoolKit does. It names no new
    byte, but the list *length* is what the callers count: an attribute list is
    read positionally and stops at the end of the array's last row, so collapsing
    the repeats slides every later address into a slot SkoolKit never reaches and
    claims bytes it never reads. N copies of a long range can outrun the address
    space, and a spec that does comes back unmeasurable rather than huge.
    """
    elements = []
    end = index
    while True:
        match = MACRO_INT_RE.match(spec, end)
        if not match:
            return None, index
        elements.append(parse_address(match.group()))
        end = match.end()
        if len(elements) == 4 or end >= len(spec) or spec[end] != '-':
            break
        end += 1

    copies = 1
    if end < len(spec) and spec[end] == 'x':
        match = MACRO_INT_RE.match(spec, end + 1)
        if not match:
            return None, index
        copies = parse_address(match.group())
        end = match.end()

    if len(elements) < 2:
        elements.append(elements[0])
    if len(elements) < 3:
        elements.append(1)
    if len(elements) < 4:
        elements.append(elements[2] * width)
    address, last, h_step, v_step = elements

    addresses = []
    while address <= last:
        addresses.append(address)
        if len(addresses) % width:
            address += h_step
        else:
            address += v_step - (width - 1) * h_step
        if len(addresses) > RANGE_LIMIT:
            return None, index          # a step that does not advance
    if len(addresses) * copies > RANGE_LIMIT:
        return None, index
    return addresses * copies, end


def udg_bytes(addresses, step):
    """Return the bytes the given UDGs are drawn from: eight rows, `step` apart."""
    return {address + row * step for address in addresses for row in range(UDG_HEIGHT)}


def udgarray_extent(text, index):
    """
    Return the addresses a #UDGARRAY reads, or None when they are not derivable.

    The macro is `#UDGARRAYwidth[,attr,scale,step,inc,flip,rotate,mask,…]
    (UDGSPEC[;UDGSPEC…])[[ATTRSPEC[;ATTRSPEC…]]]`, and each UDGSPEC is an address
    range with its own optional `,attr,step,inc` and `:mask` tail. Attribute
    addresses are one byte per cell, read positionally and stopped at the end of
    the array's last row, which SkoolKit pads out to the full width, so a spec
    listing more addresses than that does not stretch the extent. A lone row
    shorter than the width is the shape SkoolKit leaves unpadded: an attribute
    spec that overruns it raises instead of reading, so the rounded-up count is a
    ceiling over a macro no build renders.

    `#UDGARRAY*frame…` builds an animation out of frames other macros defined and
    names no address of its own, so it comes back None.
    """
    if index < len(text) and text[index] == '*':
        return None
    params, end = macro_params(text, index, UDGARRAY_PARAMS)
    if params is None:
        return None
    width = params.get('width')
    if not width or width < 1:
        return None
    step, mask = params.get('step', 1), params.get('mask', 1)

    specs, end = bracketed(text, end)
    if specs is None:
        return None

    covered, cells = set(), 0
    for spec in specs.split(';'):
        addresses, at = address_range(spec, 0, width)
        if addresses is None:
            return None
        udg_step = step
        if at < len(spec) and spec[at] == ',':
            values, at = macro_params(spec, at + 1, UDG_SPEC_PARAMS)
            if values is None:
                return None
            udg_step = values.get('step', step)
        covered |= udg_bytes(addresses, udg_step)
        cells += len(addresses)
        if at < len(spec) and spec[at] == ':':
            masks, at = address_range(spec, at + 1, width)
            if masks is None:
                return None
            mask_step = udg_step
            if at < len(spec) and spec[at] == ',':
                values, at = macro_params(spec, at + 1, ('step',))
                if values is None:
                    return None
                mask_step = values.get('step', udg_step)
            if mask:
                covered |= udg_bytes(masks[:len(addresses)], mask_step)

    if end < len(text) and text[end] == '[':
        attrs, end = bracketed(text, end, '[', ']')
        if attrs is None:
            return None
        listed = []
        for spec in attrs.split(';'):
            addresses, _ = address_range(spec, 0, width)
            if addresses is None:
                return None
            listed.extend(addresses)
        covered |= set(listed[:-(-cells // width) * width])
    return covered


def udg_extent(text, index):
    """
    Return the addresses a #UDG reads, or None when they are not derivable.

    `#UDGaddr[,attr,scale,step,…][:maskaddr[,step]]` draws one 8-byte character,
    plus its mask when the macro asks for one.
    """
    params, end = macro_params(text, index, UDG_PARAMS)
    if params is None or 'addr' not in params:
        return None
    step = params.get('step', 1)
    covered = udg_bytes([params['addr']], step)
    if end < len(text) and text[end] == ':':
        values, end = macro_params(text, end + 1, MASK_SPEC_PARAMS)
        if values is None or 'addr' not in values:
            return None
        if params.get('mask', 1):
            covered |= udg_bytes([values['addr']], values.get('step', step))
    return covered


def font_extent(text, index):
    """
    Return the addresses a #FONT reads, or None when they are not derivable.

    `#FONTaddr,chars` draws the characters from code 32 up, eight bytes each,
    contiguous from `addr`. Without `chars` the macro draws a message instead,
    and which characters that names — hence which bytes — depends on text this
    does not expand.
    """
    params, _ = macro_params(text, index, FONT_PARAMS)
    if params is None or 'addr' not in params:
        return None
    chars = params.get('chars', 0)
    if chars < 1:
        return None
    return set(range(params['addr'],
                     params['addr'] + UDG_HEIGHT * min(chars, FONT_CHARS)))


EXTENT_READERS = {
    'UDGARRAY': udgarray_extent,
    'UDG': udg_extent,
    'FONT': font_extent,
}


def render_extent(prose):
    """
    Return the addresses the render macros in some prose read.

    None means one of them draws bytes this cannot name: #FRAMES redraws frames
    defined elsewhere, #UDGS assembles them, #SCR reads a display file at its
    `df`/`af` bases, and #AUDIO's delays come out of a simulated run. A macro
    whose parameters are arithmetic rather than literals reads the same way.
    None is "unmeasured", not "nothing", and the caller treats it as covering
    whatever block it is asked about.

    #UDGTABLE draws nothing itself: it opens a table whose cells hold the macros
    that do, and those are read here in their own right.
    """
    covered = set()
    for match in RENDER_MACRO_RE.finditer(prose):
        if match.group(1) == 'UDGTABLE':
            continue
        reader = EXTENT_READERS.get(match.group(1))
        if reader is None:
            return None
        extent = reader(prose, match.end())
        if extent is None:
            return None
        covered |= extent
    return covered


def rendered_coverage(block, by_address):
    """
    Return the addresses a render declares of a block, or None for all of them.

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

    Addresses outside the block are kept: the caller intersects, and a macro on a
    partner routine names the data block's addresses rather than its own.
    """
    covered = render_extent(block['prose'])
    if covered is None:
        return None

    for ref in REF_RE.findall(block['prose']):
        partner = by_address.get(parse_address(ref))
        if partner is None or partner['type'] != 'c':
            continue
        if not any(parse_address(back) == block['address']
                   for back in REF_RE.findall(partner['prose'])):
            continue
        drawn = render_extent(partner['prose'])
        if drawn is None:
            return None
        covered |= drawn
    return covered


def uncovered_runs(address, size, covered):
    """Return the [start, end) runs of a block's bytes that `covered` misses."""
    runs = []
    start = None
    for at in range(address, address + size):
        if at in covered:
            if start is not None:
                runs.append((start, at))
                start = None
        elif start is None:
            start = at
    if start is not None:
        runs.append((start, address + size))
    return runs


def render_discharges(block, covered):
    """
    Whether the coverage a render declares accounts for a whole block.

    True is the discharge: nothing further is asked of the block, because
    something exercised draws all of it. False leaves the block's spans to be
    asked about one at a time, and `covered` is what answers them — a caller
    tests a span against the same set it passed here, so the block granularity
    and the span granularity cannot answer differently about one file.

    `covered` is what `rendered_coverage` returned for this block. None is
    unmeasured coverage: a macro that states no byte range draws whatever it is
    asked about. The last block in the file is the other case read as presence —
    the file states no address after it, so there is no extent to measure a
    remainder against.
    """
    if covered is None:
        return True
    if block['size'] is None:
        return bool(covered)
    return not uncovered_runs(block['address'], block['size'], covered)


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

    `w` answers the question in the entry type, so it is asked nothing. Its bytes
    render one `DEFW` per word whether or not a `W` repeats the stride, so the
    directive this check would demand changes nothing published; and a word that
    names a labeled address assembles as that label, which is the relocation the
    untyped-span defect costs. `validate_ctl_array_elements.py` exempts a bare `w`
    entry for the same reason; it is a `W` sub-directive that it asks whether its
    words group into multi-word records and whether each element is annotated.
    """
    violations = []
    size = block['size']

    # A rendered asset: the macro is the schema, and drawing it is the proof.
    # Nobody should index 6144 screen pixels or 50 pitch periods to satisfy a
    # linter — those bytes are already declared by something that is exercised.
    # The discharge reaches only as far as the macro reads, so what it leaves is
    # asked about below exactly as if no macro were there.
    covered = rendered_coverage(block, by_address)
    if render_discharges(block, covered):
        return violations
    uncovered = []
    if size is not None:
        uncovered = uncovered_runs(block['address'], size, covered)

    if not block['spans']:
        if block['type'] == 'w':
            return violations
        left = sum(end - start for start, end in uncovered)
        if size is not None and left <= threshold:
            return violations
        if covered:
            message = (f"{left} of {size} bytes fall outside every render's extent, "
                       f"the first at ${uncovered[0][0]:04X} — the macros draw "
                       f"{size - left} bytes and declare nothing about the rest; "
                       f"widen them or state its stride")
        else:
            extent = 'unbounded' if size is None else f'{size} bytes'
            # A partner exemption is invisible from the prose that holds it open:
            # it reads as an ordinary cross-reference, so an edit that strips a
            # sentence can close it from another file, and this fires in an entry
            # the edit never opened. Say so, because nothing else will.
            message = (f"{extent} with no sub-directives — declare the stride, "
                       f"cover it with a render, or model it as code. If this "
                       f"block was passing before, check whether a prose edit "
                       f"removed the #R that named its render's partner: the "
                       f"exemption needs the two blocks to name each other, and "
                       f"the link can be anywhere in the body")
        violations.append((block['line_number'], 'UNTYPED', message))
        return violations

    for span in block['spans']:
        if covered.issuperset(range(span['address'], span['address'] + span['length'])):
            # Drawn: this span's bytes are the render's, and it is their schema.
            continue
        if span['type'] == 'S':
            # A skip block's size is its whole claim: N bytes of buffer.
            continue
        if span['type'] == 'W':
            # `W` is the answer to "bytes of what?": words, two bytes each. A
            # sublength on it groups words into records, which is a different
            # question and a different check's.
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
        description='Validate that data entries in a .ctl declare a checkable schema.')
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
    ctl_baseline.add_arguments(parser)
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
        if block['type'] == 'u':
            # Bytes nothing uses have no layout to declare: asking an unused entry
            # for a stride, a tiling or a type would invent structure for them.
            continue
        found = check_untyped(block, args.threshold, by_address)
        found += check_tiling(block)
        found += check_divisibility(block)
        if image is not None:
            found += check_zerofill(block, args.threshold, image, args.org)
            found += check_pointers(block, image, args.org, args.reloc_floor, addresses)
        for line_number, kind, message in found:
            violations.append((line_number, kind, message, block))
    violations.sort(key=lambda v: v[0])

    with open(args.ctl, encoding='utf-8') as f:
        lines = f.read().splitlines()

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(
            args.baseline, CHECK,
            *ctl_baseline.write(args.baseline, CHECK, violations, lines))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, violations, lines,
                                              report_stale=not args.ignore_stale)

    if new:
        print(f"Found {len(new)} data-block schema violation(s) "
              f"in {len(blocks)} data entry(ies):")
        print()
        for line_number, kind, message, block in new:
            print(f"  Line {line_number}: {kind} — {message}")
            print(f"    in {block['type']} ${block['address']:04X} {block['title']}")
            print()

    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
