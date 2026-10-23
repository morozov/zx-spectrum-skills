# The site build of a zx-game-disasm project: the snapshot, the program image,
# the skool file and the HTML site.
#
# This directory is the skill's site/. A project carries a copy of it at the
# path its Makefile sets as SITE_DIR, written by `make vendor` and tracked in
# git, so `make html` needs SkoolKit and the project's tools/requirements.txt
# and nothing from the skill. Change the skill's copy and run `make vendor`;
# the gate fails while the two differ.
#
# The project Makefile sets GAME, ORG, SIZE, PC and SP and includes this file
# before the skill's tools/disassembly.mk.

SITE_HOME := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# The build runs its tools from PATH.
TAP2SNA    := tap2sna.py
SNA2SKOOL  := sna2skool.py
SKOOL2HTML := skool2html.py

SRC       ?= src
BUILD     ?= build
# Where a project's make rules write the site files they render from the image.
SITE_RENDERS ?= $(BUILD)/resources

# Source files (hand-edited)
CTL = $(SRC)/$(GAME).ctl
T2S = $(SRC)/$(GAME).t2s
REF = $(SRC)/$(GAME).ref

# Further .ctl files the disassembly is built from, if the project generates any
# (a build script's sprite masks, say). Set it in the game Makefile as a plain
# list of paths. They reach sna2skool as extra `--ctl` arguments and are held to
# the same publication rules as the main one: a page is a page whichever file
# declared it.
CTL_EXTRA ?=

# Generated files
SKOOL    = $(BUILD)/$(GAME).skool
Z80      = $(BUILD)/$(GAME).z80
BIN      = $(BUILD)/$(GAME).bin
HTML_DIR = $(BUILD)/html

.PHONY: html

# A recipe that redirects into its own target has already created that target by
# the time it fails: `sna2skool.py … > $(SKOOL)` that dies mid-write leaves a
# truncated .skool newer than the .ctl, which make then calls current and every
# downstream target agrees with. Delete the target instead, so the next make
# rebuilds it and a failure cannot be laundered into an up-to-date tree. The
# target applies to the whole make run, so every failing target in
# tools/disassembly.mk that must survive is phony, and its `lint-baseline`
# writes $(BASELINE), not $@.
.DELETE_ON_ERROR:

# The first rule, so a build without the skill's framework defaults to the site.
html: $(HTML_DIR)/.stamp

# Load the game from its tape into a snapshot.
$(Z80): $(T2S)
	@mkdir -p $(dir $@)
	$(TAP2SNA) @$(T2S) --reg pc=$(PC) --reg sp=$(SP) $(Z80)

# Extract the program bytes from the snapshot (the ground truth).
$(BIN): $(Z80)
	$(SITE_HOME)/extract_bytes.py $(Z80) $(ORG) $(SIZE) $@

# Disassemble the snapshot into skool, applying the control file.
# sna2skool warns and continues when it cannot place a .ctl line — a hard-wrapped
# directive loses every line after the first this way, and the truncated comment
# then passes every downstream check, because from their point of view the text
# simply is not there. Fail here instead, the way the asm render already does.
$(SKOOL): $(Z80) $(CTL) $(CTL_EXTRA)
	@$(SNA2SKOOL) --hex $(Z80) --ctl $(CTL) $(addprefix --ctl ,$(CTL_EXTRA)) \
	    > $@.tmp 2> $@.stderr; rc=$$?; \
	if grep -q 'Ignoring line' $@.stderr; then rc=1; fi; \
	if [ $$rc -ne 0 ]; then cat $@.stderr >&2; rm -f $@.tmp $@.stderr; exit $$rc; fi; \
	cat $@.stderr; rm -f $@.stderr; mv $@.tmp $@

# Every site ships the skill's default theme: dark responsive layout, the listing
# in the platform's own monospace face, Z80 syntax highlighting, comment-group
# hover, and a card-grid index (theme/theme.{ref,css,js}). The theme names no
# face it does not load — see `references/html-docs.md`. A project layers its
# identity by appending its own stylesheet to the chain its [Game] declares
# (StyleSheet=skoolkit.css;theme.css;$(GAME).css). `-a` renders operands as
# label names — `CALL draw_sprite`, never `CALL $F0A2`.
#
# The theme ref is parsed LAST, after every project ref, and last wins.
# skool2html.py:183-196 globs $(GAME)*.ref and reads [Config] (RefFiles, GameDir)
# only in the skool file's directory, and the skool lives in $(BUILD), so the
# recipe passes what that discovery would have found: $(GAME).ref first, the
# other $(GAME)*.ref, then the files [Config] RefFiles names, in its order, then
# the theme. GameDir is passed with -c, which skool2html applies before it reads
# it (skool2html.py:192): the project's own [Config] GameDir, else $(GAME).
#
# So restating a parameter does NOT override the theme. refparser.py:30-33: a
# plain [Section] REPLACES what earlier refs built, a [Section+] extends it, and
# within a dictionary section a later `Key=` overwrites an earlier one. A key
# theme.ref states in [Game+] or [Paths+] therefore beats the project's value for
# that key, and a plain [Template:*] in theme.ref cannot be reclaimed at all.
# theme.ref carries only what is genuinely the theme's own; a default a project
# should be able to change lives in assets/game.ref.template, which is the
# project's own file and is parsed first. The one layer that composes rather than
# clobbers is `-c` (skool2html.py:197, applied after every ref), which is why
# HTML_JS below appends to the theme's JavaScript instead of replacing it.
THEME := $(SITE_HOME)/theme

# `-a` names the *targets* of calls and jumps, and nothing else: skool2html
# builds its parser with no asm_mode, so @isub/@ssub and the @equ label map —
# everything that spells an address as a constant in the ASM — never reach the
# page. `InitModule` loads the skill's parser wrapper, which parses the skool a
# second time in ASM mode and copies the operand text across, so the listing and
# the .asm read alike. A project that needs an InitModule of its own must import
# this one from it: the last [Config] value wins, and this is passed last.
HTML_SUBS := $(SITE_HOME)/html/operand_subs.py
# Every $-hex value in the site's text is wrapped in span.hex, which the theme sets
# in the monospace face. It runs after skool2html, inside the $(HTML_DIR)/.stamp recipe,
# so no page ships without it and a rebuilt page is never left unwrapped.
HTML_HEX := $(SITE_HOME)/html/hex_mono.py
# Every label and constant name in the site's prose is wrapped in span.sym, so a
# name without a link sets in the same face as a linked one. It runs after the
# hex pass, in the same recipe; it reads the labels off the built pages and the
# constants off the skool file's @equ directives.
HTML_SYM := $(SITE_HOME)/html/sym_mono.py

# [Game] JavaScript is a single key, so a ref file that names theme.js owns the
# whole slot and a project can ship none of its own. Composing it here instead
# leaves the slot open: a project lists its scripts in HTML_JS and they load
# after the theme's.
#
#   HTML_JS = maps.js;search.js
#
# Name each file in [Resources] so skool2html copies it onto the site. A project
# keeps its hand-made site files in resources/, a directory skool2html searches
# by default (skool2html.py SEARCH_DIRS), and its rendered ones in
# $(SITE_RENDERS), which the recipe adds with -S. A [Resources] path is relative
# to either.
HTML_JS ?=
HTML_JAVASCRIPT := theme.js$(if $(HTML_JS),;$(HTML_JS))

HTML_REF_FILES := $(shell sed -n 's/^RefFiles=//p' $(REF) 2>/dev/null | tr ';' ' ')
HTML_GAME_DIR := $(or $(shell sed -n 's/^GameDir=//p' $(REF) 2>/dev/null),$(GAME))
HTML_REFS := $(REF) $(filter-out $(REF),$(sort $(wildcard $(SRC)/$(GAME)*.ref)))
HTML_REFS += $(filter-out $(HTML_REFS),$(addprefix $(SRC)/,$(HTML_REF_FILES)))

$(HTML_DIR)/.stamp: $(SKOOL) $(wildcard $(SRC)/*.ref) $(wildcard resources/*.css resources/*.js) $(THEME)/theme.ref $(THEME)/theme.css $(THEME)/theme.js $(HTML_SUBS) $(HTML_HEX) $(HTML_SYM)
	$(SKOOL2HTML) -d $(HTML_DIR) -H -a -c "Config/InitModule=$(SITE_HOME)/html:operand_subs" -c "Config/GameDir=$(HTML_GAME_DIR)" -c "Game/JavaScript=$(HTML_JAVASCRIPT)" --rebuild-images --rebuild-audio -S $(THEME) -S $(SITE_RENDERS) $(SKOOL) $(HTML_REFS) $(THEME)/theme.ref
	$(HTML_HEX) $(HTML_DIR)
	$(HTML_SYM) $(HTML_DIR) $(SKOOL)
	touch $@
