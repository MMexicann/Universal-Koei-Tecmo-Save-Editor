# Samurai Warriors PC coverage and evidence

The additional PC investigation is recorded separately for
[SW4-II](SW4II_FORMAT.md) and [Spirit of Sanada](SANADA_PC_RESEARCH.md).
SW4-II's revision, stream and exact native checksum profile are independent of
DX. Sanada's tested outer framing remains unregistered research without
gameplay writes or a claim of qualified inner integrity.

The latest SW4-II/original SW2 equipment expansions and renewed SW4 DX native
dependency review are recorded in
[Samurai / classic Dynasty editor depth](SAMURAI_DYNASTY_DEPTH.md). DX's existing
functional controls below retain their scope: external proficiency conversion,
growth and mount-ownership rules remain unresolved rather than becoming
independent writes.

## Samurai Warriors 4 DX: implemented native PC adapter

The adapter accepts gameplay `SAVEDATA0000.dat`–`SAVEDATA0004.dat` copies,
exactly `0xC8210` bytes, with payload revision `0x39EA`. Image/screenshot slots,
console saves, SW4-II saves and older migrating PC revisions are rejected.
The filename is descriptive, not an identity check: revision, all native
checksums and the 55 consecutive standard officer identities qualify the data.

Implemented controls:

- Gold, with native maximum 999,999, and eight gem counters, maximum 99 each.
- Five stored base stats for each of the 55 standard officers: health, attack,
  defense, riding and speed. These are manual edits; their unsigned 16-bit
  storage bound is not a gameplay maximum and they are excluded from Max.
- Standard playable unlocks, with the native new-character badge. This is a
  one-way content unlock. Story/stage completion, EXP and other flags remain
  unchanged; relocking is unavailable. A locked officer is offered only when
  their currently equipped own-pool weapon slot is mapped and occupied.
- Equipped weapon slot selection, restricted to an existing occupied mapped
  weapon in that standard officer's own eight-slot pool.
- Existing weapons in 60 eight-slot weapon families: named attached skills,
  current skill level up to that slot's existing stored ceiling, and skill
  activation/locking. Empty weapons, empty skills, unknown IDs and unusual
  ceilings or zero current levels never become writable records. Max preserves higher existing
  values and locked state, and never changes skill identities or ceilings.
- Searchable weapon/skill inspection, with identity, current level, ceiling
  and raw flags; read-only officer level/EXP/proficiency/equipment/unlock
  inspection; spending and kill history inspection.
- Existing shared themes, retained sessions, batch Undo, Review Changes,
  automatic backups, source-change detection, atomic Save As and restore.

Standard officers and weapon families use explicit record/ID labels. The
character-name dictionary and gem order have not been qualified for this DX
build, so labels do not guess names from a different Samurai Warriors game.
The weapon skill dictionary is the published SW4 40-skill enumeration.

### Native format and static evidence

The attached x64 executable was inspected statically. Its SteamStub code
section was decoded in a private analysis copy; neither the original nor the
analysis copy was executed or included in the repository. All locations below
are native virtual addresses in the investigated build, not save offsets.

The first `0x20C` bytes of the save are a retained clear slot/menu header.
At file `0x20C`, `<HH` stores a 16-bit checksum and a 16-bit stream seed.
The `0xC8000`-byte payload begins at `0x210`. For each little-endian DWORD:

```text
state = (state * 0x5B1A7851 + 0xCE4E) modulo 2^32
word ^= state
```

Writer `0x1404B68E0` sums all payload little-endian 16-bit words modulo 2^16.
Reader `0x1404B6990` contains a shorter-sum check whose return value its caller
ignores. The genuine sample matches the writer's full sum; its last DWORD is
nonzero. The implementation therefore validates the writer's full sum and all
four gameplay checksums. It does not discard or zero the tail to force the
reader's ignored check to pass. The shared Koei DWORD stream implementation
is reused without importing a foreign editor.

Reader `0x140194F00` and writer `0x140194990` establish these current-revision
payload sections, with each byte sum named `a` through `f`:

| Section | Offset | Length |
| --- | ---: | ---: |
| a | `0x8` | `0xEC` |
| b | `0xF8` | `0x858` |
| c | `0x950` | `0x32A` |
| d | `0xC7E` | `0x71BC` |
| e | `0x7E3A` | `0xD68` |
| f | `0x8BA2` | `0x77F34` |

Checksums at payload `0x4`, `0xF4`, `0xC7A`, `0x80AD6`, respectively, are:

```text
((d+a)*b+e) & 0x7FFFFFFF
((f+d+b)*a) & 0x7FFFFFFF
(d+c+b+a) & 0x7FFFFFFF
(checksum1+checksum2+checksum3) & 0x7FFFFFFF
```

Edits recalculate these four values and the envelope checksum, retaining the
original stream seed, menu header, padding, history and unknown payload bytes.
The native reader also recognizes historic revisions `0x18D2`, `0x1CF5`,
`0x2118`, `0x253B`, `0x295E`, `0x2D81`, `0x35C7`; these require separate
layout-migration qualification and are not advertised as supported.

Gameplay evidence, relative to section d unless otherwise stated:

| System | Native evidence | Saved mapping |
| --- | --- | --- |
| Officers | `0x140067A60`, stride `0x44`; standard IDs below `0x37`, custom IDs `0x37`–`0x4A`, NPC IDs `0x4B`–`0x7D` | First 55 records at payload `0xC7E`; consecutive u32 officer IDs |
| Stats / progression | Native getters `0x14018BE40` onward; SW4-II memory schema corroborates base stat ordering | Record EXP `+8`, level `+0xC`, proficiency EXP `+0x10`–`+0x1C`, base stats `+0x20`–`+0x28`, proficiency levels `+0x2A`–`+0x2D` |
| Playable unlock | Story reward `0x14018F11A` sets flag bit 0 and bit 2 when previously locked | Officer `+0x3F`; other bits preserved |
| Equipped weapon | `0x140067C18` / `0x140067C6D` reads own-family slot and copies the selected `0x22` record | Officer `+0x3B`, eight slots |
| Weapon inventory | `0x14018D1E0` resolves type aliases and eight-slot pools; empty initializer `0x14018B1D0` | Payload `0x3DE6`, 60 families × 8 slots × `0x22`; u16 identity 180 means empty |
| Attached skill ceiling | Generator `0x140083C0E` stores a rank 1–5 | Weapon `+2`–`+9` |
| Skill identity/current level | Active-skill getter `0x14018B0B0`; generator `0x140083C6F` bounds current level by ceiling | Weapon IDs `+0xA`–`+0x11`, current levels `+0x12`–`+0x19`; ID 40 means empty |
| Skill flags / upgrades | Option gating `0x14047E600`; upgrade `0x14047E71F` | Flags `+0x1A`–`+0x21`; bit 0 locks a skill, bit 1 marks its special-gem unlock. Reaching level 5 sets bit 1; lower edits retain it |
| Gold | Add/spend `0x14018D010` / `0x14018D040`, literal cap 999,999 | `+0x7128`; cumulative spend `+0x712C` is separately preserved |
| Gems | Reward `0x14018D6B0` onward and upgrade `0x14047E6D3`, literal cap 99 | Eight bytes `+0x71A2`–`+0x71A9` |

Locked level-5 skills are not an invented state: the native generator first
randomly sets lock bit 0 at `0x140083ACC`, independently generates the ceiling
and current level at `0x140083C14`/`0x140083C79`, and sets marker bit 1 for
current level 5 at `0x140083C82`. The activation branch at `0x14047E734` clears
only lock bit 0 and skips level increment. This permits keeping the original
lock during level Max and activating a skill without changing its level.
The editor does not simulate gold/gem consumption or manufacture upgrade
rewards; these are independent resource and existing-record edits.

### Genuine sample and checks performed

A freely shared native DX save was found in this public
[Steam discussion](https://steamcommunity.com/app/2719200/discussions/0/4703539571985644358/).
The author describes level-50 characters, claimed DLC weapons and seven
completed stories. The linked save was downloaded privately and never added
to the source or release. Account information, save URLs and player data are
not emitted by the adapter or tests.

The genuine file qualified all four gameplay checksums, the full native
checksum, current revision and 55 standard identities. Its weapon records
corroborate the empty sentinel, 60 weapon families, eight skills, stored
ceilings/current levels and DLC initialization. Actual-copy no-edit roundtrip
was byte-exact. A targeted gold edit was re-encoded/reparsed, and decrypted
byte differences were confined to the intended field and the four checksum
words; the header and seed were retained.

The focused suite passes 12 tests when the private copy and a Tk display are
available: procedural malformed/foreign/corrupt input rejection, bounds,
flag dependencies, empty-record exclusion, higher-value preservation,
targeted surgical edits, backups, restore, original/source guards, genuine
roundtrip/gold/weapon/base-stat edit qualification, and GUI search/edit/review/Undo/Save As/theme
workflows. Procedural data is generated, not a substitute for a genuine save.
No test claims that an edited save was loaded in the game.
An additional independent nine-test contract review covers mutable snapshot
rejection, exact-bytes restore qualification, unusual rank preservation,
starter-weapon guards, flag-order independence, live-path rejection and the
shared scalar contract.

```text
python -m unittest tests.test_samurai4dx_format tests.test_samurai4dx_gui -v
```

An optional `SW4DX_SAVE_COPY` environment variable points to a private genuine
copy for the native qualification test. Without it, that test is skipped.
GUI tests skip when Tk cannot create a display.

An additional supplied current-revision `SAVEDATA0000.dat` qualifies all
integrity layers and 55 officer identities, with 1,834 dynamic writable fields
in its particular occupied-record state. Its unchanged roundtrip and the
existing native field/GUI regressions pass. The unreleased follow-up also
rejects negative, non-integer and unknown pending edits before Max can transform
them; Max cannot hide an invalid staged change. No game-load check is claimed.

### Per-mechanic coverage checklist

| Mechanic | Status / precise remaining blocker |
| --- | --- |
| Gold, eight gem resources | Implemented/tested; gem name/order dictionary is in external assets and lacks a qualified DX enumeration |
| Base health/attack/defense/riding/speed | Implemented/tested manual values; character growth caps require the external growth tables, so these have no Max action |
| Standard playable characters | Implemented/tested monotonic unlock when the officer has a valid occupied equipped weapon; native story reward mask is applied without campaign completion. No missing starter weapon/skill records are manufactured |
| Character names | Read-only numeric identity labels; DX officer string/asset dictionary is unavailable, and a different game's order is insufficient proof |
| Level / character EXP | Inspected; native level cap 50 and EXP locations known, but growth thresholds and level-derived stat/reward tables come from external assets. No independent level/EXP writes |
| Attack-move proficiency | Inspected; native maximum level 20 and EXP cap 999,999 known. Its level/EXP conversion table is external; writing either alone would create an inconsistent pair |
| Weapons / attached skills / elements | Existing inventory inspected; current skill levels and activation implemented/tested. Skill names include Blaze, Shock, Frost, Wind, Diamond and Reaper; these are attached weapon skills, not a separate invented element inventory |
| Equipped weapons | Implemented/tested occupied own-pool selection; unknown/empty identities rejected |
| Weapon types / rare/DLC weapon manufacture | Identity inspected. Template, attack values and valid owner/type aliases are external assets; no creating rare/DLC weapons or assigning a foreign type |
| Weapon skill replacement / ceiling changes | IDs/ceilings inspected. No qualified duplicate/exclusion/template rules or named DX weapon dictionary, so identifiers and ceilings remain unchanged |
| Reforging / melting / gem exchange | Native tutorials and upgrade flow inspected. These are inventory/resource transactions with costs, type templates and rewards; only independent safe resource/skill edits are available, not fabricated transactions |
| Officer personal skills / abilities / musou gauge | Bytes present in officer records, but full skill/gauge schema and derived modifiers are not qualified; no writes |
| Mount ownership / equipped mount | Equipped reference inspected; mount inventory identity/ownership schema and special-mount prerequisites need qualified asset tables or before/after saves |
| Battle consumables / other equipment | No qualified saved item record dictionary, stack caps and ownership/equip dependencies; existing bytes retained |
| Custom character creation / appearance / names | Native 20-slot stride `0xCC` found; presence/type aliases/appearance/name dependencies need actual created-character save pairs and asset schema. No manufacture or editable personal names |
| Chronicle exploration / life goals / mentor / friendship / biography | Native tutorials confirm these systems and the Chronicle section. Node/goal/officer dictionaries and reward/prerequisite masks are external; require qualified assets or targeted Chronicle save pairs |
| Companions / bodyguards | Chronicle companion behavior discovered; no independently qualified saved companion selector/availability schema. Do not equate officer IDs with companion ownership |
| Story chapters / stage clears / objectives / rare-weapon rewards | Native reward routine found; per-stage external tables and dependencies remain unavailable. Campaign completion is kept separate from resource/stat/content unlock actions |
| Collections / biographies / music / movies | Related flag sections found, but flag-to-content dictionaries and prerequisite masks remain unqualified; no bulk setting of unknown bits |
| Lifetime kills / gold spending / rankings | Historical counters inspected, not treated as spendable resources or offered as Max actions |
| Interim battle data / resume / difficulty/options | Saved section retained byte-for-byte; exact resume/session dependencies and option enums are not qualified |
| Older PC revisions / other regions | Native migration revision list recovered; no genuine older-revision samples and verified per-revision field layouts. Current revision only |
| Actual game-load validation | Requires the game and deliberate loading of an edited copy; static inspection and reparse tests do not establish this |

## Samurai Warriors 5 — native PC castle saves

The new `samurai5_pc` adapter supports owner-dependent native `SAVEDATA00.BIN`
revision 39 saved at My Castle. It edits gold, stock EXP, shared spendable skill
points, stock weapon mastery, lumber, mineral and fabric. Development source
also edits already held skill-gem quantities from 1–20 at their original
type/rank, without acquiring an empty stack or learning a weapon skill; see the
[current expansion evidence](GAME_SPECIFIC_EXPANSION.md#samurai-warriors).
Native source proves
field widths, resource limits and current-checkpoint selection; historical
copies, spending counters, officer skill allocations, story/facilities and
both battle buffers remain intact. Searchable native-record inspection covers
weapons, officers, mounts, skill-gem quantities and progression classes.

Keep the original `steam_autocloud.vdf` beside source and destination copies.
The new complete genuine slot and its original owner context resolve the
previous key blocker. Earlier public saves without their own owner context
remain unusable; the adapter does not try another owner's key or legacy
fallbacks. Active battle/resume, trial and other slot/revision variants are
not accepted. The game executable was inspected statically and never run.

See [SW5 format and mechanics coverage](SAMURAI5_PC_FORMAT.md) for the complete
native stream/current-copy evidence, tests and exact remaining progression
blockers. Direct unchanged ciphertext reconstruction, surgical native edits,
backups, same-owner restore, malformed-input checks and Tk workflows are
covered. Edited game loading remains unperformed.

## Public research references and reuse

- [Apollo SW4 patch documentation](https://github.com/bucanero/apollo-patches/blob/master/PS3/NPUB31564.savepatch): published SW4 skill names and console cap/record clues. PC offsets were recovered independently; console offsets were not copied into the PC adapter.
- [save-decrypters SW4 checksum research](https://github.com/bucanero/save-decrypters/tree/master/sw4-checksum-fixer): historical console integrity reference, not proof of this PC container.
- [SW4-II community memory table](https://github.com/Hexorg/CheatEngineTables/blob/master/tables/shinkansen_samurai_warriors_4-ii_v1003_583.ct): corroborating stat ordering only; not executed, not imported as DX save support.
- [Steamless](https://github.com/atom0s/Steamless): consulted privately to understand static SteamStub decoding. No upstream source, tooling, stub data or game code is included or distributed.

The new adapter is an independent implementation using observed native facts
and existing repository safety/cipher helpers. No external project was pasted
wholesale, and no game binary, player save, account identifier or personal
research path is packaged.
