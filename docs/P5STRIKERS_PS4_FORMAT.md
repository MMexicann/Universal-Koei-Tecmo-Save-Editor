# Persona 5 Strikers — English PlayStation 4 export

The independent `p5strikers_ps4` adapter opens a copied **decrypted `APP.BIN`**
from English PS4 title **CUSA19640**. Keep its original **`sce_sys/param.sfo`**
in the copied export folder. Export/decryption, account ownership, keystone,
console filesystem integrity and PS4 reimport/resigning remain external. This
adapter does not decrypt PS4 storage, copy owner metadata or convert platforms.

## Implemented features and mechanics

Qualified occupied slots expose Money, Persona points and unspent BOND points.
Named existing ordinary stacks cover consumables, prepared dishes, cooking
ingredients, incenses, ailment remedies and selected skill cards. The acquired
early-game native export exposes **23 controls**: three resources and twenty
existing stacks. Other occupied slots/stacks may expose additional curated
controls; empty/reserved slots and unknown records remain unchanged.

Manual Money/Persona-point bounds are 0–9,999,999, BOND points 0–999 and admitted
ordinary stacks 1–99. These conservative editor bounds are not asserted natural
caps. Every field excludes automatic Max. Higher opened resource values remain
intact and assigning an opened value unstages the change. Stacks qualify only
with positive ordinary quantity 1–99 and zero adjacent byte; acquisition,
zero/higher quantities and nonzero adjacent records stay read only.

The shared GUI includes named search, Undo, Review Changes, backups, atomic
Save As and validated restore. Four inspectors show resources, named stacks,
ten named character level bytes and held Persona IDs. Player names and owner
identifiers are never displayed. Resource controls do not teach skills, apply
incense stat gains, unlock recipes, allocate BOND abilities, fuse/register
Personas or complete requests/story. These transitions remain under game control.

## Native format and integrity

The qualified complete payload is **5,627,068 bytes (`0x55DCBC`)**. The public
full platform converter explicitly distinguishes this English PS4 geometry from
Japanese PS4 (`0x55DB2C`), English/Japanese Switch (`0x600000`) and encrypted PC
(`0x55DEA0`). It preserves the 28-byte header and explicitly copies all ten
serialized field blocks between platforms; the documented name widths are 33
bytes for each English name and 13 for Japanese. Thus field reuse follows a
complete platform serializer, not an assumed size adjustment or guessed offset.

Version bytes are `00 20 01 20`, selected slot is signed little-endian −1..9,
block stride is `0x88DF4 + 66 = 0x88E36`, and block base is
`0x1C + slot * 0x88E36`. All ten layout markers at block `+0x938` must equal
`0x0036EE7F`; all native padding after `0x558E38` must be zero. Occupied slots
require a non-`FFFF` opening word and two nonempty terminated bounded UTF-8 names
without control characters. Names qualify record shape and are discarded from
inspection results. Unknown name states stay read only.

The complete converter directly emits PS4 header/blocks/zero padding, without a
native cipher or checksum operation. The full factual editor writes selected
little-endian fields in its original buffer and saves the whole buffer directly;
its authors explicitly tested Switch, with PC/PS4 not yet game-tested. This
project independently validates a genuine decrypted PS4 export and uses the
complete PS4 serializer plus its platform/name markers. The adapter honestly
sets `INTEGRITY_KIND='none'`. Its profile gates cannot detect arbitrary corruption
in unknown bytes, and no invented checksum or repair is applied.

Resources are little-endian u32 at block-relative Money `0x8788E`, Persona points
`0x87892` and BOND points `0x876E2`. The existing independently curated project
catalog supplies factual item identities; all positions match the Switch-tested
writer's absolute tables across nine slots and are preserved verbatim by the
complete English PS4 converter. One-byte stack edits preserve the source's
adjacent two-byte entry storage; the foreign four-byte generic writer is not
reproduced. Every output preserves native length, padding and all unrelated bytes
and is reparsed before atomic saving.

## Mandatory identity and storage protection

The bounded SFO reader interprets only public `TITLE_ID`, rejecting malformed,
missing, duplicate or foreign title identity. It reads at most 4,097 bytes and
accepts only the observed PSF 1.1 table framing. Other owner/signing values are
never decoded or returned. An opaque hash of the entire original SFO binds the
opened document, destination and context sidecar of each backup; the same title
with changed metadata cannot silently change context.

Source bytes and original metadata are checked before backup and immediately
before writing. Destination metadata is checked before and after backup.
Resolved aliases/existing destinations reject, backups retain immutable original
bytes, and restore validates bounded bytes plus native format and exact context.
Save As uses a new `.bin` copy within the same copied export folder or a separate
folder containing the same unchanged original SFO. No `sce_sys` files are edited
or created by ordinary editing/storage. The copied CLI diagnostic generates
public title-only metadata for its temporary test folder; this is not an
importable PS4 export and does not copy signing/account data.

## Sources and licence boundaries

- [Complete platform converter](https://github.com/zarroboogs/p5spc.saveutil/blob/2462a2043aba3bc551d2eb6b732a81d2374aa826/src/p5spc.saveutil/Save/SaveConvert.cs):
  English/Japanese PS4 sizes, name widths, fixed ten-block copy and direct full
  save output. No explicit implementation licence was found; only format facts
  inform an independent implementation.
- [Full factual editor](https://github.com/Amuyea-gbatemp/Persona-5-Strikers-Scramble-Save-Editor/tree/7466afbb3c1bbcf550d4ff5c18e293103969e678):
  GPL-3.0, statically inspected complete Open/Save and scalar/name tables. No
  source, patch action, complete catalog, executable or asset is copied/executed.
- [Public native PS4 export](https://github.com/bucanero/apollo-saves/tree/master/PS4/CUSA19640):
  original decrypted `APP.BIN` and original `sce_sys/param.sfo`. Its title,
  English names, ten markers, framing and zero tail match the independent full
  converter. Player data, signing metadata, archives and private paths stay
  outside source and release artifacts. Shared progress is not natural-cap proof.
- [Switch-specific mechanics discussion](https://gbatemp.net/threads/persona-5-strikers-hex-edit.584529/)
  corroborates the resource identities; item mechanics and existing generic
  inspectors are documented in the [PC](P5STRIKERS_PC_FORMAT.md) and
  [Switch](P5STRIKERS_SWITCH_FORMAT.md) format notes.

## Coverage and remaining inputs

| System | Implemented scope or exact blocker |
| --- | --- |
| Money, Persona points, unspent BOND points | Individual qualified occupied-slot edits; no natural-cap Max or history/EXP changes. |
| Ordinary named stacks | Existing consumables/dishes/ingredients/incenses/remedies/selected cards; no acquisition, recipes, teaching or stat application. |
| Characters and held Personas | Searchable read-only level/ID inspection. Need EXP/stat/reward derivation, capacity and ownership evidence before writes. |
| Equipment, Persona growth/fusion/compendium/skills | Preserved. Need occupied structures, references, legal IDs and dependent transitions. |
| Allocated BOND abilities, recipes, requests, Jails, story, gallery/collections/NG+ | Preserved separately from resource edits. Need controlled action pairs, named flags and prerequisite/reward mappings. |
| Other PS4 regions, Japanese PS4 and revisions | Need original title metadata, complete decrypted native exports and independent geometry/integrity qualification. No fallback into PC/Switch parsers. |
| PS4 import and edited game loading | External save-management workflow; project has not loaded or re-saved an edited file in the game. |

## Verification

`tests/test_p5strikers_ps4.py` covers all curated surgical spans, no-op roundtrip,
strict values/keys and frozen snapshots, empty/unknown/foreign records,
original-value unstage, higher/unusual preservation, source changes/deletion,
backup-time races, resolved aliases and bounded forged native/context restore.
Mandatory missing/foreign/malformed SFO, same-title changed context, mismatched
destination context and destination mutation during backup reject before write.
Actual Tk workflows cover native Open, named search, Apply/Undo, Review Changes,
Save As, backups and all four inspectors.

`P5S_PS4_SAVE_COPIES` optionally selects private complete native `APP.BIN` paths,
with their original `sce_sys/param.sfo` beside each. Every genuine native control
is independently edited/serialized/reparsed and compared byte-for-byte outside
its scalar range. Native backup/restore and copied CLI self-test retain source
bytes. The self-test correctly reports no native checksum verification and no
edited game-load validation. Procedural fixtures are explicitly not genuine or
playable saves; native checks skip explicitly without private input.
