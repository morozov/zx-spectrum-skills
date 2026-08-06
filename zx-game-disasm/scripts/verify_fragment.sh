#!/usr/bin/env bash
# Round-trip a Worker's per-routine .ctl fragment in isolation: splice it over its
# own address range into a throwaway copy of the canonical .ctl, disassemble,
# reassemble to a byte-identical program image, assemble the fixed source under
# the project's own flags, and run the linters and both skool2asm warning gates —
# touching no shared file. On success prints
# `verify-frag: OK`, naming the fixed-asm flags it gated under; any failure exits
# non-zero with the offending output.
#
# Usage: verify_fragment.sh <base.ctl> <fragment.ctl> <pristine.z80> <pristine.bin>
#                           <scripts-dir> <baseline> <org> <reloc-floor> <size>
#                           [fixed-asm flag ...]
set -euo pipefail

CTL="$1"; FRAG="$2"; Z80="$3"; BIN="$4"; SCRIPTS="$5"
BASELINE="$6"; ORG="$7"; RELOC_FLOOR="$8"; SIZE="$9"

# Everything past the fixed nine is $(ASM_FIXED_FLAGS) — the flag list the
# project's fixed-asm rule passes to skool2asm, `-s` by default and empty for a
# project that has opted out of the strict gate. It is a list, so it goes last
# and stays in "$@": an empty one then expands to no argument at all, and a
# caller adding a flag never has to renumber a positional.
shift 9
FIXED_FLAGS="${*:-none}"

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
# label) is a hard failure, exactly as in the full build. This is the non-fixed
# source, the one the round-trip cmp is taken over.
skool2asm.py --create-labels "$tmp/game.skool" > "$tmp/game.asm" 2>"$tmp/asm.err" \
  || { cat "$tmp/asm.err" >&2; exit 1; }
if grep -q WARNING "$tmp/asm.err"; then cat "$tmp/asm.err" >&2; exit 1; fi

pasmo --bin "$tmp/game.asm" "$tmp/game.bin" 2>"$tmp/pasmo.err" \
  || { cat "$tmp/pasmo.err" >&2; exit 1; }
cmp "$tmp/game.bin" "$BIN"

# The fixed source, under the project's own flags. `-s` is the strict static
# relocatability gate and is the default, so a fragment that leaves an in-image
# operand raw fails here — where its author can see it — instead of in the
# Manager's `make` over the integrated .ctl, attributed to nobody. A project that
# has opted out passes no flag and is held to exactly what its build holds it to.
# Nothing is compared to the image: @ofix/@isub make the fixed bytes differ from
# the original by design, which is what the non-fixed cmp above is for.
skool2asm.py --create-labels -f 1 "$@" "$tmp/game.skool" > "$tmp/fixed.asm" 2>"$tmp/fixed.err" \
  || { cat "$tmp/fixed.err" >&2; exit 1; }
if grep -q WARNING "$tmp/fixed.err"; then cat "$tmp/fixed.err" >&2; exit 1; fi

# The build assembles that source too, and a clean render does not mean it
# assembles: an `@ssub=LD (lbl+1),A` naming a label that does not exist renders
# without a warning and fails only here. Assembling it is what makes the fragment
# check gate on what `make` gates on.
pasmo --bin "$tmp/fixed.asm" "$tmp/fixed.bin" 2>"$tmp/fixed-pasmo.err" \
  || { cat "$tmp/fixed-pasmo.err" >&2; exit 1; }

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
# The skool passed here is the one disassembled from the spliced .ctl above, so
# the MUTABLE check reads the code as the fragment's own map lays it out.
"$SCRIPTS/validate_ctl_publication.py"    "$SPLICED" \
    --org "$ORG" --size "$SIZE" --skool "$tmp/game.skool" \
    --baseline "$BASELINE" --ignore-stale

# The prose sweep runs over the spliced .ctl alone. The `.ref` catalogs are not
# spliced, so their findings are the project's, not the fragment's, and a Worker
# cannot answer for them here.
"$SCRIPTS/validate_prose_names.py"        "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale
"$SCRIPTS/validate_ctl_byte_counts.py"    "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale

# `lint-images` has no counterpart here: it reads the built site, and a fragment
# does not build one. The Manager's `make` is where that outcome is checked.

# Advisory comment-quality pre-filter over the spliced skool.
"$SCRIPTS/lint_comments.py" "$tmp/game.skool" || true

echo "verify-frag: OK [fixed-asm flags: $FIXED_FLAGS]"
