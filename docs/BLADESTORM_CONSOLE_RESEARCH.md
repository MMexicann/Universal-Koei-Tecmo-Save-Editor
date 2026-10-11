# Bladestorm: The Hundred Years' War — console writer retry

No Bladestorm editor is registered. Original Xbox 360 and original PS3 remain
separate investigations; Nightmare and PC do not inherit either profile.

The public [MarkH221 Xbox 360 writer](https://github.com/MarkH221/BladestormSaveEditor)
contains complete source for its open, per-slot reads, writes and STFS reimport.
No project licence is declared. Its implementation, UI, catalogs and assets were
not copied; source was read for factual format evidence only and never executed.

The writer extracts the first STFS file, reads 30 slot-preview entries at
`0xE35800` with stride 128, and patches opened slot records at
`0x44 + slot_index * 0x79400`. It writes the 16-byte name at slot-relative `+4`,
money as a big-endian u32 at `+64`, and seventeen unit-type level/SP records.
Levels are u16 at slot-relative `842 + type_index * 84`; SP is u32 six bytes
later. It then replaces the first STFS file and completes external STFS hashing
and signing. No separate native gameplay integrity routine appears in that
complete save method. This is **Xbox 360 writer evidence**, not proof that PS3
lacks internal integrity. Its all-inventory option creates ownership and is not
an independently safe existing-record edit.

The essential Xbox input remains a **genuine original-title extracted first
STFS file**, plus the original complete package for title/region and extraction
qualification. Neither the public writer repository nor either inspected public
Xenia save collection supplies this game. Its multi-slot geometry and foreign
language preview handling require native verification before a writable adapter.
An invented concatenation of PS3 slots is not an Xbox fixture.

Two genuine original European PS3 `BLES00113` exports were acquired from the
[Apollo catalogue](https://bucanero.github.io/apollo-saves/PS3/BLES00113/), with
original metadata and PFD. Each console-encrypted `PLAYDATA` is 496,592 bytes.
Those exports remain private. The
[PS3 patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLES00113.savepatch)
contains money targets at `0x84` and `0xAB8`, sixteen book-SP targets and a broad
inventory patch, but no complete PS3 native-integrity writer. The two money
words must not be treated as interchangeable without proving current/history
semantics; the Xbox single-money writer does not settle the PS3 dependency.

| Mechanic | Qualification needed before support |
| --- | --- |
| Money | Matching Xbox native geometry; PS3 additionally needs complete native integrity and separate meaning/dependency proof for its two targets |
| Seventeen unit-type levels and SP | Native existing-book/unlocked-type identities, unspent SP versus earned EXP, thresholds and upgrade dependencies; writer numeric maxima are not natural caps |
| Weapons, armor and pennons | Existing occupied identities and quantity/equipment dependencies; broad ownership-creation patches are excluded |
| Existing mercenary name | Genuine platform encoding/length and multibyte preservation; source uses a fixed ASCII field |
| Contracts, fame, chapters and completion | Exact native records, costs, rewards and prerequisites; no blanket completion action |
| STFS/PFD import | Remains an external console workflow; title identity, native integrity and source-context checks must each qualify independently |

No game/editor binary was executed, no player file or source asset was
redistributed, and no actual edited game-load/re-save was performed.
