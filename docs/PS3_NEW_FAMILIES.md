# Deception IV, Escha & Logy and Ar tonelico Qoga

These are three new title families, with deliberately separate original PS3
profiles. Open a PFD-decrypted gameplay copy with its complete **original
PARAM.SFO** beside it. Keep copies outside the live game directory. Save As
creates a new file and an automatic paired-context backup. External console
save management remains responsible for decrypting, importing and resigning.

| Game/profile | Native file | Size | Writable field | Encoding/offset |
| --- | --- | ---: | --- | --- |
| Deception IV: Blood Ties, US PSN NPUB31442 | DATA.BIN | 409,600 | Warl | Little-endian u32 at 0x20 |
| Atelier Escha & Logy, EU PSN NPEB01945 | USR-DATA | 409,600 | Cole | Big-endian u32 at 0xBD63 |
| Ar tonelico Qoga, US BLUS30639 | USR-DATA | 1,048,576 | Leaf | Big-endian u32 at 0xCCC8 |

The normal editing ceilings are 999,999 Warl/Cole and 9,999,999 Leaf. These are
published or observed editing values, **not established natural game caps**.
Bulk Max is disabled. The acknowledged experimental mode can author the exact
unsigned 32-bit encoding range. Reopening a higher original value preserves it;
assigning it back removes a staged edit without normalizing other bytes.

Each profile has its own eight-byte observed header, exact size and original
save-directory identity. No region or edition is inferred from another game.
The Escha & Logy EU offset differs from the published US offset; DX and Plus
are excluded. Blood Ties does not imply Nightmare Princess support. Qoga
USR-DATA does not imply SYS-DATA/gallery editing. Headers qualify the observed
profile; they do not establish that every game revision has the same layout.

The inspector separates Deception's three ability-experience words, Escha &
Logy's named stored character/alchemy EXP, and Qoga's stored character EXP and
three dive-point words. These are read-only. Qoga's third character record is
labelled by record number because the public writer's name is ambiguous.
No field grants traps, items, abilities, talk topics, endings, assignments,
calendar time or ownership. Growth, rewards and equipment dependencies need
additional mappings before writes.

## Evidence and validation

Complete public PS3 exports were independently PFD-decrypted outside the
checkout: one Blood Ties chapter-one export, one Escha & Logy clear export and
two independent Qoga exports. They establish the full sizes, profile headers,
original title/slot context, and byte-exact unchanged reconstruction. Public
references may already contain edited values; their wallets do not prove caps.
Own-title Apollo patch definitions independently corroborate the scalar offsets
and byte order. Only numeric format facts are used; external source code,
cheat catalogs, save contents, keys and owner metadata are not redistributed.

Primary references:

- [Blood Ties native catalog](https://gamefaqs.gamespot.com/ps3/731291-deception-iv-blood-ties/saves)
  and [NPUB31442 writer](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31442.savepatch).
- [Escha & Logy native catalog](https://gamefaqs.gamespot.com/ps3/709407-atelier-escha-and-logy-alchemists-of-the-dusk-sky/saves)
  and [NPEB01945 writer](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPEB01945.savepatch).
- [Qoga native catalog](https://gamefaqs.gamespot.com/ps3/976762-ar-tonelico-qoga-knell-of-ar-ciel/saves)
  and [BLUS30639 writer](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30639.savepatch).

The published workflow supplies external PFD integrity. This implementation
claims **no discovered internal checksum** and does not silently repair or
fabricate one. Native copy edits, surgical preservation, actual saved-value
read-back, original-context binding, backup/restore, source-change checks and
Tk workflows are checked separately from console acceptance. **Edited
in-game loading and re-saving have not been validated here.**

Public regression fixtures are generated, with distinctive unknown bytes.
Optional `DECEPTION4_PS3_NATIVE_DIR`, `ESCHA_LOGY_PS3_NATIVE_DIR` and
`QOGA_PS3_NATIVE_DIR` select private directories containing decrypted native
filenames plus original PARAM.SFO. They are never packaged. The bound scalar
contract rejects foreign profiles, mutable/forged snapshots, unsupported
fields, stale metadata and source changes. Extensionless USR-DATA copies use
the same guarded storage, backup and restore path as existing PS3 adapters.
