# Tenshouki with Power-Up Kit — original Japanese Windows saves

The `nobu6_pk_pc` adapter edits existing military-district Gold, Rice, Horses
and Firearms in the original Japanese Windows Power-Up Kit `.n6p` format.
All eight slots remain separate. Searchable inspectors show existing generals,
castles, clans, treasures, military districts and save-slot previews.
This is not the original DOS game, a console port, or the HD remake.

## Complete writer and native identity

Format facts were independently read from the published
[Tenshouki save editor source](https://github.com/tenshoukijp/nobu6_tool_savedataeditor/tree/69455e9f566874d8440a572041a61cc0c52e72fa),
pinned to `69455e9f566874d8440a572041a61cc0c52e72fa`:

- `SaveDataEditorView.h` explicitly selects Windows Power-Up Kit
  `savedat*.n6p`, and its Save/Save As handlers call the native data writer.
- `Data.h`, `CDatawrapp::Open`, tests the first 11 bytes against
  `1995.08.16` including its NUL terminator. `DATA.txt` describes the complete
  844,623-byte eight-slot container.
- The active `CData::Save` calls `SaveFile(fn, m_lp, m_fs)`;
  `SaveFile` calls `CreateFile`, then `WriteFile(hf, lp, dwSize, ...)` on the
  complete opened buffer, then `CloseHandle`. There is no intervening cipher,
  compression, checksum update, or reconstructed output. This complete save
  path, rather than an isolated patch, establishes the raw-write contract.
- `SaveDataStruct.h` defines packed one-byte alignment. `Data.h` adds district
  resource columns explicitly labelled 金, 米, 騎馬 and 鉄砲, reads their four
  word members, and writes those same members in its grid-to-save path.

No declared upstream reuse licence was found. This adapter is an original
implementation of independently observed format facts. It imports no upstream
implementation, name catalogue, artwork or game assets. Unlike the upstream
viewer, opening this adapter never normalizes district position flags.

## Exact admitted layout

All offsets and words below are little endian. The adapter requires the exact
file size, magic, occupied-slot flags and admitted record references before
offering edits; it does not select a format from the filename alone.

| Component | Offset / stride | Count and qualification |
| --- | --- | --- |
| Magic | 0 | `1995.08.16` followed by NUL |
| Slot occupied flags | 11, stride 2 | Eight words, each 0 or 1 |
| Slot previews | `0x1F`, stride 158 | Eight; occupied season 0–3, scenario 0–5, difficulty 0–4 |
| Gameplay slots | `0x50F`, stride 105,416 | Eight; occupied gameplay season 0–3 |
| Generals | Slot +2,786, stride 47 | 532 |
| General names | Slot +27,790, stride 18 | 532 |
| Castles | Slot +37,366, stride 33 | 214 |
| Military districts | Slot +46,140, stride 21 | 214 |
| Clans | Slot +`0xC5CA`, stride 22 | 72 |
| Treasures | Slot +`0xD334`, stride 19 | 120 |

The preview date is stored separately from the gameplay date and is not forced
to match it. Unused slots remain entirely opaque and are preserved byte for
byte. Existing native Shift-JIS names are shown without replacing unknown
encodings; no external catalogue is needed.

A district with residence `0xFFFF` is unused and never editable. Other admitted
districts must reference castle 1–214, general 1–532 and clan 1–72; the clan
must itself have a valid general reference. Their Gold, Rice, Horses and Firearms
are unsigned 16-bit words at record +11, +13, +15 and +17 respectively.
They are district stocks, not four global player balances or deployed troop
counts.

Only an existing positive stock is writable, from zero to its opened value.
Zero stock cannot be created; automatic Max is disabled. The source proves
storage widths and identities but does not prove natural stock ceilings, so
65,535 is never presented as a gameplay maximum. Unusual original values remain
intact and assigning the original value unstages a reduction.

## Mechanics and coverage

| System | Implemented coverage or precise remaining blocker |
| --- | --- |
| District Gold, Rice, Horses, Firearms | Individual existing-stock reductions and validated selected-field bulk edits; stock creation and natural Max need gameplay-cap evidence |
| District action points and offices | Preserved; action regeneration/turn dependencies and legitimate office assignments not qualified |
| Generals | Native names, talents, proficiencies, loyalty and state/clan inspection; talent growth, experience, promotion, merits and troop changes need gameplay limits and dependency proof |
| Castles | Native names, fortification, rice yield, commerce, population and loyalty inspection; development maxima, population/recruitment relationships and daily recalculation remain unqualified |
| Clans and diplomacy | Existing leaders, court standing, hostile/friendly references inspection; ownership, succession, retirement, diplomacy and linked-list consistency remain read only |
| Treasures | Existing name, type, owner, stored bonus and state inspection; transfer requires inventory/owner and effect dependencies |
| Campaign/story progression | Slot preview inspection only; scenario, dates, events, victory and unlock flags remain separate from resource editing |
| Other platforms/HD remake | Different title/revision formats; no shared offsets or support claimed |

## Validation and remaining inputs

`published_format=True`; `sample_verified=False`, `editing_verified=False`,
and `game_load_verified=False` deliberately remain explicit in the adapter.
Nine focused tests pass, including actual Tk Open, stage, Undo, Review Changes,
Save As and backup restore. These use **procedural source-fact buffers**, not
genuine player saves. They prove unchanged roundtrips, every writable field's
two-byte surgical edit, unknown/unused-slot preservation, malformed/foreign
input rejection, immutable snapshots, source-change races, backup validation,
link-alias rejection and live-game-folder rejection.

A freely shared genuine occupied original Japanese Windows PK
`SAVEDAT.n6p` is still required for independent native qualification, followed
by loading and re-saving an edited copy in the actual game. No matching fixture
was present in the source repositories or linked editor archives inspected.
The original game/editor binaries were not executed, and no private save is
included in source, tests or release assets.

Open a separate `.n6p` copy outside the game's executable folder. Save As creates
a new file, automatically backs up the immutable opened copy, and revalidates
the edited native structure. Restore validates the same bounded bytes it writes.
