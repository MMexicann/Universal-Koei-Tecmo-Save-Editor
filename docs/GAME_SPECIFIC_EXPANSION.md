# Game-specific editing expansion

Version **3.0** deepens existing editors. The registered inventory remains
97 game/platform profiles; no additional edition is qualified by these changes.
Use a separate save copy and review staged changes before Save As. Native-file
checks and application workflows do not establish edited game loading/re-saving.

## DW3 Complete Edition Remastered

- Copy the applied bonus layout from another qualified owned weapon copy.
  Every destination retains its own rank/count rules, ordinary-roll limits,
  rare-bonus packing and unique-weapon stock exceptions. Source-only and
  experimental high rolls cannot be transferred to an incompatible destination.
  Identity, element, hit flags, acquisition time, equipped references and the
  first-acquisition collection snapshot are separate and remain unchanged.
- Apply an element to the qualified owned weapon copies in the current filter.
  Existing bonus layouts and unrelated flag bits are preserved.
- Select individual named music/movie gallery entries to unlock. This reuses
  the existing availability mapping, preserves acknowledgement arrays and
  unshown tail entries, and retains the native lazy-array defaults.

These actions reuse the tagged schema and audited patch writer; they do not
introduce binary offsets or a new format. [Weapon proof](WEAPON_ROLLS.md) and
[tagged save format](SAVE_FORMAT.md) describe the established mappings.

## Dynasty Warriors 8 XL — Windows PC

An existing ranked weapon attribute can be replaced using a finite palette of
qualified ranked IDs also present in the opened save. Only already populated,
normally ranked slots qualify; empty, unknown and unusual records remain opaque.
The final pending weapon must retain distinct attribute IDs and supported ranks.
The rank, affinity, attack, inventory state and equipped references remain
separate controls. Replacement is excluded from Max and experimental expansion.
Choosing an ID already in another eligible slot swaps the two identities in one
staged action, retaining each position's rank. Undo or Revert Selected on both
identity fields restores the pair; a partial restore that would duplicate an ID
is rejected.

The permanent PC weapon record independently describes the six ID bytes at
`+6..11` and paired ranks at `+12..17`; the original PC native sample corroborates
the ranked identities. The existing [weapon-fusion reference](https://steamcommunity.com/sharedfiles/filedetails/?id=268825547)
describes replacing an attribute. The editor changes the selected existing
property, without simulating material consumption, a sacrificed weapon or rewards.
Native aptitude choices expose the established 25/50/75/100 stored units as
one/two/three/four stars; affinity retains explicit IDs because its localized
numeric-name mapping is unproved. [Earlier evidence](DW8_COMPATIBILITY.md).

## Warriors Orochi 3 Ultimate Definitive — Windows PC

The existing compatibility-reset field retains its stable ID and gains manual
entry from **0 to 5,600 stored raw units**. Native setter `0x14026C7C0` clamps by
descriptor grade, using `1400 * 2**(grade + 3)` for grades -1 through 4; ordinary
weapons limit the grade to 3. Thus 5,600 fits the lowest admitted grade. It is a
conservative editing bound, not a universal natural cap or a displayed star count.
Higher qualified originals can be preserved/restored exactly, but arbitrary
higher values require the missing grade descriptors. Max and experimental
expansion remain excluded. Attack is derived by the game; it is not overwritten.

Spendable **rare crystals** are a separate two-byte balance at file `0xD5DC`.
Native serializer `0x14025DE60` and the system-copy bridge identify that word;
the native gain routine clamps it at 999 and blacksmith spending subtracts from
the same word. Lifetime crystal earnings are separate and preserved. The native
gem gain routine also establishes a **9,999,999** balance ceiling, correcting the
earlier conservative 999,999 editing limit. Unknown bytes and unusual original
values retain the existing preservation rules. [Prior scope](WARRIORS_V26_DEPTH.md).

## Dynasty Warriors: Origins — Steam slots

Selected qualified provinces accept peace as an exact percentage in **0.01%**
steps, converted to the already mapped native units without floating-point
rounding. Existing formed-bond training counters have a targeted count-at-least-3
action that preserves higher opened or pending counts. It sets only the stored
count condition: bond events, learned Battle Arts, rewards and prerequisite flags
are separate. Both actions stage one reviewed Undo operation.

Native bond-level and monotonic battle-history choices clarify existing fields.
Weapon inspection now distinguishes the stored instance identity, opaque flag
bytes and why reinforcement is or is not qualified; inspection creates no new
weapon, identity or flag writer. [Native format](ORIGINS_FORMAT.md).
Proficiency levels and Old Coin writers remain
[unimplemented for their documented reasons](ORIGINS_REQUEST_STATUS.md).

## Fire Emblem: Three Houses — Nintendo Switch

Rename the existing qualified protagonist in the admitted main-campaign v13/v23
profiles. New input is conservatively limited to 1–8 printable ASCII characters;
this is an editor restriction, not a recovered natural name limit. Existing
canonical UTF-8 names, including longer or non-ASCII originals, are exact no-ops
and can be restored through Undo. A unique living, joined, available Byleth record
and known name framing are required. Recruitment, gender, appearance and
system-file previews are separate.

The 40-byte name buffer starts at payload `0x8984` in v13 and `0x9014` in v23.
The pinned historical layouts and later isolated `SetName` writer establish the
storage facts; interpreted independently from
[the reviewed source](https://github.com/hashcade/feth-save-editor/tree/b9f53f0e01a3dd2cd24c96f97f1a829e51a1f00d).
The new writer preserves the opened `1B 4E 30` or `1B 4E 31` closing control,
rather than copying an external writer's normalization. Malformed framing,
unknown nonzero padding and unqualified owners remain unwritable. The native
payload checksum is recomputed and every requested value reparsed.
[Original format and licence boundaries](THREE_HOUSES_FORMAT.md).

## Samurai Warriors

**SW5 Windows revision 39, current My Castle checkpoint:** edit quantities of
already held skill gems at their existing type/rank. Native inventory has 1,000
quantity bytes; the current checkpoint starts them at `0x1966A`. Native grant
`0x14014C060` validates the gem type/rank, indexes `type * 10 + rank`, clamps held
quantity to **20** and writes that quantity byte independently. Serializer
`0x1401271C0` and current-copy vector binding `0x140142A70` corroborate the exact
storage. Only positive opened quantities at rank indices 1–9 get a control;
minimum 1 preserves the held stack. Empty/rank-zero entries, identity, rank,
learned weapon skills, older checkpoints and reward state remain unchanged.
The hard stack limit applies in experimental mode; Max preserves higher unusual
originals. Asset-dependent gem names and new acquisition remain unqualified.
Keep the original owner companion required by the
[existing SW5 format](SAMURAI5_PC_FORMAT.md).

**SW4 DX:** qualified own-pool weapon choices identify native weapon/skill
records; existing skill activation and one-way playable flags have explicit
choices. **Original PC SW2:** existing acquired ordinary skills expose rank
1/2/3 choices and owned weapon choices show their stored identity. These controls
retain existing native validators; no rare-skill acquisition, progression cap,
mount ownership or Chronicle/story dependency is inferred.

## New-game and platform qualification

The current research still does not qualify new registrations. Original-PC
Samurai Warriors: Spirit of Sanada lacks complete inner integrity and action
mapping; PSP Special editions need authenticated plaintext, their own native
integrity and dependency evidence. Gundam 2 PS3 pilot growth needs pilot-specific
curves and reward relationships. Atelier Plus candidates retain unresolved
own-title writer/integrity proof. Nioh/Nioh 2 and Ninja Gaiden candidates with
unresolved active body integrity stay read-only. See
[additional-title qualification](EXPANSION_CANDIDATES.md) and
[remaining exact inputs](REMAINING_INPUTS.md).

No checksum is bypassed and no neighbouring edition supplies writable offsets.
No release, tag, version bump or binary publication accompanies this source work.

## Validation evidence

Procedural regressions exercise bounds, malformed and unqualified records,
complete pending maps, typed opened-value restoration, surgical byte changes,
native integrity, Max/experimental exclusions and source/copy safety. Real Tk
workflows cover Apply, Review Changes, Undo, Save As, backup and restore.

Independent native-file checks include DW8 attribute edits; two WO3 references
with ten resource/compatibility destination exports; a revision-29 Origins slot
with 48 localized peace/training assignments; eight Three Houses exports (four
per admitted revision); and all 44 held gem stacks in the supplied SW5 checkpoint.
DW3's new workflows use procedural tagged fixtures and established native mapping
evidence; a new genuine DW3 fixture was unavailable in this session. Native inputs
and owner companions remain private. No edited file was loaded and re-saved in
an actual game during this work.
