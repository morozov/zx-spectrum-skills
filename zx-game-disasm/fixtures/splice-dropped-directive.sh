#!/usr/bin/env bash
# Fixture for splice_ctl.py: does a fragment that fails to carry a directive
# forward say so, and is a drop a warning rather than an error?
#
# The splice replaces a block wholesale, so every `@` directive inside the
# replaced range that the fragment does not repeat is deleted. The realistic way
# that happens is a Worker re-typing a block instead of copying it out of the
# current `.ctl`: the labels come back, the `@ssub` and the `@keep` do not, the
# fragment still round-trips, and the annotation is gone with nothing said.
#
# Two properties are under test, and they pull against each other.
#
#   Named. Each dropped directive is reported on stderr with its address and its
#     directive, at the moment the splice deletes it.
#   Not fatal. The splice still runs and exits 0. A fragment whose task was to
#     remove a now-unnecessary `@keep` is indistinguishable from one that lost it,
#     so the tool reports and the author judges. A fatal drop would also have no
#     route through `make verify-frag`, which takes the fragment and nothing else.
#
# A directive whose value changed is not a drop — `frag-relabel.ctl` re-points an
# `@ label=` and must stay silent — because the comparison keys on address plus
# directive name, not on the line.
#
# `--check-only` reports the same drops over the fragment's address span and
# writes nothing, for a caller that performs its own splice. `frag-retype.ctl`
# retypes a `b` block to `c`: blocks pair by address whatever their type, so the
# splice takes the retype and names the field label it drops.
#
# The `.ctl` here is the same 13-byte self-modifying probe as
# `fixtures/verify-frag-flags.sh`, plus a two-byte record, so the directives are
# ones a real fragment carries. Nothing is assembled: the splice is text.
#
# Expected:
#
#   fixtures/splice-dropped-directive.sh
#   -> clean fragment:            no warning, exit 0
#      drop fragment:             `@ $F006 ssub=…` and `@ $F009 keep` named,
#                                 exit 0, both gone from the spliced .ctl
#      re-label fragment:         no warning, exit 0
#      drop fragment --check-only: the same two named, no file written
#      retype fragment:           `@ $F00E label=player_y` named, exit 0,
#                                 the block spliced in as `c $F00D`
#      retype fragment --check-only: `@ $F00E label=player_y` named, exit 0
#   -> `splice-dropped-directive: OK`, exit 0
set -euo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPLICE="$SKILL/scripts/splice_ctl.py"

command -v python3 >/dev/null 2>&1 || {
    echo "splice-dropped-directive: python3 is not executable on PATH." >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

# $F000 CALL $F004 / RET, $F004 the self-modifying patch-and-call routine,
# $F00D a two-byte player-position record.
cat > base.ctl <<'EOF'
@ $F000 start
@ $F000 org
@ $F000 label=entry
c $F000 Entry point
  $F000 Patch and run the indirect call.
  $F003
@ $F004 label=patch_and_call
c $F004 Patch a CALL operand in place and call it
D $F004 Self-modifying code: the address to call is written into the operand of the CALL below.
  $F004 Low byte of the address to call.
@ $F006 ssub=LD (patched_call+1),A
  $F006 Patch the CALL operand.
@ $F009 label=patched_call
@ $F009 keep
  $F009 Call the address just patched.
  $F00C
b $F00D Player position
@ $F00D label=player_x
@ $F00E label=player_y
B $F00D,2 Player X and Y, in pixels from the play-area origin.
i $F00F
EOF

# The block as a Worker who copied it out and edited it hands it back.
sed -n '/^@ \$F004/,/^  \$F00C$/p' base.ctl > frag-ok.ctl
# The same block retyped by hand: the labels came back, the `@ssub` and the
# `@keep` did not.
grep -v -e 'ssub=' -e '^@ \$F009 keep$' frag-ok.ctl > frag-drop.ctl
# An entry label re-pointed. Not a drop.
sed 's/label=patch_and_call/label=patch_call_indirect/' frag-ok.ctl > frag-relabel.ctl
# The record retyped as code, losing one of its two field labels.
cat > frag-retype.ctl <<'EOF'
@ $F00D label=player_state
c $F00D Player position update
  $F00D Advance the player by its current velocity.
EOF

fail=0
run() { # <what> <expected-status: accept|reject> <splice args...>
    local what="$1" want="$2"; shift 2
    set +e; OUT="$(python3 "$SPLICE" "$@" 2>&1)"; STATUS=$?; set -e
    if [ "$want" = accept ] && [ $STATUS -eq 0 ]; then
        echo "PASS  $what: accepted"
    elif [ "$want" = reject ] && [ $STATUS -ne 0 ]; then
        echo "PASS  $what: rejected"
    else
        echo "FAIL  $what: wanted $want, splice_ctl.py exited $STATUS"; fail=1
    fi
    printf '%s\n' "$OUT" | sed 's/^/      | /'
}

want_in() { # <what> <needle>
    if printf '%s\n' "$OUT" | grep -qF -- "$2"; then echo "PASS  $1"
    else echo "FAIL  $1: no \"$2\" in the output"; fail=1; fi
}
want_not_in() { # <what> <needle>
    if printf '%s\n' "$OUT" | grep -qF -- "$2"; then
        echo "FAIL  $1: unexpected \"$2\" in the output"; fail=1
    else echo "PASS  $1"; fi
}

cp base.ctl out-ok.ctl
run "clean fragment" accept out-ok.ctl frag-ok.ctl
want_not_in "clean fragment: silent" "WARNING"

cp base.ctl out-drop.ctl
run "drop fragment" accept out-drop.ctl frag-drop.ctl
want_in     "drop fragment: names the dropped @ssub"  '@ $F006 ssub=LD (patched_call+1),A'
want_in     "drop fragment: names the dropped @keep"  '@ $F009 keep'
want_in     "drop fragment: says the splice deletes them" "2 directive(s) in the replaced range"
want_not_in "drop fragment: says nothing of the kept label" '@ $F009 label=patched_call'
OUT="$(cat out-drop.ctl)"
want_not_in "drop fragment: the @ssub really is gone" "ssub="
want_not_in "drop fragment: the @keep really is gone" '@ $F009 keep'

cp base.ctl out-relabel.ctl
run "re-label fragment" accept out-relabel.ctl frag-relabel.ctl
want_not_in "re-label fragment: a changed value is not a drop" "WARNING"

cp base.ctl out-unwritten.ctl
run "drop fragment, --check-only" accept --check-only out-unwritten.ctl frag-drop.ctl
want_in "check-only: names the dropped @ssub" '@ $F006 ssub=LD (patched_call+1),A'
want_in "check-only: names the dropped @keep" '@ $F009 keep'
if cmp -s base.ctl out-unwritten.ctl; then echo "PASS  check-only: wrote nothing"
else echo "FAIL  check-only: the base was modified"; fail=1; fi

cp base.ctl out-retype.ctl
run "retype fragment" accept out-retype.ctl frag-retype.ctl
want_in     "retype fragment: names the field label the retype drops" '@ $F00E label=player_y'
OUT="$(cat out-retype.ctl)"
want_in     "retype fragment: the block is spliced in as code" 'c $F00D Player position update'
want_not_in "retype fragment: the field label really is gone" 'label=player_y'

run "retype fragment, --check-only" accept --check-only base.ctl frag-retype.ctl
want_in     "check-only: names the field label the retype drops" '@ $F00E label=player_y'
want_not_in "check-only: the re-pointed entry label is not a drop" '@ $F00D label=player_x'

[ $fail -eq 0 ] || { echo "splice-dropped-directive: FAILED"; exit 1; }
echo "splice-dropped-directive: OK"
