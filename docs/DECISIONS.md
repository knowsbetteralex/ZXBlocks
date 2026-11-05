# Architecture decisions

## ADR-001 — native Z80 output (2026-11-03)
Compile blocks into standalone Z80 ASM, not Spectrum-side interpreted bytecode. Motivation: predictable runtime costs and no visual-language interpreter in scarce RAM.

## ADR-002 — versioned JSON boundary (2026-11-03)
The editor serializes zxblocks/v1, separate from internal Blockly format. Motivation: GUI, CLI and project files evolve independently. Breaking changes require explicit migration.

## ADR-003 — Python compiler, JavaScript GUI (2026-11-03)
Use stdlib-first Python 3.11+ and a future browser Blockly UI, keeping command-line tools independent. Pin UI dependencies only when introduced.

M1 implementation: Blockly 13.4.0 is bundled by esbuild 0.28.2; the independent
Python CLI still has no third-party runtime dependencies.

## ADR-004 — Spectrum 48K baseline (2026-11-03)
Assume classic 48K, with target profiles planned for Delta-C variants. No 128K or Next-specific operations by default.

## ADR-005 — readable code before micro-optimization (2026-11-03)
Generate deterministic human-readable ASM, record contracts and test behavior before T-state optimization.

## ADR-006 — PR-oriented work (2026-11-03)
GitHub is the source of truth; Codex changes are reviewed as feature branches and PRs. Document decisions rather than relying on transient conversation history.

## ADR-007 — local M1 editor host (2026-11-04)

Use Python's standard-library HTTP server bound to loopback to serve locally
bundled Blockly assets and the compiler endpoint. The editor generates IR,
the Python compiler generates ASM, and editor layout lives in a separate
versioned envelope. This keeps existing CLI/IR/runtime behavior independent of
the GUI and needs no additional Python framework or running Node server.

## ADR-008 — explicit keyboard format extension (2026-11-04)

Add key expressions only in `zxblocks/v2`, keeping v1 output unchanged and
providing an explicit upgrade command. Sample only referenced physical rows
before start and once per frame, then reuse samples in expressions. This gives
consistent per-row state within an update without busy waiting or a block
interpreter. Start with keyboard input and an independent reference model.
Follow-up sequencing is now set by ADR-010 and the roadmap.

## ADR-009 — build and run the current project (2026-11-04)

Share a fixed-name 48K snapshot packager between the local editor and CLI run
command. Accept the current IR directly, without copying downloads into an
example folder or requiring per-project assembler wrappers. Keep immutable
per-request web build directories, fixed artifact names, same-origin requests
and server-selected executables. This reduces manual steps while preserving
the editor/compiler IR boundary and all existing v1/v2 generated instructions.

## ADR-010 — arithmetic before timers and delays (2026-11-04)

At the user's request, prioritize useful u8 expressions before scheduling:
nested addition/subtraction and expression comparisons first, then the remaining
arithmetic, bitwise operations and logical conditions. Complete the expression
stage before periodic events, non-blocking waits and user procedures. Retain
u8 wrap semantics and v1/v2 compatibility; document the new IR version,
migration and edge cases before implementing operators. The editor continues
to select required capabilities automatically. Division-by-zero behavior,
shift rules and condition evaluation details remain specification work;
see [the arithmetic implementation plan](ARITHMETIC_PLAN.md). This decision
changes work priority, not the current supported grammar or runtime ABI.

## ADR-011 — v3 byte-expression foundation (2026-11-05)

Add nested u8 add/sub and six unsigned expression comparisons in `zxblocks/v3`.
Evaluate left before right and wrap each value node modulo 256. Preserve legacy
condition shapes and byte-identical v1/v2 assembly; provide explicit CLI upgrade
and automatic capability selection for authored blocks. Keep editor-container
versions independent. Inline balanced PUSH/POP code saves operands without
scratch RAM or runtime helpers; bound expression depth/nodes and document
register/stack usage in [the v3 specification](BLOCK_IR_V3.md). New arithmetic
operators and compound conditions remain separate complete slices.
