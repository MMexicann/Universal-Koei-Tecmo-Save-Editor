# Dynasty Warriors: Gundam Reborn — PS3 EU/Japan

The native revision-2 decrypted gameplay writer supports NPEB02060 and NPJB00533
`DATA.BIN` copies beside their original `PARAM.SFO`. It implements three
spendable-resource reductions: money, Amuro Ray's Team Points and Kamille
Bidan's Team Points. Its shared GUI includes searchable read-only pilot and
material-region inspection, staged Undo/Review, backups, restore and safe Save
As. Console decryption/reimport/signing remains an external Apollo workflow;
this adapter neither consumes owner identifiers nor rebuilds `PARAM.PFD`.

## Source and native qualification

Field/checksum facts were independently implemented from the public Apollo
patches for [NPUB31531](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPUB31531.savepatch),
[NPEB02060](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPEB02060.savepatch)
and [NPJB00533](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPJB00533.savepatch).
These source files are GPL-licensed; no patch interpreter, restricted code,
assets or catalogs are included in this implementation.

Three independently shared native PS3 export archives were acquired from
[GameFAQs save 23844](https://gamefaqs.gamespot.com/ps3/730637-dynasty-warriors-gundam-reborn/saves/23844),
[23624](https://gamefaqs.gamespot.com/ps3/730637-dynasty-warriors-gundam-reborn/saves/23624)
and [23620](https://gamefaqs.gamespot.com/ps3/730637-dynasty-warriors-gundam-reborn/saves/23620).
The first is EU NPEB02060 despite its listing under the North America section;
the two latter exports are Japanese NPJB00533. These are genuine console
exports containing modified/completed player progression. They do not prove
clean earned-state boundaries, edited-game loading, or a natural resource cap.
Original exports, signing metadata and decrypted player data remain private.

All three decrypted files independently have exactly `0xFD400` bytes. Their
four leading big-endian DWORDs are `(0, 2, 0x5F938, ADD)`. The exact native
checksum is a byte sum over the half-open range `[0x10, 0x5F948)`, stored at
`0xC`; the header's content size agrees with that range. The published required
checksum writer explicitly covers this whole content range. Each acquired
native checksum validates without repair. No-op serialization returns every
original byte unchanged. Changes recompute that checksum and revalidate the
result. The remaining tail `[0x5F948, 0xFD400)` is opaque, preserved byte for
byte, and is outside this checksum's coverage; no extra tail-checksum claim is
made. Foreign revisions, sizes, regions, metadata and failed content checksums
are rejected before fields become available.

## Qualified fields and mechanics

| System | Native fact | Implemented behavior |
| --- | --- | --- |
| Spendable money | Big-endian DWORD `0x5AD44`, individually labeled by title-specific patches | Manual reduction `0..opened`; original higher/unusual values remain restorable |
| Lifetime earned money | Separate big-endian DWORD `0x57F90` | Read-only; never synchronized to wallet edits |
| Amuro Team Points | Big-endian DWORD `0x23FD6` | Reduction on an existing progressed named pilot |
| Kamille Team Points | Big-endian DWORD `0x240F6` | Reduction on an existing progressed named pilot |
| Pilot EXP / raw level | Amuro `0x23FBE` / byte `0x23FBC`; Kamille `0x240DE` / byte `0x240DC` | Searchable read-only; no EXP/level desynchronization |
| Pilot stat words | Individually published offsets `+6,+8,+10` relative to these two records | Searchable raw-word inspection; no guessed stat identity or derived-stat writes |
| Material-region words | Published broad patch starts `0x5A544` and writes ten BE16 values | All ten remain read-only; type names and exact ownership boundary still need proof |

The [gameplay guide](https://gamefaqs.gamespot.com/ps3/730637-dynasty-warriors-gundam-reborn/faqs/70035)
explains that Team Points buy individual pilot skills, normally costing
100–500 points with additional levels costing more. This is distinct from
Pilot Points/EXP and from a suit's upgrade-plan stats. Up to six skills can be
equipped. Resource reductions leave learned skills and equipped references
unchanged. Both named Team Point fields require a positive existing EXP value,
a raw level byte from 0 through 49, and positive opened Team Points; foreign or
unprogressed records are not exposed. Assigning the opened value unstages an
edit. No field uses automatic Max: published cheat amounts are not proven
natural gameplay maxima.

## Coverage checklist and exact remaining blockers

- [x] Spendable money, both individually named Team Point pools; separate histories.
- [x] Native whole-content integrity, strict revision/title identity, opaque-tail preservation.
- [x] Searchable pilot/EXP/raw-stat and ten material-region word inspection.
- [x] Surgical edits on every available control in all three genuine files.
- [x] Procedural boundaries/corruption/forged snapshots, stage/unstage, no-Max behavior.
- [x] Changed-source and full bounded original-SFO digest guards before backups and final atomic writes.
- [x] Original-copy preservation, automatic backups, save-hash/context-digest-bound restore and actual Tk workflow.
- [ ] Material quantity writes: source broad patch claims ten words, but genuine perfect
      JP exports contain eight 999 values followed by unrelated-looking 51 and 5659;
      EU has eight 999 values followed by 51 and 0. Repetition is insufficient to
      identify eight material types. Need native writer/type boundaries or a labeled
      single-material before/after pair. No quantity writer is extrapolated.
- [ ] Other pilots: title-specific broad patches disagree on pilot count and include
      overlapping Team Point strides. Need individually proven record identities
      and ownership for the remaining pilot pools.
- [ ] EXP/levels/base stats: need coherent growth tables and legitimate level-up
      consequences. The guide distinguishes growth from skill purchases.
- [ ] Learned skills/equipment: exact learned-bit, prerequisite and six-reference
      identities are missing. Team Point edits never purchase skills implicitly.
- [ ] Plans/weapon systems/fusion: source broad plan cheats alter several coupled
      fields. Need plan ownership, rank, customization-slot, combination-use and
      material-consumption mappings before meaningful safe edits. Plans range
      from E through A to S; combining and upgrading consume limited slots.
- [ ] Pilot/suit unlocks, mission results, medals, partners and gallery: reward,
      prerequisite and stored-versus-derived identities are not qualified.
- [ ] US NPUB31531, retail EU BLES02057, retail Japanese BLJM61140: useful source
      maps exist but no native export for these identities was qualified here.
- [ ] Edited-save game-load/re-save validation has not been performed.

Run the focused module under a display. Set `GUNDAM_REBORN_PS3_COPIES` privately
to a directory containing the three separately extracted GameFAQs folders for
its genuine-file checks; no fixture is distributed in source or releases.
