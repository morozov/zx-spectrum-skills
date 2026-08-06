#!/usr/bin/env bash
# Fixture for `make verify-frag`: does the fragment check gate on the same
# skool2asm flags the project's build does?
#
# It cannot be a .ctl alone. The check round-trips a fragment against a real
# program image and runs under the framework's own make rule, so the fixture is
# a throwaway 13-byte project: it writes the image, a base .ctl, three
# fragments and a Makefile into a temp dir, then runs `make verify-frag` three
# times.
#
# The image is self-modifying code. `LD ($F00A),A` patches the operand of the
# `CALL` at $F009, and $F00A is not an instruction boundary, so `--create-labels`
# cannot resolve it. The base .ctl fixes that the documented way, with an
# `@ssub` (see references/build-verify.md, "the LBL+1 technique"); the raw
# fragment drops the `@ssub` line and leaves the operand raw. That is a Worker's
# realistic mistake: re-annotating a routine and losing a directive that only
# ever renders under `-s`. The third fragment keeps the `@ssub` but names a label
# that does not exist — the other realistic mistake with the same directive, and
# one no skool2asm warning reports.
#
# Expected, with the SkoolKit tools and pasmo on PATH:
#
#   fixtures/verify-frag-flags.sh
#   -> clean fragment,     ASM_FIXED_FLAGS=-s (default): accepted
#      raw fragment,       ASM_FIXED_FLAGS=-s (default): rejected, `WARNING:
#                                                        Unreplaced address ($F00A)`
#      raw fragment,       ASM_FIXED_FLAGS= (opted out): accepted
#      bad-@ssub fragment, ASM_FIXED_FLAGS=-s (default): rejected, `ERROR: Symbol
#                                                        'no_such_label' is undefined`
#   -> `verify-frag-flags: OK`, exit 0
#
# The last two are the point. Assembled with `--create-labels` and nothing else,
# the raw fragment is accepted; rendered but not assembled, the bad `@ssub`
# passes, and only the build's pasmo would catch it. The tools run from PATH; without them the fixture
# exits 1 naming what is missing, rather than reporting the rejection cases as PASS.
set -euo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Preflight, before anything is written or built, in the shape disassembly.mk
# uses. Two of the four cases below score a nonzero `make` as the expected
# rejection, so an absent toolchain reports them as PASS; and the image is built
# with bin2sna.py, which make never preflights because no rule invokes it. The
# tools are the fixture's own plus the ones `make verify-frag` shells out to.
missing=""
for tool in bin2sna.py tap2sna.py sna2skool.py skool2asm.py pasmo; do
    command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
if [ -n "$missing" ]; then
    {
        echo "verify-frag-flags: toolchain incomplete — not executable on PATH:$missing."
        echo "The SkoolKit tools come from the packages in requirements.txt."
    } >&2
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

cat > probe.ctl <<'EOF'
@ $F000 start
@ $F000 org
@ $F000 label=entry
c $F000 Entry point
  $F000 Patch and run the indirect call.
  $F003
@ $F004 label=patch_and_call
c $F004 Patch a CALL operand in place and call it
D $F004 The routine writes the address to call into the operand of the CALL below. The patched byte sits inside that instruction, so no label can name it.
  $F004 Low byte of the address to call.
@ $F006 ssub=LD (patched_call+1),A
  $F006 Patch the CALL operand.
@ $F009 label=patched_call
  $F009 Call the address just patched.
  $F00C
i $F00D
EOF

# The fragment a Worker returns for `patch_and_call`, minus the @ssub: same
# range, same labels, one raw in-image operand.
grep -v 'ssub=' probe.ctl | sed -n '/^@ \$F004/,/^  \$F00C$/p' > frag-raw.ctl
# The same fragment with the @ssub kept — the shape that must stay accepted.
sed -n '/^@ \$F004/,/^  \$F00C$/p' probe.ctl > frag-ok.ctl
# The @ssub kept but its label mistyped: renders without a warning, assembles
# never.
sed 's/patched_call+1/no_such_label+1/' frag-ok.ctl > frag-badssub.ctl

cat > Makefile <<EOF
GAME = probe
ORG  = 61440
SIZE = 13
PC   = 61440
SP   = 65535
include $SKILL/tools/disassembly.mk
EOF

# CALL \$F004 / RET / LD A,\$05 / LD (\$F00A),A / CALL \$0000 / RET
python3 -c 'import sys; sys.stdout.buffer.write(bytes(
    [0xCD,0x04,0xF0, 0xC9, 0x3E,0x05, 0x32,0x0A,0xF0, 0xCD,0x00,0x00, 0xC9]))' \
    > probe.pristine.bin
bin2sna.py --org 0xF000 probe.pristine.bin probe.pristine.z80 >/dev/null

# The image is supplied, not downloaded: the .t2s exists only so make finds the
# pristine files current and never runs tap2sna.
touch probe.t2s
touch probe.pristine.z80 probe.pristine.bin

fail=0
expect() { # <what> <expected-status: accept|reject> <make args...>
    local what="$1" want="$2"; shift 2
    local out status
    set +e; out="$(make "$@" 2>&1)"; status=$?; set -e
    if [ "$want" = accept ] && [ $status -eq 0 ]; then
        echo "PASS  $what: accepted"
    elif [ "$want" = reject ] && [ $status -ne 0 ]; then
        echo "PASS  $what: rejected"
    else
        echo "FAIL  $what: wanted $want, make exited $status"; fail=1
    fi
    printf '%s\n' "$out" | sed 's/^/      | /'
}

expect "clean fragment, default flags" accept \
    verify-frag FRAG=frag-ok.ctl
expect "raw-operand fragment, default flags" reject \
    verify-frag FRAG=frag-raw.ctl
expect "raw-operand fragment, project opted out" accept \
    verify-frag FRAG=frag-raw.ctl ASM_FIXED_FLAGS=
expect "bad-@ssub fragment, default flags" reject \
    verify-frag FRAG=frag-badssub.ctl

[ $fail -eq 0 ] || { echo "verify-frag-flags: FAILED"; exit 1; }
echo "verify-frag-flags: OK"
