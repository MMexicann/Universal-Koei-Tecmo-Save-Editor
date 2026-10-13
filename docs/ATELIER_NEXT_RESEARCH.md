# Atelier and other additional-editor leads

This follow-up separates qualified saves from similarly named games, system
files, assets, trainer advertisements and generated codec fixtures. Third-party
implementations were read for format facts; restricted or unlicensed code and
catalog dumps were not copied. Public player copies remain private. No downloaded
game or third-party editor executable was run.

## Implemented, separately qualified profiles

- [Atelier Ayesha PS3](AYESHA_PS3_FORMAT.md): three public US/Japanese decrypted
  exports independently establish framing, the Cole field, two distinct memory
  words and inventory arrays. Cole edits and conservative existing stack
  reductions preserve native float quality, properties, effects and unknown
  bytes. Other regions and PC/DX are separate unqualified profiles. PS3 PFD
  reimport/signing and edited game loading have not been performed here.
- [Persona 5 Strikers PC](P5STRIKERS_PC_FORMAT.md): two complete public native
  PC exports establish framing, account-seeded stream preservation and the
  plaintext additive checksum. Occupied-slot resources and existing named
  ordinary consumable/ingredient quantities are manually editable; character
  growth and held Persona IDs are inspected separately. No Switch/PS4
  conversion, Persona creation, skill replacement or story action is provided.

## Sophie 2: preserve the existing bounded features

The existing Steam PC 1.08 tagged reader/writer is grounded in the MIT-licensed
[Tartarshia/Sophie2SaveEditor](https://github.com/Tartarshia/Sophie2SaveEditor)
at `93d807072a852c73799394af4d32fb164841cd3e`. Its resource ownership and runtime
recalculation assumptions must not be extended to another Atelier game merely
because it is made by Gust.

Current inventory inspection and use refill keep each record's opened positive
capacity. Quality edits and Sophie/Plachta alchemy EXP remain separate from
combat growth, alchemy level and recipes. Higher or unusual originals are
preserved. The source's mixed-gem value and Plachta's stored level are distinct
inspection records; their names do not establish safe write dependencies.

The upstream release explicitly excludes user save data, backups and external
Cheat Engine tables. The expected item/trait/effect dropdown table is not in the
repository. Searches of GitHub, freely shared-save pages, Steam discussions,
Reddit, guides and PS4 cheat references did not supply a qualified native Steam
1.08 player file in this pass. Original Sophie/Sophie DX downloads and PS4
cheats are not Sophie 2 PC controls.

Supply a separate original Steam 1.08 `data.dat` copy, unchanged save/re-save
control, build/language and one controlled use/refill, synthesis, equipment,
alchemy EXP or recipe purchase pair. Trait/effect applicability and item-kind
rules need a native catalog and controlled records. Combat levels/EXP/AP/skills,
alchemy recipes/catalysts/essences, currency/gems, bonds/quests/exploration,
collections and story need their own thresholds, ownership and reward rules.
See the [existing coverage checklist](SOPHIE2_COVERAGE.md).

## Arland titles and later Atelier games

| Candidate and factual source | Result and precise missing input |
| --- | --- |
| Totori DX PC: [jrpx/AtelierTotoriColeCheat](https://github.com/jrpx/AtelierTotoriColeCheat), Apache-2.0 | The published Cole bytes alone do not establish complete framing, width or integrity. The publicly advertised Totori archive was downloaded again and still contained app **936160 Rorona** `SYSDATA`, not app **936180 Totori** gameplay. It is deliberately rejected. Need actual Totori gameplay slot plus matching system file, build/language and a purchase/sale control. [Detailed checklist](TOTORI_PC_RESEARCH.md). |
| Arland DX runtime serialization: [nicoverbruggen/atelier-arland-fixes](https://github.com/nicoverbruggen/atelier-arland-fixes), MIT | Runtime item/equipment record facts are useful, but do not establish each game's disk framing or encryption. Need title-labelled native gameplay files and native loader/writer or controlled pairs before inventory/synthesis writes. |
| Meruru date transfer: [jrpx/Atelier-Meruru-Date-Transfer-Tool](https://github.com/jrpx/Atelier-Meruru-Date-Transfer-Tool), CC0-1.0, `c75f8d3457379677c1e84ff87232f85918ee6985` | The tool transfers opaque date bytes between files. Its author documents inconsistent years, income, quests and Hom timers after rewinds. This is a dependency blocker, not a safe calendar writer. Need native date encoding/integrity and event/timer transition rules; resource/inventory support could proceed independently once a genuine profile is qualified. |
| Rorona/Meruru DX PC | 27 Rorona and 17 Meruru gameplay snapshots now qualify bounded read-only chunk inspection. Published Rorona PLUS money/item leads partially match but later offsets differ. Native integrity and safe field dependencies remain missing before writes. [Arland evidence](ARLAND_DX_RESEARCH.md). |
| Original Sophie and Ryza 2 PC | Implemented separate qualified profiles: [Sophie resources/quality](SOPHIE_PC_FORMAT.md) and [Ryza 2 base-cap quality](RYZA_FORMATS.md). Genuine-file and GUI tests pass; actual edited game loading is untested. |
| Original Firis PC, original Ryza PC and Second Light PC | Implemented separate bounded profiles: [Firis Cole/quality reductions](FIRIS_PC_FORMAT.md), [Ryza existing quality reductions](RYZA_PC_FORMAT.md) and [Second Light container quantity reductions](BRSL_PC_FORMAT.md). Native copied-save writer checks pass; edited game loading is untested. Ryza/Second Light retain specifically matched terminal bytes opaquely without padding or repair. |
| Original Ryza 3, Sophie/Firis DX, Dusk DX/Nelke and original Blue Reflection | Native research leads retain title-specific codec/integrity or gameplay mapping blockers. See [Ryza](RYZA_FORMATS.md), [Sophie](SOPHIE_PC_FORMAT.md), [Dusk](DUSK_DX_RESEARCH.md) and [Blue Reflection](BLUE_REFLECTION_RESEARCH.md); system-only files are excluded. |

## Other Koei-associated candidates considered

| Lead | Qualification or blocker |
| --- | --- |
| Fatal Frame II: Crimson Butterfly Remake in [Katana](https://github.com/mi5hmash/KatanaSaveDataResigner), MIT | The inspected title class at source snapshot `4c90a2b388438cb27a9752e6eab7333257de215f` inherits Wo Long's container with JSON offset `0x110`, data checksum at `0x50` and header checksum at `0x70`. Its bundled fixtures are explicitly **dummy**, not genuine players. They are not distributed as native evidence. Complete independently shared system/gameplay files now qualify both native checksums and title-specific schema. The [implemented adapter](FATAL_FRAME2_REMAKE_FORMAT.md) permits only shared system Photo Point reductions; gameplay items/camera/collections are inspected and all binary photo bytes preserved. Actual edited game loading is untested. |
| Older Fatal Frame, Attack on Titan 1/2, Dead or Alive, Fairy Tail, Dragon Quest Heroes I/II | Searches supplied scattered save/trainer/forum references without a qualified native gameplay writer for these profiles. Need exact original gameplay file and format-specific loader/checksum evidence; currencies, inventories, growth and collections can be investigated independently of story flags. |
| [760194962/FatalFrame1-Save-Converter](https://github.com/760194962/FatalFrame1-Save-Converter), no declared licence | This is a region-conversion lead for the original Xbox Fatal Frame, separate from later PC games. No native fixture, checksum-safe gameplay mapping or licensed implementation was qualified here; a genuine extracted US/Japanese save and container/import evidence are required. |
| [Kivoie/bluereflection_cloud_saves](https://github.com/Kivoie/bluereflection_cloud_saves), no declared licence | This is a cloud-copy script, not a save parser/editor. Its existence does not establish Blue Reflection gameplay fields, integrity or safe synchronized cloud writing. |
| [ExcaliburZero/dqhrs_save_editor](https://github.com/ExcaliburZero/dqhrs_save_editor), MIT | This edits **Dragon Quest Heroes: Rocket Slime on Nintendo DS**, not either Omega Force Dragon Quest Heroes game. It is excluded from the Koei Musou candidate evidence. |
| Asset tools and random trainer repositories | Atelier PAK decryption and G1T texture conversion are asset formats, not save codecs. A binary download or a repository declaring a permissive licence does not prove advertised save fields, game identity or integrity. No such binary was executed or shipped. |

Public original files are useful even when intentionally modified, but such
modifications do not prove natural caps. A checksum-valid procedural fixture
tests a writer's contract; it does not establish a native game's ownership,
rewards or loadability. Each new qualified profile has its own tests and notes
above, and actual edited game-load/re-save validation remains outstanding.

## Additional original Lydie & Suelle PC input

A fresh [original PC SaveGame.Pro archive](https://savegame.pro/pc-atelier-lydie-suelle-the-alchemists-and-the-mysterious-paintings-savegame/)
supplies an actual `SAVE DATA09.pcsave` gameplay file of 164,112 bytes and a
separate 3,632-byte `SYSTEMDATA.pcsave`. This is stronger than the earlier
system-only Barrel Wisdom lead, but it does not qualify a writable profile.
The existing checksum-enforcing Gust save codec rejects its native body with
an encrypted-marker mismatch. No integrity check was disabled and no
Sophie/Ryza/console item schema was transplanted. Required next evidence is a
title/platform-specific native loader or matching encoded/decoded pair proving
framing, compression and checksum coverage, then occupied-record and mechanic
qualification. DX and Switch remain separate candidates. Archive and input
bytes stay outside the checkout; no third-party binary was run.
