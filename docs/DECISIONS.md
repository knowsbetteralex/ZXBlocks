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
interpreter. Start with keyboard input and an independent reference model;
design non-blocking timers and procedures as the next focused slice.
