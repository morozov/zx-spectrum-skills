#!/usr/bin/env bash
# Assert what each .ctl check reports on its fixture, rather than printing it.
#
# A fixture that is only run tells you a check still produces findings. It does
# not tell you the check still produces *these* findings, and that is the gap a
# rule falls through: a check that loses a finding kind still prints findings,
# and a lower count reads as progress while the build gates on a property the
# check no longer tests.
#
# So the expectation is a file, and the assertion is a diff of the whole output.
# Whole output, not a count and not the finding kinds alone: a kind that stops
# firing, a kind that starts, a finding that moves address, and a message that
# changes are all things a reviewer should see in a diff and approve, and none of
# them should be able to arrive silently. Fixture files do not churn, so their
# line numbers are stable and the diff stays quiet until behavior moves.
#
# `--record` regenerates every expectation. That is the dangerous direction — it
# is how a removed rule gets blessed — so a recording is only worth what the
# review of its diff is worth. Two things make that review possible: the diff is
# the finding text itself, and `references/build-verify.md` states, in prose
# written before the expectations existed, what several of these fixtures must
# report. Check a recording against that prose, not against the fact that it ran.
#
# Usage:  fixtures/check-findings.sh [--record]

set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

record=0
[ "${1-}" = '--record' ] && record=1

failed=0
ran=0

# One case per line: the expectation's name, then the command. Every fixture whose
# check and arguments are determinable belongs here.
run() {
    local name=$1
    shift
    local actual
    actual=$("$@" 2>&1 | sed "s|$PWD/||g")
    local expected="fixtures/$name.expected"

    ran=$((ran + 1))
    if [ "$record" = 1 ]; then
        printf '%s\n' "$actual" > "$expected"
        echo "recorded  $name"
        return
    fi
    if [ ! -f "$expected" ]; then
        echo "MISSING   $name — no $expected; record it and review the diff"
        failed=$((failed + 1))
        return
    fi
    if ! diff -u "$expected" <(printf '%s\n' "$actual") > /tmp/check-findings.$$; then
        echo "FAIL      $name"
        sed 's/^/    /' /tmp/check-findings.$$
        failed=$((failed + 1))
    else
        echo "ok        $name"
    fi
    rm -f /tmp/check-findings.$$
}

run instruction-order-late-directive \
    scripts/validate_ctl_instruction_order.py fixtures/comment-line-order.ctl
run instruction-order-decimal \
    scripts/validate_ctl_instruction_order.py fixtures/decimal-addresses.ctl
run array-elements-unindexed \
    scripts/validate_ctl_array_elements.py fixtures/wide-comment-array.ctl
run publication-fragmented \
    scripts/validate_ctl_publication.py fixtures/fragmented-structure.ctl \
    --org 0x4000 --size 6912 --skool fixtures/no-stores.skool
run publication-outside-image \
    scripts/validate_ctl_publication.py fixtures/outside-image.ctl \
    --org 0x4000 --size 256 --skool fixtures/no-stores.skool
run publication-entry-type \
    scripts/validate_ctl_publication.py fixtures/entry-type.ctl \
    --org 0x4000 --size 512 --skool fixtures/entry-type.skool
run publication-contradicted \
    scripts/validate_ctl_publication.py fixtures/contradicted-claim.ctl \
    --org 0x4000 --size 256 --skool fixtures/contradicted-claim.skool
run label-namespace \
    scripts/validate_ctl_label_namespace.py fixtures/label-namespace.ctl \
    --skool fixtures/label-namespace.skool
run comments-group-span \
    scripts/lint_comments.py fixtures/group-span.skool

# Where one block ends and the next begins. Each case is a boundary that, read
# wrong, deletes a line with no report: a `u` block, a non-`label=` directive
# at the next header's address, a run of directives at a span's start, and the
# pre-flight window, which must agree with the write path on all three.
run block-boundaries \
    fixtures/block-boundaries.py

run registry-terms \
    scripts/validate_glossary_terms.py fixtures/registry-prose.ref \
    --registry fixtures/registry.ref

# The prose extractor feeds Vale, so a silent regression in it shows up as a
# check that stops reporting rather than as an error. Both halves are asserted:
# the Markdown it emits, and the line map that puts a finding back on a real
# source line.
run prose-extract \
    scripts/extract_prose.py --out - --map - fixtures/prose-extract.skool
run prose-extract-map \
    scripts/extract_prose.py --out /dev/null --map - --print-map \
    fixtures/prose-extract.skool

if [ "$record" = 1 ]; then
    echo "check-findings: recorded $ran expectation(s) — review the diff before committing"
    exit 0
fi
if [ "$failed" -gt 0 ]; then
    echo "check-findings: FAIL, $failed of $ran fixture(s) — a check no longer reports" \
         "what its fixture says it must. Fix the check, or re-record and justify the diff."
    exit 1
fi
echo "check-findings: $ran fixture(s), every check reports what its fixture says it must."
