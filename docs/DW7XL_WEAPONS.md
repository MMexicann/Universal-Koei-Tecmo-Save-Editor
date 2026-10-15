# DW7 XL Definitive Edition PC: weapon loadouts and applied seals

The PC editor can select existing equipped weapon variants and replace or remove
already learned seals in occupied slots. These features use the native
**Dynasty Warriors 7: Xtreme Legends Definitive Edition** `save.dat`, revision
`0x11080200`, exactly 470,307 bytes.

**Arbitrary weapon base attack and element editing is not implemented.** The game
loads a variant's attack, element, element level and seal capacity from separate
game parameter data. Those attributes are absent from its saved inventory record.
Selecting a different qualified variant uses that variant's existing attributes;
it does not change the parameters of the original weapon.

This guide covers the PC editor. The separate
[PS3-to-PC conversion preview](DW7XL_CONVERSION.md) and PS3 editor have their own
scope. Old 2012 Windows editions do not qualify the Definitive Edition format.
Edited weapon changes have **not been loaded or re-saved in the game**.

## Use the controls

1. Finish any suspended battle, close the game and copy its native `save.dat`
   outside live save and Steam Cloud folders. Keep an untouched original.
2. Select **Dynasty Warriors 7: Xtreme Legends Definitive Edition · PC** and
   **Open Save Copy**. Use **Inspect Data → Equipment** to identify an officer's
   two inventory records. Officer labels are physical slots; character names and
   weapon names are not inferred from an unverified catalog.
3. Select **Weapon loadouts** in Categories and the desired officer in Record.
   Select **Weapon 1** or **Weapon 2**, choose an inventory slot, then
   **Apply Selected**. **Find choices** filters the choices by their displayed
   inventory slot. Each choice was already equipped by a playable officer in
   the opened copy and still has its ownership bit. It can be shared across
   officers, but one officer's two slots must refer to different physical records.
4. To change seals, inspect **Inspect Data → Applied seals**, then select the
   **Applied seals** category and the physical weapon record. Select an occupied
   position and choose an already learned **Seal ID**, or **Remove seal**.
   Apply the change. IDs identify stored seals; a matching name/effect catalog
   has not been qualified, so the editor does not invent names for them.
5. Use **Review Changes** to check the staged values. **Undo** or
   **Revert Selected** restores opened values. **Save As...** writes a new `.dat`
   copy with a backup and native read-back validation. Keep the original and
   test a disposable edited copy in the game.

**Equipment → Active weapon** retains the existing first/second switch control.
The new loadout and seal choices are excluded from Max, and experimental numeric
limits do not expand their allowed choices.

## Why some weapons or slots are unavailable

| Control | Qualification and limits |
| --- | --- |
| Weapon choices | Only owned references already equipped across the 65 playable officer slots in the immutable opened copy. Other owned inventory entries remain unavailable because ownership alone does not prove the game's external DLC/availability checks. |
| Officer loadout | The opened active index must be 0 or 1, its selected reference must be owned, and the original pair must differ before new controls appear. A changed final pair must differ and retain a valid owned active weapon. |
| Applied seal choices | Ordinary IDs 0–63 already learned in this copy. The native picker excludes IDs 64–91 even though the low-level storage setter accepts them. |
| Editable seal positions | Only positions occupied by a qualified seal when this copy was opened. The weapon must be owned, have recognized status bits and contain distinct learned ordinary IDs or empty sentinels. Unknown, duplicate or unlearned original vectors stay read only. |
| Empty positions | `0xFFFF` means empty. It does not distinguish available capacity from a position beyond the variant's capacity. Empty positions cannot be filled. |
| Removal | Replaces the selected occupied reference with `0xFFFF`; neighboring positions are not compacted. Before saving, Undo can restore the opened seal. After reopening the removed copy, that empty position is read only; use the game or reopen the untouched original to restore it. |
| Smith learning | Five reserved smith-learning references are excluded from new equipment and applied-seal choices. The editor does not cancel or complete learning assignments. |
| Suspended battles | Any nonzero suspension flag hides the new loadout and applied-seal controls. Finish the battle in the game; the editor does not synchronize embedded battle equipment. |

The full pending map is validated together, including duplicate references and
duplicate seals. Changing a seal does not acquire it, increase its learning
meter, grant ownership or update rewards. Existing unlearned **seal-meter
reduction** remains a separate feature. Unusual original or untouched state is
preserved; unavailable new controls do not suppress unrelated qualified edits.

Save As returns a freshly parsed copy. Its qualified choice pool can therefore
shrink when a reference is no longer equipped by any playable officer, or when
a seal position becomes empty. The untouched original retains the original pool.

## Native format evidence

Offsets below are decoded payload positions, excluding the four-byte PC
checksum/seed header. Values are little endian. The existing codec validates
framing, revision and native checksum and retains the original cipher seed.

| Stored structure | Position and type |
| --- | --- |
| Playable officers | First 65 of 92 physical records, base `0x2039`, stride `0x80` |
| Equipped references | Officer `+0x12` and `+0x14`, separate 16-bit IDs; qualified choices below 1,738 |
| Active index | Officer `+0x16`, 16-bit value 0 or 1 |
| Weapon records | Base `0x4E39`, 1,738 records, 20 bytes each |
| Weapon status | Record `+4`, 16-bit flags; ownership bit 0. New seal controls require no unknown bits outside `0x1F`. |
| Seal learning meter | Record `+6`, 16-bit value; preserved by applied-seal editing |
| Applied seal references | Five separate 16-bit values at record `+8`, `+10`, `+12`, `+14`, `+16`; empty `0xFFFF` |
| Remaining weapon members | The first four bytes and trailing two bytes are preserved by these operations. They are not weapon attack or element controls. |
| Learned-seal mask | `0xC9C`, six 16-bit bit words; ordinary equippable choices are restricted to IDs 0–63 |
| Smith-learning reservations | `0x1564`, five 16-bit weapon references |
| Suspension flag | `0xDD1F`, one byte; zero required for the new controls |

The inspected executable's runtime weapon record is 68 bytes. Its first 23 bytes
are separately loaded parameter members, followed by live state, a physical
index and the 20-byte saved state. Runtime parameter offsets are **not save
offsets**: base attack is byte `+0x12`, element and its level are bytes
`+0x14/+0x15`, and seal capacity is byte `+0x16`.

Independent static disassembly supplies the following evidence. Addresses refer
to the inspected native PC binary, not executable patches or runtime hooks.

| Native routine | Evidence |
| --- | --- |
| `0x598BF2`–`0x598C35`, `0x5A5050` | Loads the separate parameter stream: one 32-bit member, six 16-bit members and seven bytes per parameter record. |
| `0x5A5310`, `0x5A4BF0` | Serializes 1,738 saved records of 20 bytes; does not serialize the static attack, element or capacity members. |
| `0x59D2C0`, `0x40F0A4`, `0x63DECE` | Resolves active-weapon parameter attack for combat and displays that parameter byte. |
| `0x5A49B0`, `0x63DD50` | Reads/displays the external element byte; the getter bounds it to 0–5. The adjacent byte supplies element level. |
| `0x64A8D2`, `0x63E02F` | Reads external seal capacity for slot selection/display. |
| `0x5A4D20`, `0x643063` | Writes one applied-seal reference at one of five positions. |
| `0x638FE3`–`0x639041` | Restricts selectable seals to IDs 0–63 and checks their learned bits. |
| `0x639321`–`0x6393A7` | Disables a seal already present on that physical weapon. |
| `0x639E44`–`0x639EA9` | Removes one seal with a direct `0xFFFF` write, without compaction. |
| `0x63B094`–`0x63B0D2` | Requires both ownership and availability predicates when constructing weapon choices. |
| `0x63BFF5`–`0x63C029`, `0x63C060`–`0x63C08C` | Excludes the other equipped reference and reserved smith-learning references. The editor conservatively excludes reservations without inferring a current runtime mode. |

These facts explain why an arbitrary base-stat or element writer cannot be
implemented by relabeling the saved seal references. Editing the matching game
parameter assets would require a separately qualified asset editor; this release
does not include one.

## Sources and validation

The [official Definitive Edition PC manual](https://cdn.akamai.steamstatic.com/steam/apps/968790/manuals/Steam_DW7XLDE_EN.pdf)
corroborates the two equipped weapons and seals. It does not supply disk offsets.
[vbvan's original 356Editor thread](https://game.ali213.net/thread-3969487-1-1.html)
distinguishes save, memory and LINKDATA editing. It concerns the **2012 Windows
editions**, and is a historical research lead, not qualification for Definitive
Edition. No third-party editor code or parameter catalog is incorporated.

Three distinct genuine public PC states passed native integrity and byte-exact
unchanged roundtrips. The earlier converter and Steam sharing references contain
the same state, counted once. The two later dated states appear to share a
creator; **three states do not establish three independent publishers**. All are
advanced saves, not controlled before/after game-action pairs. See the provenance
discussion in [DW7 XL conversion](DW7XL_CONVERSION.md#format-evidence).

An independent private audit made 17,865 assertions across these three states.
It checked every exposed choice/field and made 18 sampled surgical reference
exports, 18 seal replacements and 18 removals. Each export preserved every
unrelated payload byte, native seed and input file. The states exposed 53, 25
and 3 distinct equipped weapon choices, and 464, 356 and 361 occupied seal
positions respectively; these are observed counts, not universal capacities.

Public [loadout tests](../tests/test_dw7xl_loadouts.py) cover no-ops, typed bounds,
duplicate prevention, learned prerequisites, smith reservations, unknown records,
removal/reopening, pending-map dependencies, Max/experimental exclusions and safe
Save As/backup/restore. Their generated fixtures are procedural evidence.
Additional suspension and reservation audit cases were test-created derivatives
of native states, not captures of game actions. Private player files, account
context, game binaries and extracted assets are excluded from the repository and
release. No game code was executed, and edited in-game acceptance remains
unverified.
