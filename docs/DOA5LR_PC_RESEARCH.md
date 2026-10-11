# Dead or Alive 5 Last Round — original Windows PC research

This edition is unregistered. Two privately retained public native saves pass
the complete encrypted-block checksums and unchanged cipher roundtrips. No
PC-specific gameplay or settings field has qualified for editing. The original
PS3 and Vita Plus layouts do not establish Last Round PC fields.

## Sources and native envelope

[SteffenL/doa5lr-gamesave-tools](https://github.com/SteffenL/doa5lr-gamesave-tools/tree/139f8106076c5c4dc05fe136cd847067138392c2)
contains original-PC protected-block readers and a writer in `Core/Doa5lr.cpp`.
`Core/Doa5lr.h` identifies a private Steam account value in the first decoded
payload, while the remaining payloads are opaque word arrays. Its end-user
instructions describe a save resigner, not a costume or settings editor.
No explicit project licence was found in that snapshot; no implementation code,
assets or catalogue are imported into this project.

[Bucanero's DOA5 decrypter](https://github.com/bucanero/ps3-save-decrypters/tree/master/doa5-decrypter)
separately documents the same block arithmetic for console editions. Its PS3,
Vita and large PS4 samples are edition-specific, not PC field definitions.

[Mahmoud083/DeadORAlive-Saves](https://github.com/Mahmoud083/DeadORAlive-Saves/tree/6a2cbebc6666d13cc0fe27bd38f601059e03badb)
supplies a current and an older PC save. Both are 130,928 bytes and contain these
three complete little-endian blocks:

| Block | Absolute start | Magic | Header size word | Source-defined total size |
| --- | ---: | ---: | ---: | ---: |
| First | `0x00000` | 1 | `0x5B58` | `0x5B58` |
| Second | `0x05B58` | 0 | `0xDB20` | `0xDB20` |
| Third | `0x13678` | 0 | 0 | `0xC8F4` |

Each 16-byte header contains magic, size word, checksum and seed as four
little-endian words. The checksum is the sum of every encrypted payload byte,
modulo 2^32. Each payload word is XORed with the current seed; the next seed is
`((seed << 4) + (seed >> 4)) & 0xffffffff`. Independent arithmetic validated all
three checksums on both files and reproduced all encrypted payloads exactly.
Original seeds, account bytes, unknown words and headers were preserved.

The third block's size word is zero. Its public reader explicitly consumes
`0x3239` payload words / `0xC8F4` total bytes, ending at `0x1FF6C`. Four zero
native trailer bytes remain outside that block in both acquired files and must
be preserved separately. A checksum computed through EOF happens to match
because the trailer is zero; this does **not** prove an extra encrypted word or
a new revision. The public resigner rewrites only the first block in place,
preserving the remaining file. A future complete-save writer must preserve this
trailer and prove every applicable native integrity rule before enabling fields.

Native saves, original owner context and external source copies stay outside
the checkout and public assets. No downloaded game or editor binary was run.
No genuine gameplay edits, GUI workflow or edited game-load test was performed.

## Coverage and exact next inputs

| System | Evidence and remaining blocker |
| --- | --- |
| Native block integrity and cipher | All six observed block sums and complete unchanged cipher roundtrips pass. Need exact revision/title gates before a public adapter. |
| Costume ownership and selected appearance | Need a Last Round PC-specific serialized record definition or a labelled earned-costume and already-owned costume-selection pair, with unchanged re-save controls. Original PS3 costume addresses are not reused. Separate earned base costumes, DLC entitlement and active equipment references. |
| Fighters and unlock progression | Need exact PC records and their dependencies. A completed save or a blanket unlock write does not distinguish earned progression, installed content and entitlement. |
| Audio, controls and other settings | Need a PC save-backed field source or one-setting before/after pair identifying the displayed setting and native values. Configuration files and runtime-memory addresses do not prove an encrypted save offset. |
| Titles, training, achievements and records | Need independent mappings and prerequisites. Wins, rankings, history, completion and reward claims remain separate from customization. |
| Owner context and safe saving | Retain original private account bytes without converting ownership. A future adapter must bind complete source bytes/context, validate encoded output and test source races, Undo, Review Changes, backups and restore. |

The essential missing input is **a matching PC save serializer/field source**, or
controlled native before/after captures for one of the actions above. Additional
unlabelled completed saves alone do not resolve the field mapping. The existing
samples already establish that encryption alone is not the remaining obstacle.
