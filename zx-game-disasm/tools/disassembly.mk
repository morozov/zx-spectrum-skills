# Shared SkoolKit-disassembly build framework for the zx-game-disasm skill.
#
# A game Makefile sets GAME, ORG, SIZE, PC, SP (and optionally RELOC_FLOOR), then
# `include`s this file. All build rules live here, so a project's Makefile stays a
# few lines and a fix to the framework reaches every game without re-copying. This
# mirrors how SkoolKit's own disassemblies include `$(SKOOLKIT_HOME)/tools/
# disassembly.mk`. Do NOT copy this into a project — reference it in place.
#
# Targets:
#   make          The gate: round-trip cmp + .ctl linters + HTML build (validates
#                 the .ref catalogs). Build the asm, snapshot, and site.
#   make gate     The same gate, logged, ending in one PASS/FAIL verdict line
#   make coverage The "is it done?" gauge (documentation/naming/relocatability)
#   make verify-frag FRAG=…  Round-trip one Worker fragment in isolation
#   make tap      A loadable .tap of the fixed build — the disassembly as a
#                 playable rebuild, not only a byte-check
#   make clean    Remove all generated files
#
# The default `make` builds everything — the disassembly, the verified round-trip,
# and the HTML site — so one command produces the whole deliverable. HTML degrades
# gracefully: with no `.ref` files yet it is a basic site from the skool alone, and
# it gains the catalog/reference pages as the `.ref` files appear. `make` is
# incremental — run it while iterating; avoid `make clean && make`.

# Locate the skill's scripts relative to this file: .../tools/disassembly.mk lives
# beside .../scripts, so the project never has to point at them.
SCRIPTS := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../scripts)

# Game floor: a raw operand at/above this address is the game's own and must be a
# label (below is ROM/screen, fixed). Per-game; override in the game Makefile.
RELOC_FLOOR ?= 0x5B00

# Source files (hand-edited)
CTL = $(GAME).ctl
T2S = $(GAME).t2s
INI = skoolkit.ini
REF = $(GAME).ref

# Generated files
SKOOL         = $(GAME).skool
Z80_PRISTINE  = $(GAME).pristine.z80
Z80_FIXED     = $(GAME).fixed.z80
BIN_PRISTINE  = $(GAME).pristine.bin
BIN_NON_FIXED = $(GAME).non-fixed.bin
BIN_FIXED     = $(GAME).fixed.bin
ASM_NON_FIXED = $(GAME).non-fixed.asm
ASM_FIXED     = $(GAME).asm

.PHONY: all gate tap clean verify-frag test lint lint-address-order lint-instruction-order lint-lengths lint-label-length lint-comments coverage html

# `make` (the default) is the one verification gate: it drives the round-trip cmp,
# the .ctl linters, and the HTML build (the only step that validates the .ref
# catalogs). It is not slow, so there is no separate "verify" — use `make`.
all: $(ASM_FIXED) $(Z80_FIXED) test lint html

# The same gate, with a result that cannot be misread. Under `-j` the HTML branch
# can print `touch html/.stamp` while the asm branch is failing, so the tail of a
# parallel build shows a success line for a red build; and a piped `make | tail`
# hands the reader the pipeline's status, not make's. This runs the gate into a
# log and ends with one verdict line, then exits with make's own status. Judge a
# build by that status — never by what the output looks like.
GATE_LOG = build/make.log

gate:
	@mkdir -p $(dir $(GATE_LOG))
	@$(MAKE) --no-print-directory all > $(GATE_LOG) 2>&1; s=$$?; \
	  if [ $$s -eq 0 ]; then \
	    echo "GATE PASS — round-trip, linters and HTML green (log: $(GATE_LOG))"; \
	  else \
	    tail -40 $(GATE_LOG); \
	    echo; echo "GATE FAIL (make exit $$s) — full log: $(GATE_LOG)"; \
	  fi; exit $$s

# Round-trip a parallel Worker's range-fragment in isolation (splice into a
# throwaway .ctl, reassemble, lint — all under a temp dir, touching no shared file)
# so a Worker can self-check before reporting; the Manager still proves the
# integrated result with the full `make`. The multi-step logic lives in the script
# so this recipe stays one line. Usage: make verify-frag FRAG=build/frags/my.ctl
verify-frag: $(Z80_PRISTINE) $(BIN_PRISTINE)
	@$(SCRIPTS)/verify_fragment.sh "$(CTL)" "$(FRAG)" "$(Z80_PRISTINE)" "$(BIN_PRISTINE)" "$(SCRIPTS)"

# Download and convert the original tape to the pristine snapshot.
$(Z80_PRISTINE): $(T2S)
	tap2sna.py @$(T2S) --reg pc=$(PC) --reg sp=$(SP) $(Z80_PRISTINE)

# Extract the program bytes from the pristine snapshot (the ground truth).
$(BIN_PRISTINE): $(Z80_PRISTINE)
	$(SCRIPTS)/extract_bytes.py $(Z80_PRISTINE) $(ORG) $(SIZE) $@

# Disassemble the snapshot into skool, applying the control file.
$(SKOOL): $(Z80_PRISTINE) $(CTL)
	sna2skool.py --hex $(Z80_PRISTINE) --ctl $(CTL) > $@

# The round-trip: reassembled non-fixed bytes must equal the pristine bytes.
test: $(BIN_PRISTINE) $(BIN_NON_FIXED)
	cmp $(BIN_PRISTINE) $(BIN_NON_FIXED)

lint: lint-address-order lint-instruction-order lint-lengths lint-label-length

# Label naming is a gauge metric, not a build gate. Early on the map is mostly
# auto-labels and you cannot name a block before you have disassembled it, so a hard
# per-commit gate would block the breadth phase. `make coverage` reports label-naming
# progress (% named, auto-labels remaining); the goal is 100% before "done", not
# before the first commit. See `scripts/coverage_report.py`.

lint-address-order: $(CTL)
	$(SCRIPTS)/validate_ctl_address_order.py $(CTL)

lint-instruction-order: $(CTL)
	$(SCRIPTS)/validate_ctl_instruction_order.py $(CTL)

lint-lengths: $(CTL)
	$(SCRIPTS)/validate_ctl_lengths.py $(CTL)

# Labels never wrap in the HTML listing, so an over-long label opens a wide
# gutter on its page. Cap length at the source (24 chars); a violation is fixed
# by renaming the label, never by clipping the column.
lint-label-length: $(CTL)
	$(SCRIPTS)/validate_ctl_label_length.py $(CTL)

# Advisory data-block schema check: every b/s block must tile — its sub-directives
# cover every byte exactly once. Code modeled as an undifferentiated byte span
# reads as clean under every other check while relocating nothing, and that is the
# defect this catches. Advisory for now, so it is not in `lint`: it flags real but
# pre-existing gaps in a mature .ctl, and a gate that lands red on day one gets
# switched off. Promote it into `lint` once a project
# clears it.
#
# The image is passed, not optional: the ZEROFILL and POINTER checks need to read
# the bytes, and a linter that silently skips half its checks is worse than one
# that is not wired up at all.
lint-data-structure: $(CTL) $(BIN_PRISTINE)
	$(SCRIPTS)/validate_ctl_data_structure.py $(CTL) --bin $(BIN_PRISTINE) \
	    --org $(ORG) --reloc-floor $(RELOC_FLOOR)

# Advisory comment-quality pre-filter (RET / RESTATE / PLACEHOLDER / SELFLINK /
# DIARY / REFPOINTER / STAMP). Advisory, so it is not in the default `make` gate
# — run it on demand. The Challenger consults it; a flag is a prompt to review,
# not necessarily a build failure (a STAMP can be a legitimate formula over a
# genuinely templated reality). The checks that matter most — does a comment add
# what the code can't show, does a multi-line comment span the right
# instructions — are the Challenger's, not scriptable.
#
# The catalogs and the spec pages are passed too: they reach the same reader as
# the .skool, so the DIARY sweep covers them. An unswept .ref is where a claim
# sourced from a run survives.
PROSE = $(wildcard *.ref) $(wildcard spec/*.md)

lint-comments: $(SKOOL)
	$(SCRIPTS)/lint_comments.py $(SKOOL) $(PROSE)

# Advisory documentation-coverage report — the "is it done?" gauge. Shows the
# fraction of routines with an explained body, inline-graphics/naming/relocatability
# signals, and audio/table/placeholder gaps. A green build is breadth; maturity
# requires this to clear the floor.
coverage: $(SKOOL)
	$(SCRIPTS)/coverage_report.py $(SKOOL) --reloc-floor $(RELOC_FLOOR)   # auto-discovers the .ctl and every *.ref

# Non-fixed source: must already match the original (no @ofix applied).
$(ASM_NON_FIXED): $(SKOOL)
	@skool2asm.py --create-labels $(SKOOL) > $@.tmp 2> $@.stderr; \
	if grep -q WARNING $@.stderr; then cat $@.stderr >&2; rm -f $@.tmp $@.stderr; exit 1; \
	else rm -f $@.stderr; mv $@.tmp $@; fi

$(BIN_NON_FIXED): $(ASM_NON_FIXED)
	pasmo --bin $(ASM_NON_FIXED) $@

# Fixed source: applies @isub/@ofix directives. The fixed asm renders relocatably
# by default — `-s` puts every in-image operand through its @ssub/@equ form and
# strictly gates that no raw in-image reference remains, so `coverage` reports
# RELOCATABLE = 0. This is the standard, not a per-project opt-in. `-s` fails on
# any unresolved in-image operand, so a project still in the breadth/labeling
# sweep opts OUT until the sweep is done by setting `ASM_FIXED_FLAGS =` (empty) in
# its Makefile, then removes that line to restore the standard gate.
ASM_FIXED_FLAGS ?= -s
$(ASM_FIXED): $(SKOOL)
	@skool2asm.py --create-labels -f 1 $(ASM_FIXED_FLAGS) $(SKOOL) > $@.tmp 2> $@.stderr; \
	if grep -q WARNING $@.stderr; then cat $@.stderr >&2; rm -f $@.tmp $@.stderr; exit 1; \
	else rm -f $@.stderr; mv $@.tmp $@; fi

$(BIN_FIXED): $(ASM_FIXED)
	pasmo --bin $< $@

$(Z80_FIXED): $(BIN_FIXED)
	bin2sna.py --border 0 --org $(ORG) --start $(PC) --stack $(SP) $< $@

# The documented source as a runnable deliverable: wrap the fixed program image
# into a tape anyone can load. Kept out of `all` — it is a shipping artifact,
# not a gate.
TAP_FIXED = $(GAME).fixed.tap

tap: $(TAP_FIXED)

$(TAP_FIXED): $(BIN_FIXED)
	bin2tap.py --org $(ORG) --start $(PC) --stack $(SP) $< $@

# Every site ships the skill's default theme: dark responsive layout,
# JetBrains Mono listing, Z80 syntax highlighting, comment-group hover, and a
# card-grid index (assets/theme.{ref,css,js}). The theme ref is passed before
# the project's refs, so a project overrides it by restating a parameter and
# layers its identity by appending its own stylesheet
# (StyleSheet=skoolkit.css;theme.css;$(GAME).css). `-a` renders operands as
# label names — `CALL draw_sprite`, never `CALL $F0A2`.
THEME := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../assets)

html: html/.stamp

html/.stamp: $(SKOOL) $(wildcard *.ref) $(THEME)/theme.ref $(THEME)/theme.css $(THEME)/theme.js
	skool2html.py -d html -H -a --rebuild-images --rebuild-audio -S $(THEME) $(SKOOL) $(THEME)/theme.ref $(REF)
	touch $@

clean:
	rm -rf html *.asm *.bin *.skool *.z80
