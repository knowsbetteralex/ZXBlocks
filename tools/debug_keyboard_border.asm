; Snapshot-only packaging for the zxblocks/v2 keyboard example.
; RAM/system variables and restored SP match CLEAR 32767 / SP=0x7FFC.
; Requires the emulator's 48K ROM for IM 1 interrupts; includes no ROM.
        DEVICE ZXSPECTRUM48, 32767
        SLDOPT COMMENT WPMEM, LOGPOINT, ASSERTION
        INCLUDE "../build/keyboard_border.asm"
        SAVESNA "build/keyboard_border.sna", ZXB_START
