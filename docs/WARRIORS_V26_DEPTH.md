# Warriors editor refinements

These changes deepen three existing profiles: **Musou Orochi Z on PC**, **Warriors
Orochi 3 Ultimate Definitive Edition on PC**, and the separately qualified **US
PS3 Warriors Orochi 3 Ultimate decrypted export**. They do not add conversion
routes, console signing, gameplay acquisition or an in-game validation claim.

## Orochi Z: the other four saved base stats

The Officer base stats group adds **Life, Musou, Defense and Speed**. These are
independent saved base growth values. Existing Base attack controls keep their
stable field IDs and Officer attack group. Team abilities, weapon effects,
battle modifiers, current battle health, EXP and level are separate systems.

Each of the 96 officer IDs has its own initial floor and natural growth ceiling.
The editor exposes a new control only when the opened value lies inside that
ID's qualified range. An unknown, zero or unusually high original stays opaque;
opening a file or using Max never repairs it. Max uses the individual native
ceiling, preserving unrelated progression and the original weapon inventory.
Manual changes do not simulate leveling, spend Stock EXP or grant rewards.

| Saved base value | Officer-relative offset | Independent increment/clamp |
| --- | --- | --- |
| Life | `+4`, u16 little endian | `0x477970`, ceiling word `0x6D4750 + id*10` |
| Musou | `+6`, u16 little endian | `0x4779F0`, ceiling word `0x6D4752 + id*10` |
| Attack, existing control | `+8`, u16 little endian | `0x477A70`, ceiling word `0x6D4754 + id*10` |
| Defense | `+10`, u16 little endian | `0x477AF0`, ceiling word `0x6D4756 + id*10` |
| Speed | `+12`, u16 little endian | `0x477B70`, ceiling word `0x6D4758 + id*10` |

Officer records start at `0xC`, stride `0xDC`. Native reset `0x4752B0` writes the
five initial words from `0x6D4390 + id*10`. The independent scalar setters,
`0x52B060` through `0x52B0A0` getters, growth menu copies and level-up calls
corroborate the individual saved values. These are exact Z executable facts,
not original-Orochi or console offsets. The interpreted bounds live in
`games/orochiz/orochiz_limits.py`; no game binary or extracted game asset is
included.

The existing acknowledged experimental mode can write the exact unsigned
16-bit ceiling, 65,535, to an already qualified new numeric field. It does not
lower the native minimum or make an unusual original eligible. Reopening an
experimental value above its qualified normal range preserves it read only.
Assigning the opened value during the original session still unstages the edit.

The [Z mechanics reference](https://wikiwiki.jp/orochis/無双OROCHI%20Z/基本情報)
and [Z fusion reference](https://wikiwiki.jp/orochis/無双OROCHI%20Z/武器融合)
remain mechanics context; they do not supply PC offsets. Full level transitions,
proficiency rewards, abilities, costumes, alchemy and story writers remain outside
these independent scalar edits. See the earlier
[Orochi research](OROCHI_RESEARCH.md) for container and integrity qualification.

## WO3 Ultimate Definitive PC: deliberate compatibility reset

The Weapon compatibility group offers two choices for an existing qualified
weapon: **Keep opened compatibility** or **Reset compatibility to zero**.
The control is deliberately excluded from Max and experimental range expansion.
It does not change the weapon's identity, grade, reinforcement, attributes,
collection, ownership or equipped reference. The displayed number is the stored
raw compatibility value; it is not a star count or an attack value.

Native `0x14026C8C0` serializes the weapon's four-byte compatibility value after
its 20 bytes of identity, capacity, reinforcement and attributes. Thus its file
offset is `0xC8010 + physicalIndex*0x1C + 20`, u32 little endian. The independent
setter `0x14026C7C0` writes only this value. Native attack getter
`0x14026CC90` reads compatibility, resolves the original descriptor and derives
its contribution through `0x14025B9A0`, then adds descriptor attack and the
separate reinforcement byte. No cached attack is invented or overwritten.

The setter's ceiling depends on external weapon-grade descriptors. Its largest
supported grade ceiling is 179,200, but that is **not** a universal weapon cap.
Without the matching descriptor table, arbitrary increases and bulk Max are not
qualified. Zero is valid across those setter branches and already occurs in the
native source inventories. A positive original no larger than 179,200 can offer
the explicit reset; higher values, unknown/empty weapon IDs and unsupported
capacity layouts remain opaque. After saving and reopening a reset weapon there
is no positive compatibility to reset, so the control disappears.

This edits one existing value; it does not emulate a battle, fusion, crafting
transaction or spending/acquisition event. Earlier reinforcement and existing
attribute controls retain their separate rules. See the
[WO3 mechanics guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2851197510)
and [native format notes](OROCHI_RESEARCH.md) for the game's different upgrade
systems and original qualification.

## WO3 PC: item inventory and clearer equipment choices

The searchable **Item inventory** inspector displays all 64 native item records:
original ownership, stored rank and existing equipped references. Ownership and
rank are separate fields. An unowned item with a positive rank remains unowned;
its bytes are not repaired. Ordinary officer item selectors and the separate
mount lookup ordinals are interpreted separately, so mount ordinal zero is
shown against item ID 28 rather than ordinary item ID zero. Item names are not
guessed from another game's catalogue. The inventory inspector remains read only.

Ordinary-item dropdowns now follow the complete pending officer loadout. An item
already assigned to another active slot is withheld; deliberately unequipping
that slot makes the originally owned item available. The backend still validates
the final batch, including Undo/unstaging, and rejects duplicate equipment.
Pending edits never add ownership, change ranks, activate a locked slot or widen
the original qualified choices. Different officers may share an item, and
repeated Unequipped values are allowed.

## US PS3 Ultimate: verify the created copy and its unchanged context

The existing `wo3u_ps3` profile retains its two independently qualified resource
writers. No PC gameplay offset is promoted to PS3 support by this change.

Backup now verifies the opened gameplay source and original opaque `PARAM.SFO`
both before and after snapshot creation. Save As checks the actual created
file, the original source and the same context after destination read-back.
Restore checks the exact bounded bytes validated for that operation against the
created file and checks that its destination context did not change during the
operation. A late mutation or replacement is reported as failure.

Completed outputs, backups and manifests are retained on a later failure. A
retained file does not establish a successful save or restore; keep it separate
and reopen the original export before retrying at a new destination. Existing
backup formats remain readable. Context checks detect changes during the
operation; they do not authenticate console ownership or retrospectively bind
legacy backups to an account. External PFD decryption, reimport and resigning
remain necessary. See [the exact US PS3 profile](WO3U_PS3.md).

## Validation and limits

Public procedural regressions are in `test_orochiz_base_stats.py`,
`test_wo3u_compatibility.py` and `test_wo3u_ps3_copy_races.py`. They cover native
boundaries, unusual originals, complete pending dependencies, hard choice
validation, acknowledged experimental widths, surgical serialization, Undo,
Review Changes, actual copy read-back, backups/restore, source safety and late
source/context/output mutations. Windows race injections compare created-file
identity so temporary-path aliases cannot silently skip the scenario.

Private independent native qualification compared all **960** initial/ceiling
words for the five Z base stats with the native executable. Two distinct
qualified Z gameplay states supplied 384 and 380 new controls; **1,526 boundary
serializations** preserved every byte outside the selected word and the native
additive checksum. That count includes exact boundary no-ops. Two independently
qualified WO3 PC copies supplied **526 surgical compatibility resets**. Four
native PC GUI/Save As/backup/restore workflows passed. The supplied genuine US
PS3 export also passed unchanged and surgical resource Save As, original-context
preservation and restore with the stricter checks. Private sources and their
account context are excluded from Git and release assets.

These are native-file and application checks. No edited save was loaded and
re-saved in an actual game during this work. Windows release checks are reported
separately from these source-level validations.
