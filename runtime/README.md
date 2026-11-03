# Z80 runtime (planned)

Bootstrap compiler emits one tiny built-in border procedure; a reusable graphics/game runtime is not implemented yet.

Every future runtime procedure must state:
- Purpose, inputs and outputs
- Registers and flags modified
- Stack depth and RAM ownership
- Screen/interrupt constraints and hardware profile
- Best/worst T-states and measurement method
- Callers, failure modes and regression tests

Compile only required runtime routines into game output. Selectively adapt universal SpaceCan procedures after reviewing code, contracts and license.
