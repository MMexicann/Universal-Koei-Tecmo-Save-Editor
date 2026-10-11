# Gundam 2 PS3: native-input retry

This is an unregistered research result, not a supported editor. The previously
missing native-input gate is now resolved for original US BLUS30288 and EU
BLES00528 exports. Safely writable gameplay field dependencies remain blocked.

Four genuine console exports were acquired privately from GameFAQs:
[19026](https://gamefaqs.gamespot.com/xbox360/952638-dynasty-warriors-gundam-2/saves/19026),
[19005](https://gamefaqs.gamespot.com/xbox360/952638-dynasty-warriors-gundam-2/saves/19005),
[19932](https://gamefaqs.gamespot.com/xbox360/952638-dynasty-warriors-gundam-2/saves/19932)
and [19293](https://gamefaqs.gamespot.com/xbox360/952638-dynasty-warriors-gundam-2/saves/19293).
Three native `PARAM.SFO` companions identify BLUS30288 and one BLES00528.
Cross-platform listing URLs do not determine the contained export platform.
The complete protected files were privately decoded using their original PFD
context and the published secure-file key, without executing binaries. All
four decrypted `DATA.BIN` files have exactly `0xA4000` bytes.

Their leading revision DWORD is `0xD`; header DWORDs `+0x14` and `+0x18` are
`0x20` and `0x3D400`. Header words `+4` and `+0x1C` differ and remain unknown.
All four files independently match these observed big-endian byte-add words:

| Stored word | Half-open byte coverage | Qualification |
| --- | --- | --- |
| `+8` | `[0x20, 0x40000)` | Same exact endpoint and sum on four original exports |
| `+0xC` | `[0x3D400, 0xA1400)` | Same endpoint and sum on four original exports; starts at the header's observed second offset |
| `+0x10` | `[0x20, 0xA4000)` | Complete required writer explicitly published in the US/EU Apollo patches, independently matches all four files |

The complete original protected-file geometry is preserved in private research.
The two additional observed sums are useful evidence; native serializer proof
or independently controlled edit/load pairs should corroborate their exact
roles before a production writer relies on mathematical matches alone. The
third domain is explicitly defined by the title-specific public writer.

[US](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30288.savepatch)
and [EU](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLES00528.savepatch)
publish individually named Amuro, Char, Kamille and Judau Pilot Point/level
patches. Their Pilot Points are progression EXP, not a safely independent
spendable wallet. Blindly changing EXP or the raw level byte could desynchronize
stat growth and unlock/reward consequences. No unsupported currency control is
created from the misleading cheat title.

## What is still needed

- Exact complete native writer proof for the two additional integrity domains,
  or independently verified native edit/reimport/load controls.
- Coherent EXP thresholds, raw level encoding, stat growth and level-up
  consequences for pilot edits; the actual maximum pilot level is 50, while
  the public "Level 30" operation is only a cheat target.
- Alternatively, individually proven cosmetic gallery/music/movie flags or
  a genuine independent spendable inventory resource could qualify a useful
  editor without touching pilot progression. None was established in this
  source retry. Public GitHub repository/code searches found no complete
  original Gundam 2 save editor with such maps.
- Parts/lab/skills/license/friendship/mission ownership and prerequisite
  mappings remain unqualified. No native record stride or catalog is guessed.

The matching US/EU inputs are no longer the missing requirement; the blockers
are safe field meaning/dependencies and full integrity-writer proof. No player
file, signing metadata, account identifier or external source is distributed.
