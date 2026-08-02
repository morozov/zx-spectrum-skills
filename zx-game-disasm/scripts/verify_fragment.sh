#!/usr/bin/env bash
# Round-trip a Worker's per-routine .ctl fragment in isolation: splice it over its
# own address range into a throwaway copy of the canonical .ctl, disassemble,
# reassemble to a byte-identical program image, and run the linters and the
# skool2asm warning gate — touching no shared file. On success prints
# `verify-frag: OK`; any failure exits non-zero with the offending output.
#
# Usage: verify_fragment.sh <base.ctl> <fragment.ctl> <pristine.z80> <pristine.bin> <scripts-dir>
set -euo pipefail

CTL="$1"; FRAG="$2"; Z80="$3"; BIN="$4"; SCRIPTS="$5"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Splice the fragment over its address range. The fragment owns a contiguous span
# from its lowest block address up to (but not including) the next base block that
# starts above its highest block address; every base line in that span is dropped
# and the fragment inserted in its place. This handles a b->c reclassification,
# which splice_ctl.py (a c-block-for-c-block replace) does not.
python3 - "$CTL" "$FRAG" > "$tmp/game.ctl" <<'PY'
import sys, re
base = open(sys.argv[1]).read().splitlines()
frag = open(sys.argv[2]).read().splitlines()

BLOCK = re.compile(r'^([bcwtsgi]) \$([0-9A-Fa-f]+)')
def block_addr(line):
    m = BLOCK.match(line)
    return int(m.group(2), 16) if m else None

ADDR = re.compile(r'^[@A-Za-z*>\s]*\$([0-9A-Fa-f]+)')
def line_addr(line):
    m = ADDR.match(line)
    return int(m.group(1), 16) if m else None

fa = [block_addr(l) for l in frag if block_addr(l) is not None]
if not fa:
    sys.exit("fragment has no block-start line")
fmin, fmax = min(fa), max(fa)
above = sorted(a for a in (block_addr(l) for l in base)
               if a is not None and a > fmax)
end = above[0] if above else None

out, inserted = [], False
for l in base:
    a = line_addr(l)
    if a is not None and a >= fmin and (end is None or a < end):
        if not inserted:
            out.extend(frag)
            inserted = True
        continue
    out.append(l)
if not inserted:
    sys.exit("fragment range not found in base .ctl")
print('\n'.join(out))
PY

# Disassemble; no overlapping-instruction or other warning is allowed.
sna2skool.py --hex "$Z80" --ctl "$tmp/game.ctl" > "$tmp/game.skool" 2>"$tmp/sna.err" \
  || { cat "$tmp/sna.err" >&2; exit 1; }
if grep -qi 'warning\|overlap' "$tmp/sna.err"; then cat "$tmp/sna.err" >&2; exit 1; fi

# Reassemble with label creation; a warning (e.g. an address not resolvable to a
# label) is a hard failure, exactly as in the full build.
skool2asm.py --create-labels "$tmp/game.skool" > "$tmp/game.asm" 2>"$tmp/asm.err" \
  || { cat "$tmp/asm.err" >&2; exit 1; }
if grep -q WARNING "$tmp/asm.err"; then cat "$tmp/asm.err" >&2; exit 1; fi

pasmo --bin "$tmp/game.asm" "$tmp/game.bin" 2>"$tmp/pasmo.err" \
  || { cat "$tmp/pasmo.err" >&2; exit 1; }
cmp "$tmp/game.bin" "$BIN"

# The .ctl linters that gate the real build.
"$SCRIPTS/validate_ctl_address_order.py"     "$tmp/game.ctl"
"$SCRIPTS/validate_ctl_instruction_order.py" "$tmp/game.ctl"
"$SCRIPTS/validate_ctl_lengths.py"           "$tmp/game.ctl"
"$SCRIPTS/validate_ctl_label_length.py"      "$tmp/game.ctl"

# Advisory comment-quality pre-filter over the spliced skool.
"$SCRIPTS/lint_comments.py" "$tmp/game.skool" || true

echo "verify-frag: OK"
