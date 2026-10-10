# Run a set of independent checks and report every one that failed.
#
# Sourced, never executed. The callers that sweep checks: `lint` and `lint-html`
# in tools/disassembly.mk, over the project's own .ctl and its built site, the
# one-check sweeps behind `lint-images` and `lint-html-layout` there, and
# scripts/verify_fragment.sh, over a spliced fragment. Each states its own
# argument lists — the same check takes a different file and a different
# baseline mode in each — but the loop that runs them, reads a count back out,
# and turns the tally into one verdict line is stated here once.
#
# Usage, all in one shell:
#
#     . "$SCRIPTS/lint_sweep.sh"
#     lint_begin
#     lint_run <name> <command> [arg ...]
#     ...
#     lint_report <number of checks swept>
#
# `lint_report` exits 1 when any check failed, so anything the caller wants
# printed on a red sweep must come before it.
#
# POSIX shell only, and it must behave the same whether or not the caller has set
# `-e`, `-u` or `pipefail`: make runs a recipe under /bin/sh with none of them and
# verify_fragment.sh runs under bash with all three.

lint_begin() {
    failed=0
    findings=0
    list=''
}

# Run one check and tally its outcome. Its output is captured rather than
# streamed so the count can be read back out of it: a check reports findings as
# `Found <n> …`, and a baseline line it no longer reports as `<check>: <n>
# baseline entry(ies) …`. Both are things the reader has to act on, and a check
# can fail on the second with none of the first.
#
# An exit status the checks do not define, an uncaught exception, and a failure
# that printed neither count, are each reported as themselves. Printing `0
# findings` for a check whose output nobody could parse would be the same defect
# one level down.
#
# The traceback test is not redundant with the exit-status test: an uncaught
# Python exception exits 1, the same status a check uses to report findings, so
# without it a crashed check is filed as a failure whose count could not be read
# — which sends the reader to "its findings are in the output above" over a
# traceback. It is a `case` and not a `grep -q` so that it cannot misread its own
# pipeline: `grep -q` exits on the first match, and under `pipefail` the writer
# it leaves mid-write turns a found traceback into a nonzero pipeline.
lint_run() {
    name="$1"
    shift
    echo
    echo "--- lint-$name ---"
    out=$("$@" 2>&1) && s=0 || s=$?
    [ -z "$out" ] || printf '%s\n' "$out"
    # `|| true`: the count is whatever the substitution captured, so a pipeline
    # status is not the assignment's to fail on under `-e`/`pipefail`.
    n=$(printf '%s\n' "$out" | sed -n 's/^Found \([0-9][0-9]*\) .*/\1/p' | head -1) || true
    d=$(printf '%s\n' "$out" | sed -n 's/^[^ ]*: \([0-9][0-9]*\) baseline entr.*/\1/p' | head -1) || true
    case "$out" in
        'Traceback (most recent call last):'*|*'
Traceback (most recent call last):'*) crashed=1 ;;
        *) crashed=0 ;;
    esac
    if [ "$s" -eq 0 ]; then
        echo "lint-$name: ok"
    elif [ "$s" -ne 1 ]; then
        failed=$((failed+1)); list="$list lint-$name (could not run),"
        echo "lint-$name: COULD NOT RUN, exit $s. That is not a finding count of zero."
    elif [ "$crashed" -eq 1 ]; then
        failed=$((failed+1)); list="$list lint-$name (crashed),"
        echo "lint-$name: CRASHED — its output is a traceback, not findings. That is not a finding count of zero."
    elif [ -z "$n$d" ]; then
        failed=$((failed+1)); list="$list lint-$name (count unread),"
        echo "lint-$name: FAIL, and its output carries no finding count — read it above."
    else
        c=$(( ${n:-0} + ${d:-0} ))
        failed=$((failed+1)); findings=$((findings+c))
        list="$list lint-$name $c,"
        echo "lint-$name: FAIL, $c finding(s)."
    fi
}

# The one line a verdict is built from. The gate's verdict is CHECKS PASS or
# CHECKS FAIL: it covers the checks swept here and nothing a review decides, and
# the REVIEW clause under it reports that separately. Its shape is load-bearing: `gate` reads
# the failing count from field 3, the number of checks the sweep accounted for
# from field 5, the finding count from field 8, and the per-check split from
# everything after the second colon. A sweep that reports nothing failing still
# states its total, so the verdict can say how many checks stood behind a green
# one.
#
# The argument is what this sweep ran, not what the caller is held to, and the
# two differ whenever a sweep covers less than the whole set. Saying so is the
# caller's: `gate` compares this number against $(LINT_TOTAL), and
# verify_fragment.sh names the gating check a fragment cannot reach.
lint_report() {
    echo
    if [ "$failed" -eq 0 ]; then
        echo "LINT PASS: $1 of $1 checks clean."
    else
        echo "LINT FAIL: $failed of $1 checks failed, $findings finding(s):${list%,}."
        exit 1
    fi
}
