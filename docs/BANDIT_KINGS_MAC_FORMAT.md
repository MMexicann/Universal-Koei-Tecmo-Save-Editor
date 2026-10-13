# Bandit Kings of Ancient China — original English Macintosh

The adapter edits a copied **21,122-byte native data fork** with `SUI0` or
`SUI1` framing. Use a `.cim` filename for the copied input/output. This is a
Windows-hosted editor for classic Macintosh data, not a DOS/NES adapter.
MacBinary, AppleDouble, emulator states and resource forks are rejected.
Classic Macintosh type/creator filesystem codes must be retained or restored
externally when transferring the edited data fork back to the original system;
those codes are not bytes inside this file and are not manufactured here.

## Source and qualification

The complete [Dan Healy toolkit](https://github.com/danhealy/bandit_kings_modding/tree/c0edaed0350e4b62139120bf0bfd0d309af46a05)
explicitly targets Macintosh scenarios **and saved games**. Its
[struct definitions](https://github.com/danhealy/bandit_kings_modding/blob/c0edaed0350e4b62139120bf0bfd0d309af46a05/lib/bandit_kings/structs.rb)
map the complete data fork; the
[writer](https://github.com/danhealy/bandit_kings_modding/blob/c0edaed0350e4b62139120bf0bfd0d309af46a05/lib/bandit_kings/scenario_editor.rb)
reconstructs those contiguous spans and writes the complete exact-size file.
It applies no checksum, encryption, compression or alternate save envelope.
Offsets are independently implemented as factual format information. No third
party code, name catalog, assets or binary data is included in this repository.
The source is MIT licensed, copyright Dan Healy, 2026.

The published `examples/dans_custom_scenario/SUIDATA2_NEW.CIM` was privately
acquired and validates every array boundary, name anchor, native ruler link,
unchanged roundtrip and surgical edit. It is an **author-modified scenario**,
not an independently shared native saved campaign. It must not count as genuine
player-save or in-game editing evidence. Qualification is explicitly
`published_format=True`, `sample_verified=False`, `editing_verified=False`,
`game_load_verified=False`. No game executable was run.

## Layout and controls

| Span | Native framing |
| --- | --- |
| Header | Four bytes `SUI0` / `SUI1`; original English names qualify locale/title |
| Heroes | Offset 4, 255 records of 24 bytes |
| Setup | `0x17EC`, 328 bytes; BE16 year and one-byte month |
| Prefectures | `0x1934`, 49 records of 32 bytes |
| Tactical/name records | `0x1F54`, 49 records of 28 bytes |
| Hero names/persona metadata | `0x24B0`, 255 records of 46 bytes |
| Active hero gate | Hero +23 bit `0x80`; prefecture ID at +6 |
| Hero abilities | Strength/Dexterity/Wisdom at +12/+13/+14, one byte each |
| Prefecture ownership | +31 is ruler hero ID plus one; zero means unclaimed |
| Resources | Gold/Food/Metal/Fur at +12/+14/+16/+18, unsigned BE16 |

The first native hero name is `Gao Qiu` and first prefecture is `Lan`; these
are framing anchors rather than imported catalogs. Active hero locations must
fit the prefecture array. An owned prefecture must reference an active ruler
whose faction equals their own hero ID and whose location is that prefecture.
Missing/foreign names, duplicate prefecture identities, bad calendar, wrong
size, incompatible links and foreign wrappers are rejected.

Controls reduce opened balances and existing active hero abilities only.
Unknown values above ordinary gameplay ranges remain readable and are retained
as exact typed no-ops. Assigning an opened value unstages changes. The public
writer's example targets do not establish natural limits, so increases and Max
are excluded. A resource can reach zero; ownership is never created.

| System | Implemented scope or remaining requirement |
| --- | --- |
| Gold, food, metal, fur | Owned-prefecture reductions; unclaimed prefectures are inspection only |
| Strength, dexterity, wisdom | Existing active heroes, reductions only; progress bytes preserved |
| Search and records | All prefectures and active heroes; names read from opened data |
| Body/max body, men, persona, loyalty | Inspection/preservation; coupled mechanics and legitimate bounds unqualified |
| Faction, movement, rulers, ship/facility flags | Read only; no membership/ownership or prerequisite actions |
| Calendar, completion, conquest and scenario setup | Read only; no scenario or campaign creation |
| Native campaign / original-game edit loading | Matching independent original English Macintosh save and controlled action/load pairs still required |

## Validation

`tests/test_bandit_kings_mac.py` covers all seven mapped field families,
big-endian storage, exact no-op, surgical unknown-byte preservation, typed
unusual values, existing-record gates, complete pending-map validation,
identity/calendar/geometry rejection, immutable snapshots, source changes,
backup/restore, destination protection and on-disk readback. The optional
`BANDIT_KINGS_MAC_REFERENCE_COPY` check accepts the private author-modified
scenario solely as source geometry evidence. Fixtures and external copies stay
outside the repository and release assets.
