"""Classic 48K keyboard matrix, bit 0 first, with active-low row samples.

Source: Sinclair ZX Spectrum BASIC Programming manual, chapter 23.
Only physical keys are represented, not BASIC keywords or composed symbols.
"""

KEY_ROWS = (
    (0xFE, ("CAPS_SHIFT", "Z", "X", "C", "V")),
    (0xFD, ("A", "S", "D", "F", "G")),
    (0xFB, ("Q", "W", "E", "R", "T")),
    (0xF7, ("1", "2", "3", "4", "5")),
    (0xEF, ("0", "9", "8", "7", "6")),
    (0xDF, ("P", "O", "I", "U", "Y")),
    (0xBF, ("ENTER", "L", "K", "J", "H")),
    (0x7F, ("SPACE", "SYMBOL_SHIFT", "M", "N", "B")),
)
KEY_MATRIX = {key: (row, bit) for row, keys in KEY_ROWS for bit, key in enumerate(keys)}
