#!/usr/bin/env bash
# Fixture for how tools/disassembly.mk wires the checks to a project's files.
#
# A check is only as good as the arguments the gate hands it, and a wrong
# argument fails silently: the check runs, reads nothing, and passes. So this
# expands the gate's own command lines in a throwaway project and prints them.
#
# Expected:
#
#   CHECK_terms names the registry at src/glossary.ref. Its first file is the
#   .skool under build/, and the script's default looks beside its first file,
#   where no glossary.ref lives.
#
#   OTHER_CTL is src/intro.ctl and src/tune.ctl, the .ctl files of the
#   [OtherCode] listings in the refs the site reads: src/game.ref declares
#   `intro` with no Source=, so its skool is SkoolKit's default intro.skool, and
#   src/tune.ref, which game.ref names in RefFiles=, declares `tune`. It is not
#   src/loader.ctl, whose listing is in src/unused.ref, a ref the site does not
#   read. Each check over each one runs as a check of its own, so LINT_TOTAL
#   counts them, and each one that holds a baseline reads it under its own
#   `--baseline-scope`.
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# GNU make 4 runs the framework; macOS ships 3.81 as `make`.
mk=$(command -v gmake || command -v make)

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work" || exit 2

# The preflight wants every tool of the default build on PATH. Nothing here runs
# one, so stand-ins answer for them.
mkdir -p stub src
for t in tap2sna.py sna2skool.py skool2asm.py skool2html.py pasmo bin2tap.py; do
    printf '#!/bin/sh\nexit 0\n' > "stub/$t"
    chmod +x "stub/$t"
done

cat > Makefile <<'MK'
GAME = game
ORG = 0x8000
SIZE = 256
PC = 0x8000
SP = 0xFF00
include $(SKILL)/tools/disassembly.mk
show-%:
	@echo '$*: $($*)'
show-other:
	@$(foreach o,$(OTHER_CTL),$(foreach c,$(OTHER_CTL_CHECKS),\
	    echo '$(c)@$(notdir $(o)): $(call OTHER_$(c),$(o))';))
MK
touch src/game.ctl src/glossary.ref src/intro.ctl src/tune.ctl src/loader.ctl
printf '[Config]\nRefFiles=tune.ref\n\n[OtherCode:intro]\n\n[Page:Notes]\nSource=x.skool\n' > src/game.ref
printf '[OtherCode:tune]\nSource=tune.skool\n' > src/tune.ref
printf '[OtherCode:loader]\nSource=loader.skool\n' > src/unused.ref

show() {
    PATH="$work/stub:$PATH" "$mk" --no-print-directory -s "SKILL=$SKILL" "$1" \
        | sed "s|$SKILL/||g"
}

show show-CHECK_terms
show show-OTHER_CTL
show show-LINT_TOTAL
show show-other
