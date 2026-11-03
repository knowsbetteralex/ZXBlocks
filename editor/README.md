# Visual editor (M1, planned)

The bootstrap repository does not yet contain a functioning Scratch/Blockly UI. We plan a web editor based on Google Blockly, with a toolbox corresponding exactly to the supported zxblocks/v1 IR.

The editor must not generate Z80 assembly directly. It should support import/export JSON, variable editing, and independent workspace layout persistence. Sprite/animation timelines and source-linked compiler diagnostics are later features.

First task: pin a Blockly version, document license, create an editor prototype and round-trip tests for the border-cycle example.
