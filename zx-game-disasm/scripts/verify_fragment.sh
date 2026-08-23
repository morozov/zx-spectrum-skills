#!/usr/bin/env bash
# Round-trip a Worker's per-routine .ctl fragment in isolation: splice it over its
# own address range into a throwaway copy of the canonical .ctl, disassemble,
# reassemble to a byte-identical program image, assemble the fixed source under
# the project's own flags, and run the linters and both skool2asm warning gates —
# touching no shared file. On success prints
# `verify-frag: OK`, naming the fixed-asm flags it gated under; any failure exits
# non-zero with the offending output.
#
# The round-trip is a chain — no .skool, no .asm, no image to compare — so it
# halts at the first stage that fails, and says that no check ran. The .ctl checks
# after it are independent of each other and are swept: every one runs, and the
# run ends in one verdict line naming each that failed and with how many findings.
# A Worker who fixes the one reported finding and re-runs, twice, pays three
# round-trips for what one run can tell them. The sweep itself is
# `scripts/lint_sweep.sh`, shared with the gate's `lint`.
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

# Halt the round-trip, naming the stage and saying that the .ctl sweep below it
# never ran. Without that the reader is left to read a `cmp` difference as the
# whole verdict, when it is the only thing that got as far as being checked.
abort() { # <stage>
    echo "verify-frag: FAILED at $1, before any .ctl check ran — no check here" \
         "has a finding count, and none of them is what failed." >&2
    exit 1
}

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

BLOCK = re.compile(r'^([bcgistuw]) \$([0-9A-Fa-f]+)')  # every block type, `u` included
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

# This splices one contiguous span, so a fragment holding two non-adjacent
# entries would delete every base entry between them and then fail at the render
# on the missing labels — which reads as a defect in the fragment. Refuse it
# instead, and say which entries would have gone.
covered = set(fa)
between = sorted(a for a in (block_addr(l) for l in base)
                 if a is not None and fmin < a < fmax and a not in covered)
if between:
    sys.exit("fragment covers non-adjacent entries: splicing it as one span would "
             "delete %d base entr%s between them (%s%s). Verify one entry per "
             "fragment, then splice the combined fragment with splice_ctl.py, "
             "which replaces block for block."
             % (len(between), 'y' if len(between) == 1 else 'ies',
                ', '.join('$%04X' % a for a in between[:6]),
                ', …' if len(between) > 6 else ''))

above = sorted(a for a in (block_addr(l) for l in base)
               if a is not None and a > fmax)
end = above[0] if above else None

# A `.` paragraph-continuation line carries no address of its own — and the `$79`
# in one is an item code, not an address — so it has to inherit the block above
# it. Without that it survives a replace that deletes its block, leaving orphaned
# prose dangling after the new entry, which no drop report covers.
out, inserted, last = [], False, None
for l in base:
    a = line_addr(l)
    if a is None:
        if l.strip():
            a = last
    else:
        last = a
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

# Name every `@` directive the splice above deleted because the fragment does not
# carry it forward. Reporting only: a fragment whose task was to remove a
# directive is indistinguishable from one that lost it, so this never fails the
# check. It exits non-zero only for a fragment with no block-entry line, which the
# splice already rejected.
"$SCRIPTS/splice_ctl.py" --check-only "$CTL" "$FRAG"

# Disassemble; no overlapping-instruction or other warning is allowed.
sna2skool.py --hex "$Z80" --ctl "$SPLICED" > "$tmp/game.skool" 2>"$tmp/sna.err" \
  || { cat "$tmp/sna.err" >&2; abort "the disassembly"; }
if grep -qi 'warning\|overlap' "$tmp/sna.err"; then
    cat "$tmp/sna.err" >&2; abort "the disassembly"
fi

# Reassemble with label creation; a warning (e.g. an address not resolvable to a
# label) is a hard failure, exactly as in the full build. This is the non-fixed
# source, the one the round-trip cmp is taken over.
skool2asm.py --create-labels "$tmp/game.skool" > "$tmp/game.asm" 2>"$tmp/asm.err" \
  || { cat "$tmp/asm.err" >&2; abort "the non-fixed render"; }
if grep -q WARNING "$tmp/asm.err"; then
    cat "$tmp/asm.err" >&2; abort "the non-fixed render"
fi

pasmo --bin "$tmp/game.asm" "$tmp/game.bin" 2>"$tmp/pasmo.err" \
  || { cat "$tmp/pasmo.err" >&2; abort "assembling the non-fixed source"; }
cmp "$tmp/game.bin" "$BIN" || abort "the round-trip cmp"

# The fixed source, under the project's own flags. `-s` is the strict static
# relocatability gate and is the default, so a fragment that leaves an in-image
# operand raw fails here — where its author can see it — instead of in the
# Manager's `make` over the integrated .ctl, attributed to nobody. A project that
# has opted out passes no flag and is held to exactly what its build holds it to.
# Nothing is compared to the image: @ofix/@isub make the fixed bytes differ from
# the original by design, which is what the non-fixed cmp above is for.
skool2asm.py --create-labels -f 1 "$@" "$tmp/game.skool" > "$tmp/fixed.asm" 2>"$tmp/fixed.err" \
  || { cat "$tmp/fixed.err" >&2; abort "the fixed render"; }
if grep -q WARNING "$tmp/fixed.err"; then
    cat "$tmp/fixed.err" >&2; abort "the fixed render"
fi

# The build assembles that source too, and a clean render does not mean it
# assembles: an `@ssub=LD (lbl+1),A` naming a label that does not exist renders
# without a warning and fails only here. Assembling it is what makes the fragment
# check gate on what `make` gates on.
pasmo --bin "$tmp/fixed.asm" "$tmp/fixed.bin" 2>"$tmp/fixed-pasmo.err" \
  || { cat "$tmp/fixed-pasmo.err" >&2; abort "assembling the fixed source"; }

# Every .ctl linter that gates the real build, so a fragment cannot pass here and
# fail the Manager's `make`. The content checks read the project's baseline: its
# key is the directive's address, so a finding the fragment inherited is still
# held after the splice moves its line.
#
# They are independent of each other, so they are swept rather than chained: each
# one runs whatever the last one did, and the run ends in one verdict line naming
# every check that failed and with how many findings. Chained, what comes back is
# whichever check comes first in this list, and that need not be the one the
# fragment broke. Every check here reads the whole spliced .ctl, so any of them
# can be red over a finding outside the fragment's range that the baseline does
# not hold and a Worker cannot fix from a fragment; chained, such a check stops
# the run and the fragment's own findings, further down the list, are never
# reached.
. "$SCRIPTS/lint_sweep.sh"
lint_begin

lint_run address-order     "$SCRIPTS/validate_ctl_address_order.py"     "$SPLICED"
lint_run instruction-order "$SCRIPTS/validate_ctl_instruction_order.py" "$SPLICED"
lint_run lengths           "$SCRIPTS/validate_ctl_lengths.py"           "$SPLICED"
lint_run label-length      "$SCRIPTS/validate_ctl_label_length.py"      "$SPLICED"

# --ignore-stale: clearing a baselined finding is the fragment doing its job, and
# the Worker cannot edit the shared baseline to record it. Dropping the line is
# the Manager's, at the full `make`. What the fragment must not do is add one.
lint_run identity "$SCRIPTS/validate_ctl_identity.py" "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale
lint_run data-structure "$SCRIPTS/validate_ctl_data_structure.py" "$SPLICED" \
    --bin "$BIN" --org "$ORG" --reloc-floor "$RELOC_FLOOR" \
    --baseline "$BASELINE" --ignore-stale
# The skool passed here is the one disassembled from the spliced .ctl above, so
# the MUTABLE check reads the code as the fragment's own map lays it out.
lint_run publication "$SCRIPTS/validate_ctl_publication.py" "$SPLICED" \
    --org "$ORG" --size "$SIZE" --skool "$tmp/game.skool" \
    --baseline "$BASELINE" --ignore-stale
lint_run array-elements "$SCRIPTS/validate_ctl_array_elements.py" "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale

# The prose sweep runs over the spliced .ctl alone. The `.ref` catalogs are not
# spliced, so their findings are the project's, not the fragment's, and a Worker
# cannot answer for them here.
lint_run names "$SCRIPTS/validate_prose_names.py" "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale
lint_run byte-counts "$SCRIPTS/validate_ctl_byte_counts.py" "$SPLICED" \
    --baseline "$BASELINE" --ignore-stale
# Reads the skool disassembled from the spliced .ctl, so the dominator trees are
# built over the fragment's own map — the same reason `publication` gets it.
lint_run label-namespace "$SCRIPTS/validate_ctl_label_namespace.py" "$SPLICED" \
    --skool "$tmp/game.skool" --baseline "$BASELINE" --ignore-stale

# Comment-quality check over the spliced skool. It runs ahead of the verdict so a
# red sweep still carries it: it is what the Challenger reads, and a fragment
# being sent back over a finding is when its author most wants it.
# `comments` gates in `make`, so it gates here: a fragment carrying an `OPEN`
# marker must not be green here and red in the Manager's `make`, which is the one
# thing this script promises cannot happen. It needs the project's baseline for
# the same reason every other gating check does.
lint_run comments "$SCRIPTS/lint_comments.py" "$tmp/game.skool" \
    --baseline "$BASELINE"

# `terms` likewise: the registry in glossary.ref gates the build, and a fragment
# that reintroduces a banned spelling should fail where it is written.
lint_run terms "$SCRIPTS/validate_glossary_terms.py" "$SPLICED" \
    --registry "$(dirname "$CTL")/glossary.ref" --baseline "$BASELINE"

# The `lint_run` calls above. The count is written out rather than derived from
# the gate's, which is larger by `lint-images` — the one gating check with no
# counterpart here, because it reads the built site and a fragment builds none. A
# number carried over from the makefile would keep its old count if the gate
# gained a check this file did not, which is worse than saying so in words.
lint_report 13

echo "verify-frag: OK [fixed-asm flags: $FIXED_FLAGS] — every .ctl check the gate" \
     "runs, except the checks that read the built site. A fragment builds no" \
     "site, so those stay the Manager's \`make\` to settle."
echo "verify-frag: a clean sweep is not a round-trip. These are .ctl checks; that" \
     "the spliced source still assembles to the original bytes is the Manager's" \
     "\`make\`, and no linter here implies it."
