# Dynasty Warriors 7: Xtreme Legends — original US/EU PS3 editor

The `dw7xl_ps3` profile now has a standalone scalar editor as well as its
existing [one-way conversion preview to PC Definitive Edition](DW7XL_CONVERSION.md).
It supports **original US BLUS30873 and European BLES01496** exports. Base DW7,
Empires, Japanese/Asian XL, encrypted exports and other platforms are separate
formats and are rejected.

## Opening and saving

Open a separate, PFD-decrypted `APP.BIN` copy with its **complete original
`PARAM.SFO` beside it**, outside live game/cloud directories. The qualified
plaintext is exactly **470,303 bytes**, starting with big-endian revision
`0x11080200`. Original encrypted files have 470,304 bytes; their AES padding is
not plaintext gameplay data. Do not trim or rename an encrypted file to make it
match this profile.

Save As writes a new decrypted `.bin` copy and creates a paired-context backup.
Keep the same complete original `PARAM.SFO` beside the destination. Opening,
backup, saving, actual destination read-back and restore bind that complete
metadata snapshot, including opaque bytes. Changed source/context, existing
outputs and foreign game profiles are rejected. Backups remain available after
a later failure; a failed save must not be imported even if a new file exists.

The app does **not** decrypt PFD files, rebuild PFD authentication, reassign an
account or sign a console save. Use an appropriate external console-save tool
for decryption and reimport/resigning. No new internal checksum is invented or
silently repaired. The profile declares external integrity; format and typed
value checks do not authenticate console ownership or replace PFD validation.

## Editable scope

| Control | Native encoding and normal bounds | Preserved relationships |
| --- | --- | --- |
| Spendable Gold | Big-endian u32 at `0xC7C`; 0–999,999 | Earnings/history, rewards and all other system values |
| 65 playable officers' stored health | Big-endian short, record +`0x06`; 0–1,000 | Identity, EXP/level, learned skills and equipment |
| Stored attack and defense | Record +`0x08` / +`0x0A`; 1–1,400 | Other stored/derived values and progression |
| Stored power and speed | Record +`0x0C` / +`0x0E`; 0–100 | Purchased skill flags and growth history |
| Unspent skill points | Record +`0x1A`; 0–9,999 | Skill purchases, prerequisites and rewards |
| Active equipped weapon | Record +`0x16`; first or second already equipped reference | Selected reference must identify an existing owned weapon; no inventory item is granted |
| Existing unlearned seal meter | Weapon record +`0x06`; decrease from the opened positive value | Only flags exactly `1` and opened meters 1–1,000 qualify; learned bits, ownership, seal-state enums and rewards remain unchanged |

Officer records start at `0x2039` with stride `0x80`. The file stores 92
physical officer records; the editor exposes the 65 qualified playable slots.
Names are not guessed from physical order. Weapon storage begins at `0x4E39`,
with 1,738 physical records of 20 bytes each.

Max uses the native validated limits for Gold and officer numeric controls.
It excludes equipped choices and seal meters, preserves higher/unusual opened
values, and never grants a learned skill or seal. Assigning the exact opened
value removes that staged change, including an unusual original value.

Optional acknowledged experimental editing uses the actual native encoding:
Gold permits an unsigned 32-bit value; officer numeric getters sign-extend
16-bit shorts, so their positive encoding ceiling is **32,767**. These are
encoding limits, not natural maxima or a promise of game acceptance. The
experimental policy never bypasses equipped-weapon ownership, seal-meter
decrease guards, format/context checks or the suspended-battle guard.

A nonzero suspended-battle flag at `0xDD1F` keeps the copy readable for
inspection but disables scalar edits. Finish that battle in the original game
and make a new export first. This avoids changing stored officer/equipment
state while the save carries a separate live battle object.

Searchable inspectors show both equipped references, active slot, guardian ID,
purchased-skill bits, and every physical weapon's ownership/flags/seal meter.
Weapon identities, intrinsic attack/element parameters, guardian acquisition,
NPC records, story completion, reward claims and unknown bytes are not editable
in this PS3 profile.

## Independent native proof

The original US and EU official PS3 **v01.01** update executables were inspected
statically, without executing game code. Their relevant getter/setter and
validator instruction ranges are byte-identical after the EU address relocation
of `-0xC`; no Windows-only limit was transplanted to PS3.

US native setters independently establish health at `0x28612C` (0–1,000),
attack at `0x28614C` and defense at `0x286170` (1–1,400), power at `0x286194`
and speed at `0x2861B4` (0–100), and skill points at `0x28654C` (0–9,999).
Their matching getters read the individually typed record members. The
original officer validator at `0x2866C4` separately checks these values.
The Gold getter at `0x28EA54` reads system +`0xC78`, which follows the four-byte
revision and therefore corresponds to payload `0xC7C`; its setter and system
validator at `0x28EE10` enforce 999,999. These setters change the selected native
member directly, without a skill-purchase, story or reward transaction.
Existing equipment ownership and negative seal-meter adjustment accessors
corroborate the protected choices/decrease-only scope.

Public native sources include the
[US/EU GameFAQs save catalogue](https://gamefaqs.gamespot.com/ps3/635632-dynasty-warriors-7-xtreme-legends/saves).
The complete original contexts, source archives, decrypted gameplay, game
executables and private analysis stay outside the repository and release.
No third-party game/editor executable was run or external implementation copied.

## Validation and remaining limits

Two original regional PS3 export contexts were qualified. Their decrypted
`APP.BIN` gameplay is **one identical gameplay state (advertised as 100% complete)**, so they are not two
independent progression histories. Both unchanged files roundtrip exactly.
For each context, a private exhaustive audit exercised **456 exposed controls**,
**499 surgical single-field assignments** and **413 exact no-op assignments**;
all unrelated bytes and both original source/context copies were preserved.
The shared copied-save self-test also passed for both contexts, including Max,
actual saved-value read-back, backups and restore.

The public procedural tests exercise full typed bounds, signed experimental
limits, equipped-reference/ownership rejection, qualified unlearned-meter
selection, pending-map validation, Max/Undo, surgical byte preservation,
suspended-battle handling, stale/foreign context, late context races, and the
actual Tk open/search/apply/review/Undo/Max/inspection/Save As workflow.
Procedural fixtures are generated test data, not playable native saves.

```text
python -m unittest tests.test_dw7xl_ps3_editor tests.test_dw7xl_ps3_profile tests.test_dw7xl_conversion -v
```

Set `DW7XL_PS3_SAVE_COPIES` to an OS-path-separated list of private decrypted
`APP.BIN` copies with their original `PARAM.SFO` to enable both regional native
tests. Conversion native tests additionally need `DW7XL_PC_SAVE_COPIES`.
Without the private inputs those tests skip; they do not silently generate
native evidence.

**Edited PS3 game loading/re-saving and destination PC game loading remain
unverified.** Static native proof, successful copied-file workflows and the
conversion preview do not establish that every player's exact 100% completion
or entitlement state will transfer or be accepted in-game.
