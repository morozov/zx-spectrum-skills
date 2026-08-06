#!/usr/bin/env bash
# Fixture for scripts/ctl_baseline.py: can a regeneration grow lint-baseline.txt?
#
# The file records the debt a check inherited when it landed, never debt taken on
# afterwards, so `--write-baseline` must refuse a rewrite that adds a key. The
# sequence under test is the one that must not work: introduce a finding, run the
# regeneration, commit green.
#
# Refusing is not the only shape that fails. Writing the file and exiting non-zero
# would also fail once - and would leave the finding baselined, so the next `make`
# is green and only a revert undoes it. Refusing leaves the tree and the verdict
# agreeing, which is what the cases below assert with `cmp`.
#
# Two checks share the file here, because one check's refusal must not stop
# another from re-recording, and each check owns only its own lines. `identity`
# keys on a directive address; `byte-counts` keys on the address of the
# instruction comment and carries the recited count in its message, which is what
# makes the rewording case checkable: the message is not part of the key, so a
# check whose wording drifts rewrites without reading as growth.
#
# Adoption is the one legitimate growth - a project recording what a check finds
# the first time it runs there. It needs `--adopt`, it is recorded as an
# `# adopted:` line in the file's own header, and it is refused for anything that
# header already declares. That is what the last three cases are for: a check
# whose findings were all fixed owns no line, exactly as a check that never ran
# here owns none, so while adoption was read off the lines a clean check was
# adoptable and the forbidden sequence worked one flag deeper.
#
# `--adopt-kind` is the second granularity, for a kind the check itself gained
# after the project adopted it. Its findings predate the kind by construction, so
# they are inherited debt arriving under a name the header already declares.
#
# Nothing is assembled: every check here reads .ctl text. `make lint-baseline`
# propagating the status is not exercised here - that needs a built project - see
# references/build-verify.md.
#
# Expected:
#
#   fixtures/baseline-monotonic.sh
#   -> adopt identity, then byte-counts:   accepted, each records its own lines
#      regenerate unchanged:               accepted, no keys added or dropped
#      new finding at a new address:       REFUSED, `+ identity UNDESCRIBED $F00A`
#      second finding at a listed address: REFUSED, `+ identity UNDESCRIBED $F009`
#      the same, with --adopt:             REFUSED, identity is declared
#      byte-counts while identity is red:  accepted, its own line drops
#      byte-counts reworded:               accepted, message rewritten, no growth
#      identity finding cleared:           accepted, and the inherited line drops
#      finding on the now-clean identity,
#        with --adopt:                     REFUSED, identity is declared
#      a kind the header never declared:   REFUSED without a flag; accepted with
#                                          `--adopt-kind UNTITLED_ENTRY`
#      a second finding of that kind:      REFUSED, the kind is declared
#   -> `baseline-monotonic: OK`, exit 0
set -euo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IDENTITY="$SKILL/scripts/validate_ctl_identity.py"
BYTE_COUNTS="$SKILL/scripts/validate_ctl_byte_counts.py"

command -v python3 >/dev/null 2>&1 || {
    echo "baseline-monotonic: python3 is not executable on PATH." >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

# Two instruction comments reciting a byte count, and one sub-directive that
# neither describes nor labels its bytes: three findings a mature project would
# have inherited, across two checks.
cat > probe.ctl <<'EOF'
@ $F000 start
@ $F000 org
@ $F000 label=entry
c $F000 Entry point
  $F000 Clear 163 bytes of tile map.
  $F003 Zero the 22 bytes of player state.
  $F006 Fall into the main loop.
b $F009 Player state
B $F009,2
i $F00B
EOF
cp probe.ctl base.ctl

fail=0
run() { # <what> <expected-status: accept|refuse> <check> <extra args...>
    local what="$1" want="$2" check="$3"; shift 3
    local status
    cp lint-baseline.txt before.txt 2>/dev/null || : > before.txt
    set +e
    OUT="$(python3 "$check" probe.ctl --baseline lint-baseline.txt \
                   --write-baseline "$@" 2>&1)"; status=$?
    set -e
    if [ "$want" = accept ] && [ $status -eq 0 ]; then
        echo "PASS  $what: accepted"
    elif [ "$want" = refuse ] && [ $status -ne 0 ]; then
        echo "PASS  $what: refused (exit $status)"
    else
        echo "FAIL  $what: wanted $want, the check exited $status"; fail=1
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
# A refused first regeneration must not create the file either, so "unchanged"
# has to cover the case where it does not exist yet.
want_unchanged() { # <what>
    if [ "$(cat lint-baseline.txt 2>/dev/null || true)" = "$(cat before.txt)" ]; then
        echo "PASS  $1: wrote nothing"
    else echo "FAIL  $1: the baseline was rewritten"; fail=1; fi
}
want_lines() { # <what> <check> <count>
    local got; got="$(grep -c "^$2 " lint-baseline.txt || true)"
    if [ "$got" = "$3" ]; then echo "PASS  $1"
    else echo "FAIL  $1: $2 owns $got line(s), wanted $3"; fail=1; fi
}
want_declared() { # <what> <entry> <count>
    local got; got="$(grep -c "^# adopted: $2\$" lint-baseline.txt || true)"
    if [ "$got" = "$3" ]; then echo "PASS  $1"
    else echo "FAIL  $1: the header declares \"$2\" $got time(s), wanted $3"; fail=1; fi
}

# --- adoption: the one growth that is not debt taken on -----------------------

run "first regeneration, no --adopt" refuse "$IDENTITY"
want_in "first regeneration: names the key it will not record" \
        "+ identity UNDESCRIBED \$F009"
want_in "first regeneration: points at the deliberate route" "--adopt"
want_unchanged "first regeneration"

run "adopt identity" accept "$IDENTITY" --adopt
want_in    "adopt identity: says it adopted" "adopted"
want_lines "adopt identity: records its own finding" identity 1
want_lines "adopt identity: records nothing for byte-counts" byte-counts 0

run "adopt byte-counts" accept "$BYTE_COUNTS" --adopt
want_lines "adopt byte-counts: records its own two findings" byte-counts 2
want_lines "adopt byte-counts: leaves identity's line alone" identity 1

run "re-adopt identity, nothing changed" accept "$IDENTITY" --adopt
want_not_in "re-adopt with nothing to add: not treated as growth" "REFUSED"

# --- the sequence that must not work ------------------------------------------

# The record split into two fields, the second of them anonymous: one finding at
# an address the file lists, one at an address it does not.
sed 's/^B \$F009,2$/B $F009,1\nB $F00A,1/' base.ctl > probe.ctl
run "new finding at a new address" refuse "$IDENTITY"
want_in     "new address: names the added key" "+ identity UNDESCRIBED \$F00A"
want_not_in "new address: says nothing of the inherited one" \
            "+ identity UNDESCRIBED \$F009"
want_in     "new address: says the file still fails the gate" "unchanged"
want_unchanged "new address"

# The same record wrapped in an anonymous multi-byte directive: two findings at
# $F009 against the one line the file records for it. The key is unchanged, so
# only the count says a finding was taken on.
sed 's/^B \$F009,2$/M $F009,2\nB $F009,2/' base.ctl > probe.ctl
run "second finding at a listed address" refuse "$IDENTITY"
want_in "listed address: names the key the count added" "+ identity UNDESCRIBED \$F009"
want_unchanged "listed address"

run "second finding at a listed address, with --adopt" refuse "$IDENTITY" --adopt
want_in "--adopt on a check that has lines: refused" "adopted once"
want_unchanged "--adopt on a check that has lines"

# --- one check's refusal does not block another -------------------------------

# identity is still red on probe.ctl. byte-counts has a fix to record.
sed -i.bak 's/Zero the 22 bytes of player state./Zero the player state./' probe.ctl
run "byte-counts, while identity is refusing" accept "$BYTE_COUNTS"
want_in    "byte-counts: names the line the fix drops" "- byte-counts BYTE_SPAN \$F003"
want_lines "byte-counts: its own section shrank" byte-counts 1
want_lines "byte-counts: identity's line survived untouched" identity 1

# --- a reworded message is not growth -----------------------------------------

# The check's message quotes the count it found, so recording "163-byte" instead
# of "163 bytes" rewrites the line the file already holds for $F000.
sed -i.bak 's/Clear 163 bytes of tile map./Clear the 163-byte tile map./' probe.ctl
run "byte-counts, message reworded" accept "$BYTE_COUNTS"
want_not_in "reword: not read as growth" "REFUSED"
want_lines  "reword: the section did not grow" byte-counts 1
OUT="$(cat lint-baseline.txt)"
want_in     "reword: the recorded message followed the wording" "'163-byte'"

# --- clear the finding, and the regeneration passes ---------------------------

# The introduced directive gone, and the inherited finding fixed by labeling the
# bytes it left anonymous.
sed 's/^B \$F009,2$/@ $F009 label=player_pos\nB $F009,2/' base.ctl > probe.ctl
run "identity finding cleared" accept "$IDENTITY"
want_in    "cleared: names the line it drops" "- identity UNDESCRIBED \$F009"
want_lines "cleared: identity owns nothing now" identity 0
want_lines "cleared: byte-counts is untouched" byte-counts 1

# --- a clean check is adopted, and a clean check cannot grow -------------------

# identity now owns no line at all. That is the state the header exists for:
# owning nothing means "never ran here" and "ran and came back clean" equally, so
# while adoption was inferred from the lines, --adopt walked a finding straight
# into a clean check's section - the forbidden sequence, one flag deeper. The
# declaration says which of the two it is, and identity is declared.
sed 's/^B \$F009,2$/@ $F009 label=player_pos\nB $F009,1\nB $F00A,1/' base.ctl > probe.ctl
run "new finding on a clean check, with --adopt" refuse "$IDENTITY" --adopt
want_in "clean check: names the added key" "+ identity UNDESCRIBED \$F00A"
want_in "clean check: refuses on the declaration, not on the line count" \
        "# adopted: identity"
want_unchanged "clean check with --adopt"

# --- a kind the check gained later is adopted once, by name -------------------

# A check that grows a new finding kind reports debt that predates the kind, on a
# project whose .ctl predates it too - but under a check name already declared,
# so --adopt is closed to it. --adopt-kind is the one route, it names the kind,
# and the line it writes is what a reviewer reads.
cat > probe.ctl <<'EOF'
@ $F000 start
@ $F000 org
@ $F000 label=entry
c $F000 Entry point
  $F000 Clear the tile map.
@ $F009 label=player_pos
b $F009
B $F009,2
i $F00B
EOF
run "a kind the header does not declare, no flag" refuse "$IDENTITY"
want_in "new kind: names the added key" "+ identity UNTITLED_ENTRY \$F009"

run "adopt the new kind by name" accept "$IDENTITY" --adopt-kind UNTITLED_ENTRY
want_in    "adopt-kind: declares the kind, not the check" \
           "# adopted: identity UNTITLED_ENTRY"
want_lines    "adopt-kind: records the kind's finding" identity 1
want_declared "adopt-kind: the header carries the kind" "identity UNTITLED_ENTRY" 1
want_declared "adopt-kind: the check stays declared once" "identity" 1

# A second finding of a kind the header now declares is growth like any other.
cat > probe.ctl <<'EOF'
@ $F000 start
@ $F000 org
@ $F000 label=entry
c $F000 Entry point
  $F000 Clear the tile map.
@ $F009 label=player_pos
b $F009
B $F009,2
c $F00B Second routine
@ $F00C label=flag
b $F00C
B $F00C,1
i $F00D
EOF
run "a second finding of the adopted kind" refuse "$IDENTITY" --adopt-kind UNTITLED_ENTRY
want_in "adopted kind: refused, it only shrinks from here" \
        "identity UNTITLED_ENTRY\` is declared in the header already"
want_unchanged "second finding of the adopted kind"

[ $fail -eq 0 ] || { echo "baseline-monotonic: FAILED"; exit 1; }
echo "baseline-monotonic: OK"
