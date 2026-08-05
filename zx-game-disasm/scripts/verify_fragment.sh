#!/usr/bin/env bash
# Round-trip a Worker's per-routine .ctl fragment in isolation: splice it over its
# own address range into a throwaway copy of the canonical .ctl, disassemble,
# reassemble to a byte-identical program image, and run the linters and the
# skool2asm warning gate — touching no shared file. On success prints
# `verify-frag: OK`; any failure exits non-zero with the offending output.
#
# Usage: verify_fragment.sh <base.ctl> <fragment.ctl> <pristine.z80> <pristine.bin>
#                           <scripts-dir> <baseline> <org> <reloc-floor> <size>
set -euo pipefail

CTL="$1"; FRAG="$2"; Z80="$3"; BIN="$4"; SCRIPTS="$5"
BASELINE="$6"; ORG="$7"; RELOC_FLOOR="$8"; SIZE="$9"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# The splice keeps the project's own .ctl filename. The prose check keys its
# baseline on the file a phrase sits in, so a throwaway name would make every
# inherited finding look new.
SPLICED="$tmp/$(basename "$CTL")"

# Splice the fragment over its address range. The fragment owns a contiguous span
# from its lowest block address up to (but not including) the next base block that
# starts above its highest block address; every base line in that span is dropped
# and the fragment inserted in its place. This handles a b->c reclassification.
python3 - "$CTL" "$FRAG" > "$SPLICED" <<'PY'
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
sna2skool.py --hex "$Z80" --ctl "$SPLICED" > "$tmp/game.skool" 2>"$tmp/sna.err" \
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

# Every .ctl linter that gates the real build, so a fragment cannot pass here and
# fail the Manager's `make`. The two content checks read the project's baseline:
# its key is the directive's address, so a finding the fragment inherited is still
# held after the splice moves its line.
"$SCRIPTS/validate_ctl_address_order.py"     "$SPLICED"
"$SCRIPTS/validate_ctl_instruction_order.py" "$SPLICED"
"$SCRIPTS/validate_ctl_lengths.py"           "$SPLICED"
"$SCRIPTS/validate_ctl_label_length.py"      "$SPLICED"

# --ignore-stale: clearing a baselined finding is the fragment doing its job, and
# the Worker cannot edit the shared baseline to record it. Dropping the line is
# the Manager's, at the full `make`. What the fragment must not do is add one.
"$SCRIPTS/validate_ctl_identity.py"       "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale
"$SCRIPTS/validate_ctl_data_structure.py" "$SPLICED" --bin "$BIN" \
    --org "$ORG" --reloc-floor "$RELOC_FLOOR" --baseline "$BASELINE" --ignore-stale
"$SCRIPTS/validate_ctl_publication.py"    "$SPLICED" \
    --org "$ORG" --size "$SIZE" --baseline "$BASELINE" --ignore-stale

# The prose sweep runs over the spliced .ctl alone. The `.ref` catalogs are not
# spliced, so their findings are the project's, not the fragment's, and a Worker
# cannot answer for them here.
"$SCRIPTS/validate_prose_names.py"        "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale

# `lint-images` has no counterpart here: it reads the built site, and a fragment
# does not build one. The Manager's `make` is where that outcome is checked.

# Advisory comment-quality pre-filter over the spliced skool.
"$SCRIPTS/lint_comments.py" "$tmp/game.skool" || true

echo "verify-frag: OK"
