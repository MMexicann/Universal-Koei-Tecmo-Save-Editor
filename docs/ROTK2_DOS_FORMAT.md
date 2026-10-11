# Romance of the Three Kingdoms II — Chinese DOS

This adapter targets the original Chinese DOS raw layout with exactly 30,752
bytes, the `1990.02.19` signature and 43-byte officer records. It does not target
the Korean 36-byte-officer layout, console editions, scenario assets or the
30,584-byte output produced by a later Python game recreation.

The GUI opens **extensionless copies**, matching the published `S0`–`S6`
reference filenames. The original standalone editor accepts an arbitrary file
name rather than establishing a required `.sav` suffix. Direct backend tooling
also accepts `.sav` and `.dat`; those aliases are not advertised as GUI inputs.
Keep copies outside the live DOS game folder. Save As creates a new file and
preserves the opened copy, with backup, Undo, Review Changes and restoration.

## Evidence and integrity

The original standalone [JuQiang/RoTK2Editor_Python](https://github.com/JuQiang/RoTK2Editor_Python)
identifies itself as an editor for the original KOEI DOS game. Its
[Main.py](https://github.com/JuQiang/RoTK2Editor_Python/blob/master/Main.py)
reads 30,752 bytes into its save buffer and writes that entire buffer back.
The complete writer applies no checksum, encryption, compression or output
reconstruction. Its
[Province.py](https://github.com/JuQiang/RoTK2Editor_Python/blob/master/Entity/Province.py)
and Officer definitions establish the record geometry and currency fields.
This implementation independently expresses those format facts and preserves
the complete input, including the opaque tail. No implementation, province/name
catalog, artwork or game asset has been copied. The reference repository has no
explicit reuse licence, so it is a factual format reference only.

[JuQiang/Rotk2_Python](https://github.com/JuQiang/Rotk2_Python) publishes seven
30,752-byte files named `S0` through `S6`. All match this layout and pass the
header, pointer, ownership and coordinate checks. `S0` and `S2`–`S6` align with
scenario starting years; they are treated as initialization/reference snapshots.
`S1` contains different ruler/state data, but its creation history and whether
it is a player-authored saved campaign are not independently documented. **None
of these files counts as an independently shared genuine player save.** They
remain private test inputs outside the repository and release downloads.

The game recreation's Command19 save code describes a different 30,584-byte
reconstruction. That writer is not the integrity proof for this adapter, and its
output is rejected rather than padded or repaired. A browser editor example in
[reganlu007/reganlu007.github.io](https://github.com/reganlu007/reganlu007.github.io/tree/master/editor/dos/san2)
has a 79,386-byte embedded buffer matching scenario-asset geometry; it is not
accepted as a native player save. Likewise,
[brokenpc00/RoTK2_Editor_React](https://github.com/brokenpc00/RoTK2_Editor_React)
uses the different Korean officer layout and cannot qualify this Chinese one.

Qualification is therefore **published-format support**:
`published_format=True`, `sample_verified=False`, `editing_verified=False`,
`game_load_verified=False`. No game executable has been run and no edited file
has been loaded into the original game.

## Layout and write boundaries

| Record | Exact framing |
| --- | --- |
| Header | ASCII `1990.02.19`; year LE16 at 12, zero-based month at 14, ruler count at 15 |
| Officers | 255 records at offset 32, stride 43; LE16 next-record pointer at +0 |
| Provinces | 41 records at `0x2D8C`, stride 35 |
| Province links | LE16 next-province at +0; officer-chain heads at +2, +4 and +6 |
| Owned resources | Gold LE16 at +8, rice LE32 at +10 |
| Other province facts | Population LE16 at +14, displayed as people by multiplying by 100; owner +16, invasion owner +17; grid X/Y at +32/+33, region at +34 |
| Native pointers | Zero is null; nonzero record pointers equal file offsets plus `0x38` |

The decoder rejects wrong size/signature, malformed calendar/ruler framing,
nonaligned or out-of-array pointers, link cycles, conflicting ownership in
linked province chains, invalid owner IDs and invalid/duplicate coordinates.
Unknown bytes and unusual existing currency values are preserved. Province
record numbers shown in the GUI are table positions, not copied named province
IDs. Unclaimed provinces are inspection only.

## Mechanics coverage checklist

| System | Implemented scope or precise blocker |
| --- | --- |
| Province gold and rice | Individually reduce existing balances in owned provinces, including zero. Values cannot exceed the opened balance. Field meaning and raw-write path are source-correlated. |
| Natural currency ceilings and Max | Unproved. The external editor's cheat targets do not establish legitimate gameplay limits. Max is disabled and no increase is offered. |
| Province search and inspection | All 41 records, owner IDs, balances, population in people and grid coordinates. Ownership, unclaimed records and population are read only. |
| Officer stats, loyalty, troops, development and morale | Source offsets exist, but no independently qualified natural limits, campaign dependencies or controlled gameplay pairs. No writes. |
| Governors, officer transfers, ruler/province ownership | Pointer meaning is used for structural validation only. No membership, reward or conquest actions. |
| Calendar, scenarios, story/conquest and victory | No writes; kept separate from resource editing. |
| Names and province maps | No restricted name/map catalog imported. Numeric table positions remain explicit. |

## Checks and remaining inputs

`tests/test_rotk2_dos.py` checks generated, deliberately nonplayable records for
byte-exact roundtrip; every allowed gold/rice edit; preserved unknown/tail bytes;
high existing balances; invalid bounds and types; forged snapshots; malformed
framing/pointers/chains; exclusion of unclaimed records and Max; backups and
restoration; refusing changed source files before backup and again after the
backup immediately before atomic Save As; and existing-destination protection.
The actual Tk workflow opens, edits, undoes, reviews, changes theme, saves and
restores an extensionless copied file. Optional `ROTK2_DOS_REFERENCE_DIR` runs
all seven upstream snapshots through no-op and surgical resource checks and
uses `S1` for that Tk workflow. Source-reference checks remain distinct from
genuine player-save and game-load qualification.

To upgrade qualification, obtain an independently shared **original Chinese
DOS saved campaign** of this exact 30,752-byte layout, with its edition and
creation history. Controlled before/after spending, taxation and rice-change
pairs would corroborate resource semantics and dependencies. Original-game
edited-load checks are still needed. Additional mechanics need controlled pairs
and legitimate limits before receiving write controls. No binaries or personal
player data should be committed.
