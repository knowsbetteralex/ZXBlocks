# Z80 runtime (planned)

Bootstrap compiler emits one tiny built-in border procedure; a reusable graphics/game runtime is not implemented yet.

The v2 keyboard slice also conditionally emits `ZXB_RT_KEY_POLL` and cached
row bytes. Its complete register/stack/RAM/hardware/cost contract is in
[docs/KEYBOARD_RUNTIME.md](../docs/KEYBOARD_RUNTIME.md). There is still no
reusable renderer or object runtime.

Every future runtime procedure must state:
- Purpose, inputs and outputs
- Registers and flags modified
- Stack depth and RAM ownership
- Screen/interrupt constraints and hardware profile
- Best/worst T-states and measurement method
- Callers, failure modes and regression tests

Compile only required runtime routines into game output. Selectively adapt universal SpaceCan procedures after reviewing code, contracts and license.
