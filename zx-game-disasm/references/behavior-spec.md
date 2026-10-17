# The behavior specification — the capstone artifact

Commentary. The rules are in `rules.md`. Where this file differs, `rules.md` holds.

The annotated `.ctl` documents the game routine by routine. The behavior specification is the synthesis: a subsystem-by-subsystem description of *how the game behaves*, lifted out of the code into language a reader can act on without reading Z80 at all. It is the capstone deliverable of stage 3, and it is what serves both documentation goals:

- **A reader** learns how the game behaves without reading the Z80.
- **An ML-agent trainer** reads the Markov decision process out of it — state, actions, dynamics, reward.

The spec is a set of Markdown files (one per subsystem, plus an index). It can live in the disassembly repo or in a sibling rewrite repo, but it is *derived from* the `.ctl` and references the disassembly by label name, so the two stay anchored to each other.

## Table of contents

- [What separates a spec from comments](#what-separates-a-spec-from-comments)
- [Organize by subsystem](#organize-by-subsystem)
- [The standard: concrete numbers, traced to code](#the-standard-concrete-numbers-traced-to-code)
- [The MDP lens for agent training](#the-mdp-lens-for-agent-training)
- [Control questions to answer](#control-questions-to-answer)
- [Keeping the spec honest](#keeping-the-spec-honest)
- [The completeness tests — past a green build](#the-completeness-tests--past-a-green-build)

## What separates a spec from comments

A line comment explains one instruction in place. The spec answers a question a reader brings — "how does fuel work?", "what does pressing left do?", "how many points is a saucer?" — by gathering facts that are scattered across many routines into one coherent account. It rises above the code's structure to the game's structure.

Concretely, a spec section:

- States behavior, not implementation: "the player moves 2 pixels per frame while a direction is held", not "`move_player_left` does `LD A,(player_x) / SUB 2`".
- Commits to numbers the code commits to (speeds, periods, thresholds, point values), with units.
- Cross-references the routines and variables that implement it, by label, so a reader can drop from the spec into the disassembly.
- Notes quirks and dead code where they affect behavior — a branch that looks live but never runs is a fact the reader needs.

## Organize by subsystem

Slice the game into subsystems and give each its own section. A proven layout — adapt the set to the game at hand:

| Section | Covers |
| --- | --- |
| Architecture | the frame loop, the module map, how subsystems connect |
| Rendering | how things are drawn (mostly skippable for an agent) |
| Game states & flow | attract, play, death, level transition, game over |
| Terrain / level | how a level's layout is generated or stored |
| Player | the avatar: movement, speed, coordinate system |
| Input | controls and the action each maps to |
| Enemies & objects | each object type, its behavior and stats |
| Projectiles | what the player and enemies fire, and how it moves |
| Collision | what overlaps count, and what each does |
| Resource economy | fuel/energy/ammo: consumption, replenishment, limits |
| Scoring | every point award, bonus thresholds, high scores |
| Multiplayer | how state is saved and switched between players |
| Effects | explosions, animations |
| Sound | each effect and its trigger |
| UI / HUD | the status bar, gauges, score display |
| Data & assets | sprite/level/table data the other sections consume |

Add an index that lists the sections and the cross-references between them, and names the disassembly as the source of truth.

## The standard: concrete numbers, traced to code

The difference between a spec that can drive a rewrite or a training run and one that cannot is concreteness. Pull the actual constants out of the code.

The texture to aim for, from an invented platform game's spec:

- *Player:* "A jump rises 24 pixels over 12 frames and falls at 2 pixels per frame. Walking moves 1 pixel per frame. There is no control in the air."
- *Energy:* "Energy drops by 1 every 25 frames and by 8 on contact with an enemy. It starts at 100. At 0 the player loses a life."
- *Scoring:* a table — Key 50, Gem 100, Door opened 250 — plus "an extra life at 10,000 points."

Every one of those is a fact an agent's reward function needs, and none is visible from a single instruction. Each traces back to a labeled routine or variable in the `.ctl`.

## The MDP lens for agent training

For the agent-training goal, make sure the spec pins down the four parts of the decision process explicitly. They are mostly already covered by the subsystem sections — this is a checklist that the MDP-relevant facts are stated, not buried.

- **State** — what determines what happens next. Most of it is the game's RAM variables, marked as a `g` (game-status buffer) block in the `.ctl`. Record each variable's **address** (a live agent reads state straight from these, so the disassembly doubles as the observation memory map), meaning, units, range, and special values. Object/enemy tables: document the per-slot record layout, slot count, and empty/end sentinels.
- **Actions** — the controls and the exact state change each causes, in concrete units, including constraints (mutually exclusive, ignored in some modes). This is the Input section.
- **Dynamics** — the per-frame transition: what runs each frame and in what order; each object's motion rule in pixels/frame and trajectory; spawn cadence; collision geometry and outcomes; level progression. The agent's step is one frame (or a fixed skip).
- **Reward** — every scoring event and its value; the survival economy (resource consumption and gain, lives, bonus thresholds); and the episode boundaries (what ends a life, what ends the game, any win condition).

## Control questions to answer

Before calling the spec complete, confirm it answers the concrete questions a policy depends on — the ones easy to leave vague:

- At what speed (pixels/frame) does the player move at each setting?
- What is each projectile's trajectory, frame by frame?
- How often does each periodic event fire (blink, spawn, animation step)?
- How many points does each scoring event award?
- How does the resource economy deplete and replenish, and does the rate depend on speed or actions?
- How is each level's starting state laid out in data?
- What exactly triggers a life loss and a game over?

Any question the spec cannot answer is a documentation gap to close back in the `.ctl`, not a detail to omit. These are precisely the facts an agent needs.

## Keeping the spec honest

The spec is persisted documentation, so the no-speculation discipline from `references/comment-style.md` applies in full: every claim traces to a routine or data structure you have read, no frequency hand-waving, no unverified cause. When the spec and the `.ctl` disagree, the `.ctl` (which round-trips to the original bytes) wins — fix the spec. Reference routines and variables by their `.ctl` label names, never by raw address, so renaming a label does not silently strand the spec.

The spec is also a *reader's* document, so the prose discipline applies too: each fact stated once and cross-referenced everywhere else (never the same progression rules in two sections); no status, honesty, or "open questions" sections — an unresolved item is a dig-task, and it is marked where it lives, not collected into a section about the work. And vary the structure: a bold-label prefix stamped on every bullet is generated scaffolding, not organization.

A `(unverified)` on the one field that is not derived is the right way to mark it — pointed at the claim, greppable, and honest about which byte is in doubt while the rest of the record stays flat. It needs no legend explaining the convention; a legend is the spec talking about itself. What it does mean is that the spec is **not finished**: every marker owes an open dig-task, `make coverage` counts them as OPEN and holds the project short of the bar, and the marker comes out when the claim is derived, not when the page needs to look done.

Runtime is not a source here either. A number the spec commits to must come out of the code, not off a run — a hold timer that "auto-releases at 250 (verified live)" belongs in the spec as the compare the code performs, with the emulator nowhere in the sentence. `make lint-comments` sweeps `spec/*.md` for that vocabulary along with the `.ref` catalogs.

## The completeness tests — past a green build

Two tests tell you the spec is actually done, not merely written:

- **The plain-language test.** Can you describe each subsystem in plain prose, without falling back to "it does what the code does"? If a behavior can only be restated as Z80, it is not yet understood — keep digging until it reads as game logic. This is the difference between a transcription and a spec.
- **The reimplementation test.** Could someone reimplement the game from this spec alone — every variable named with its address and invariants; every data format decoded to exact byte layout; every transition rule in concrete units? Nothing can be reimplemented that is not fully decoded, so this is the strictest completeness check there is. The model for the State section is one consolidated context struct gathering every global with its address, purpose, and invariants — written so it doubles as a reimplementation's data structures and a live agent's observation map.
