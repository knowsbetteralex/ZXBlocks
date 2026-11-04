; Debug packaging for the border_cycle example; run from the repository root.
; DEVICE initializes 48K RAM/system variables as after BASIC CLEAR 32767.
; SAVESNA supplies the entry PC and a BASIC-compatible stack below the code;
; the restored SP is 0x7FFC. The generated program uses the 48K ROM's IM 1 ISR.
; No instructions are added to the program and no ROM is included in the SNA.
        DEVICE ZXSPECTRUM48, 32767
        SLDOPT COMMENT WPMEM, LOGPOINT, ASSERTION
        INCLUDE "../build/examples/border_cycle/border_cycle.asm"
        SAVESNA "build/examples/border_cycle/border_cycle.sna", ZXB_START
