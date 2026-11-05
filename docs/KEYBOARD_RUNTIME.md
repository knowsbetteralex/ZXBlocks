# Keyboard runtime contract — compiler v2 extension

This documents generated private symbols, not an API for manual ASM blocks.
v1 output and its runtime entry conventions remain unchanged. The new poll
routine is linked only if at least one `zxblocks/v2` or `zxblocks/v3` key expression is used.

## ZXB_RT_KEY_POLL

- **Inputs:** none. Physical keys are read using the classic 48K ULA ports.
- **Outputs:** active-low bytes in `ZXB_KEY_ROW_XX`, where XX is the selected
  high byte of the port. Only referenced rows are included, in physical order.
- **Clobbers:** A, BC and flags. Preserves DE, HL, IX, IY and interrupt mode.
- **Stack:** leaf routine, 2 bytes for the caller's return address. IM 1 ROM
  interrupt stack usage is additional and is not included in that budget.
- **RAM:** exclusive write ownership of one byte per referenced row (1..8).
  Snapshot bytes start at 255 and are polled before any start-event expression.
- **Hardware:** standard Z80 instructions and Spectrum 48K keyboard/ULA.
  The normal program still uses IM 1, EI and HALT; a working 48K ROM ISR and
  BASIC-compatible stack are required for a real/emulated Spectrum run.
- **Calls:** once before `ZXB_ON_START`, then HALT → KEY_POLL → ON_FRAME.
  There is no renderer and no change to v1 loops without key expressions.

## Cost and extraction

Each row uses `LD BC,nn` (10 base T-states), `IN A,(C)` (12) and `LD (nn),A`
(13). Including CALL (17) and RET (10), the **uncontended instruction estimate**
is `27 + 35 * referenced_rows`: 62 for one row, 307 for eight.
These instruction figures come from the [Zilog Z80 CPU manual](https://www.zilog.com/docs/z80/um0080.pdf)
(LD dd,nn; IN r,(C); LD (nn),A; CALL nn; RET). SkoolKit instruction execution
checks the one/eight-row totals. These are not elapsed Spectrum measurements:
ULA I/O contention, interrupt work and other waits are excluded. No worst-case
frame-time guarantee or Delta-C timing is claimed.

A key expression reads its saved row, complements A, masks one physical key
bit, then uses zero to four RRCA instructions to normalize to 0/1. It does not
read the port again or depend on flags from a previous action. A and flags are
clobbered; BC is only clobbered by the preceding row poll. No per-expression
stack or extra state is allocated.

## Tests and limits

The Python reference model covers press/hold/release, simultaneous inputs,
unsigned wrapping and start-event sampling. Optional machine-code tests use
sjasmplus plus SkoolKit 10.1, with an independent keyboard-port fixture and a
test-owned NOP/EI/RETI interrupt stub. They execute generated code for all 40
keys, cached-row reuse, border output, base instruction costs and stack balance.
No Spectrum ROM file is loaded or committed. Install the optional tool with:

```sh
python -m pip install -r requirements-z80-tests.txt
python -m unittest discover -s tests -p test_z80_keyboard.py -v
```

These tests do not simulate a full ULA, ROM ISR, keyboard ghosting, video output
or memory contention. A new interactive 48K emulator keyboard smoke test and
browser QA are still required and are tracked separately in the roadmap.
