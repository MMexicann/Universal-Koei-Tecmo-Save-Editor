# Persona 5 Strikers — English Nintendo Switch

The `p5strikers_switch` adapter opens complete **6 MiB extensionless `savedata`**
exports from the English Nintendo Switch game, title `0100801011C3E000`.
Export and reimport use an existing Switch save manager. The adapter edits a
separate local copy; it neither accesses the console nor converts PC/PS4 saves.
Japanese Switch saves use a different name width and are rejected.

## Implemented editing

Each qualified occupied player slot has Money, Persona points and unspent BOND
points. Existing named stacks cover ordinary consumables, prepared dishes,
cooking ingredients, incenses, ailment remedies and selected skill cards.
The two acquired native exports expose 194 and 222 controls respectively;
controls depend on each export's occupied slots and existing ordinary stacks.

Money and Persona points allow manual 0–9,999,999; BOND points allow 0–999.
Admitted existing stacks allow 1–99. These are conservative **manual editor
ranges**, not proved natural gameplay maxima, and all fields are excluded from
Max. Higher opened resource balances can remain unchanged or be restored by
unstaging. Zero, unusual, unknown and nonzero-adjacent item records are not
activated or normalized. Assigning an opened value unstages that edit.

The shared searchable workspace provides Undo, Review Changes, backups, atomic
Save As and validated restore. Inspectors separately display slot resources,
named existing stacks, ten named character level bytes and held Persona ID
words. Player names and account context are not returned by the inspectors.
Empty slots and reserved slot 0 are preserved.

An incense-stack change does not apply its stat effect. A skill-card change does
not teach a skill. Ingredient quantities do not unlock recipes. Persona/BOND
points remain separate from EXP, levels, allocated abilities and their reward
transitions. Resources and inventories do not complete story, requests or Jails.

## Platform qualification and integrity

The Switch profile has a 28-byte header, version bytes `00 20 01 20` (little-endian
`0x20012000`), selected slot −1 through 9, and ten serialized blocks. English
names each occupy 33 bytes; every block is `0x88DF4 + 66 = 0x88E36` bytes and
begins at `0x1C + index * 0x88E36`. All ten observed layout markers at block
`+0x938` must equal `0x0036EE7F`. The occupied-slot gate requires a non-`FFFF`
opening word and two bounded, nonempty, terminated UTF-8 names without control
characters. Unknown name layouts stay read only. Unused native tail bytes after
`0x558E38` must match the observed zero padding; output retains the entire
original 6 MiB span.

The complete Switch-tested reference writer performs selected little-endian
field replacements and writes the original full buffer directly. It has **no
native cipher, checksum repair or serializer-reconstruction step**. The separate
platform converter likewise constructs Switch output by preserving the header
and ten blocks with the declared name widths. The PC stream/checksum layer is
separate and is not applied here. The adapter declares `INTEGRITY_KIND='none'`;
console filesystem integrity and save-manager reimport remain external.

Version, slot boundaries, names, language markers and padding qualify the
observed profile. They do not detect arbitrary corruption in unknown payload
bytes; no invented checksum is claimed. No-edit output is byte exact. A targeted
edit changes only its qualified scalar byte span; original padding, headers,
other slots, history, ownership and unknown bytes remain identical. Each output
is reparsed before safe saving.

## Independent facts and source licences

- [Amuyea's complete Switch-tested editor](https://github.com/Amuyea-gbatemp/Persona-5-Strikers-Scramble-Save-Editor/tree/7466afbb3c1bbcf550d4ff5c18e293103969e678),
  GPL-3.0: its full Open, Save, field-read and field-write paths were inspected
  statically. No source code, cheat action, binary, full catalog or game asset is
  copied or executed. Independently checked scalar/name facts are used.
- [zarroboogs' platform descriptor/converter](https://github.com/zarroboogs/p5spc.saveutil/blob/2462a2043aba3bc551d2eb6b732a81d2374aa826/src/p5spc.saveutil/Save/SaveConvert.cs)
  independently distinguishes English/Japanese Switch, PC and PS4 geometry.
  No explicit implementation licence was identified; no foreign implementation
  is incorporated.
- [The Switch-specific hex-edit discussion](https://gbatemp.net/threads/persona-5-strikers-hex-edit.584529/)
  corroborates resource identities, native little-endian data and item mechanics.
- [The public NX_Saves catalog](https://github.com/Viren070/NX_Saves/tree/main/nintendo/switch/savegames)
  supplied two complete distinct Switch exports, separately from the PC player
  files. Both have title-labelled archive provenance, all ten English markers,
  different occupied slots, and exact observed framing. Their balances include
  unusual edited values; they are not natural-cap evidence. Player data, owner
  information, archives, native/decrypted files and private paths are not shipped.

The already independently written project catalog and generic P5 inspectors are
reused. Every curated resource/item position was separately compared against the
actual **Switch** writer's absolute tables for all nine slots; every position
matches after accounting for its documented slot base. Character-level and held
Persona offsets were likewise matched for all nine Switch slots. This is not
an assumed PC-to-Switch offset translation. The only source-label difference in
the curated subset is trailing whitespace on one skill-card name.

Resource words are four little-endian bytes at block-relative `0x8788E`,
`0x87892` and `0x876E2`. Existing ordinary item quantities use the published low
byte, admitted only when the adjacent byte is zero and opened quantity is 1–99.
The source's generic four-byte item writer can overlap adjacent two-byte entries;
our one-byte writer preserves those surrounding bytes.

## Mechanics coverage and precise blockers

| System | Coverage or required next evidence |
| --- | --- |
| Money, Persona points, unspent BOND points | Implemented for qualified occupied slots; individual edits, no asserted natural-cap Max. |
| Consumables, dishes, ingredients, incenses, remedies, selected skill cards | Existing named ordinary stacks implemented; no ownership manufacture, recipe unlock, stat application or skill teaching. |
| Character levels and held Persona records | Searchable read-only inspection. EXP curves, derived stats, capacity, ownership and skill prerequisites are required before writes. |
| Weapons, armor, accessories and equipment | Preserved. Need stored ownership/equipped references, legitimate record states and dependencies before adding equipment edits. |
| Persona growth, fusion, compendium and skill sets | Preserved. Need occupied-record structure, legal IDs, reference validity, EXP/stat derivation and compatible skill maps. |
| BOND levels and allocated skills | Preserved separately from unspent points. Need thresholds, allocated flags, natural limits and reward relationships. |
| Recipes, requests, Jails, story, collections and NG+ | Preserved separately from resource edits. Need controlled unlock/completion/reward pairs and prerequisite mapping. |
| English PS4 CUSA19640 | Implemented separately in [its PS4 export adapter](P5STRIKERS_PS4_FORMAT.md); not opened or converted by this Switch adapter. |
| Japanese Switch, Japanese/other-region PS4 | Separate format/profile qualification, title-labelled native exports and safe import contract required. No platform fallback. |
| Edited in-game loading | Not performed by this project; actual export/edit/reimport/load/re-save validation remains separate. |

## Testing and storage

`tests/test_p5strikers_switch.py` covers procedural distinct unknown bytes,
full geometry and foreign-platform/language rejection, all curated field spans,
invalid values/types/keys, unknown records, higher resource preservation,
original unstage, frozen snapshots, source changes/deletion, mutation during
backup, resolved aliases, bounded forged restore and actual Tk named search,
Undo, Review Changes and Save As. A modified reserved tail with a regenerated
backup-manifest hash is rejected by the native profile gate.

Optional `P5S_SWITCH_SAVE_COPIES` selects private native paths separated by the
host platform's path separator. Both genuine exports undergo complete no-edit,
every-field targeted byte comparison, safe saving, backup/restore and the copied
CLI self-test. The self-test correctly reports no native checksum verification
and no edited game-load test. Full original bytes and file length are retained;
source reads are checked before backup and again immediately before writing.
