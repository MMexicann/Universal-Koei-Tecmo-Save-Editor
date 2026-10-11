# Tecmo Super Bowl — NES battery save

The editor accepts a separate `.sav` copy of the native 8,192-byte battery SRAM
used by the original US 28-team Tecmo Super Bowl layout. A ROM or emulator state
is not a battery save. Close the emulator before exporting/importing battery
data so its in-memory copy cannot overwrite the edited file. If an emulator uses
`.srm` for the same raw 8 KiB format, rename a separate copy to `.sav` before
opening it and follow that emulator's battery-save import instructions afterward.

Raw battery SRAM cannot authenticate the accompanying ROM, its region, or its
roster. The card therefore identifies the **compatible 28-team SRAM format**,
and uses Team 01–28 and roster-position labels. ROM hacks that change record
geometry, player count or checksum routines are outside this profile.

## Native framing and integrity

The raw file maps NES addresses `$6000–$7FFF`, so subtract `$6000` from an SRAM
address to get a file offset. The native boot routine in `Bank31_fixed_bank.asm`
compares the seven-byte `AKIHIKO` marker at `$66B7` and a little-endian checksum
at `$66BE`. Its complete `CALCULATE_CHECKSUM` routine sums bytes in two regions,
adds `$3412` and retains the low 16 bits:

```text
(0x3412 + sum(raw[0x6C0:0xEFE]) + sum(raw[0x1002:0x1F72])) & 0xFFFF
```

Both ranges are half-open. The 260-byte `$6EFE–$7001` gap is deliberately
excluded. Checksum failure makes the game clear season SRAM and recreate
defaults, so damaged inputs are rejected rather than silently repaired.
`GET_SAVE_CHECKSUM` stores this result after native season-management writes;
the NES battery preserves the SRAM directly, with no encryption or additional
on-disk container/integrity wrapper. Transient buffers outside the checksum
ranges are preserved byte for byte by this editor.

The native `TEAM_STAT_SRAM_ADDR` pointer table contains 28 records, each 208
bytes. File record addresses are `0x7AE + team_index * 208`, plus 260 for indexes
9–27. Team 9 starts at `0xE2E`; Team 10 starts at `0x1002`; Team 28 starts at
`0x1EA2`. Do not flatten the gap into a continuous 28-record array.

## Mechanics and coverage checklist

| System | Implementation and native proof |
|---|---|
| Season team control | 28 choices at `0x69B + team_index`, low two bits only. MAN/manual, COA/coach, COM/computer and SKP/skip are the native menu's four choices. Upper six bits remain intact. Control is outside season checksum coverage, as in the game's own writer. |
| Player condition | 30 positions per team at record `+0xC8`, four two-bit states per byte, most significant pair first. Bad, Average, Good and Excellent match `GET_PLAYER_COND_INJURY_STATUS` and native condition constants. Injured offensive skill players are inspection only: native weekly updates force them to Average. Their opened condition is preserved, including unusual states. The final byte's two unused player slots remain intact. Max applies only to healthy player condition. |
| Playbook | Eight slots at record `+0xBD`, high nibble then low nibble. Four run slots and four pass slots each have eight choices. Native loader computes `slot * 8 + choice`; native writer masks each choice to `0..7`. Selectors `8..15` are inspection only and remain unchanged, while a valid adjacent nibble can still be edited. Max and numeric adjustment do not invent a preferred play. |
| Injury state | Separate three packed bytes at record `+0xC5`, preserved and searchable as raw data. Condition modifies temporary ability adjustments and does not heal an injury. Injury recovery behavior and deliberate injury changes are outside the writable scope. |
| Starter lineup | Separate four packed bytes at record `+0xC1`, preserved and inspected. Native injury substitution and duplicate-player restrictions need a complete edit-dependency model before lineup changes can be exposed. |
| Season standings and statistics | Existing wins/losses/ties are inspected at `+0xB2`. All outcomes, individual/team statistics, schedule, week, playoffs and Pro Bowl choices remain unchanged; consistency across schedule/results and leaders is not established for arbitrary edits. |
| Roster names, abilities and player skills | Stored in the ROM rather than battery SRAM; not save-backed editor fields. No ROM editing, roster catalog or extracted assets are bundled. |

An ordinary file exposes **1,092 fields**: 28 controls, 840 player conditions and
224 playbook choices. Files with injuries or unusual playbook selectors expose
fewer writable fields. Searchable fields, choice menus, validated bulk condition actions,
Undo, Review Changes, automatic backups, restore and safe Save As use the shared
workspace. Changes touch only admitted packed bits and, when needed, the two
native checksum bytes. Unknown data is never normalized.

## Source provenance

These are research references, not bundled dependencies. Their implementation,
game assets, roster data, ROMs and player snapshots are not redistributed.
No game or external editor binary was executed. The parser is independently
written from factual native format/routine observations.

- [bruddog/Tecmo_Super_Bowl_NES_Disassembly](https://github.com/bruddog/Tecmo_Super_Bowl_NES_Disassembly/tree/f3bae0e1913ba532a5ace158d86d905ecf787008),
  commit `f3bae0e1913ba532a5ace158d86d905ecf787008`, no declared licence.
  `Bank31_fixed_bank.asm` supplies the native boot check, complete checksum,
  condition unpacker and team pointer table. `Bank17_18_main_game_loop.asm`
  supplies complete playbook packing/unpacking and SRAM transfers;
  `Bank26_misc.asm` supplies default/condition/team-control writers;
  `Bank16_menu_screens_slidebar.asm` supplies control choice order.
  `constants_variables/{sram_variables,stat_indexes,roster_ids,constants}.asm`
  corroborate geometry, roster positions and condition states. Its README states
  the disassembly rebuilds the original US revision byte for byte; no ROM was
  obtained or built for this work.
- [taddeimania/cstatparser](https://github.com/taddeimania/cstatparser/tree/cd2eb05e00c37a6d0b73854cadda685a2b20ef3d),
  commit `cd2eb05e00c37a6d0b73854cadda685a2b20ef3d`, no declared licence.
  Publicly bundled `State` and `1.nst` Nestopia snapshots supplied two genuine
  8 KiB WRAM copies, extracted privately from their uncompressed `WRM` chunks.
  Both match the native marker and complete checksum (`0xCB90` and `0xCB58`).
  Their original files and extracted SRAM are absent from the repository.
- [Digitoxin1/NesToy database](https://github.com/Digitoxin1/NesToy/blob/50c41266142a398d0cbe8ebc5855c0b02753d4c0/nesdbase.dat)
  and [hukkax/CaniNES title metadata](https://github.com/hukkax/CaniNES/blob/d2c34f2bc2fa499c6ed85c93b1d662d502a00067/src/res/titles.txt)
  independently identify `State`'s Nestopia NFO PRG CRC `8E5C2818` as original
  US Tecmo Super Bowl (full-ROM CRC `179A0D57`). The other snapshot's PRG CRC
  `D98FBFE1` is unidentified; it qualifies only as a compatible SRAM fixture.
  Only public metadata was inspected; no ROM download was used for identification.

## Validation

`tests/test_tecmo_super_bowl_nes.py` uses explicitly non-playable procedural SRAM
for corruption at both checksum boundaries, gap coverage, all packed field edits,
unknown selector preservation, unusual control bits, unused condition slots,
foreign formats, malformed IDs, immutable snapshots, bounds, Max scope,
backups/restore, changed-source and post-backup race protection. Tk tests in
both themes exercise Open, Find fields, choice presentation, staged Apply,
Review Changes, Undo and Save As with native readback.

Optional `TSB_NES_NATIVE_COPIES` is an OS-path-separator list of private genuine
SRAM copies. Both acquired copies passed byte-exact no-op, checksum and surgical
condition/playbook/control edits with reparsed output. **Edited saves were not
loaded or re-saved in the game.** Public snapshot qualification and native
read/write routine proof are distinct from an actual in-game acceptance test.
