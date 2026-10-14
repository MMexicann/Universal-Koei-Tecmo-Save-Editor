# Cross-platform save conversion

The Save Converter is a separate workspace in the same Windows app. It transfers
the complete shared gameplay data between explicitly supported formats. Existing
editing sessions, themes and pending changes remain available. Conversion uses
the copied on-disk save, so first save any editor changes into another copy.

## Supported routes

Each family below supports all six directed conversions, including PC to console
and console to PC: **12 routes total**. Editor support for a platform alone does
not establish a conversion route.

| Family | Platforms and exact scope | Transfer |
| --- | --- | --- |
| Dynasty Warriors 8 Xtreme Legends | PC common revision `0x131002F0`, original US PS3 PSN `NPUB31449`, plaintext Vita | All `0xB7F44` gameplay bytes, byte-exact; native encryption and checksums rebuilt. |
| Persona 5 Strikers | English PC, English PS4 `CUSA19640`, English Switch, revision `0x20012000` | Complete `0x1C` header and all ten `0x88E36` slots, including full names; destination reserved tail retained. |

**DW6 PS3 editing is included separately. DW6 PC/PS3/Xbox 360 conversion is not
available.** DW8 XL PS4, other regions, modified DW8 PC signatures, Japanese P5S,
and unrelated editions are outside these routes. Console signing, encryption of
the platform export container, reimport and account reassignment remain external.
These routes have format/native-file qualification; this project has not tested
converted saves by loading and re-saving them in the actual games.

## Use the Windows app

1. Copy the source save outside the live game and cloud folders. Export/decrypt
   console saves with your save manager first.
2. Create a save in the destination edition, then copy/export its folder too.
   This **destination template** supplies native framing/encryption context.
   Preserve its original `PARAM.SFO` beside PS3 `APP.BIN`, or
   `sce_sys/param.sfo` beside PS4 `APP.BIN`.
3. Open **Save Converter**, choose the exact route and the two copies, and select
   **Review conversion**. Use compatible game updates and installed DLC.
4. Select **Export to new folder**, choose its parent, and enter a new folder
   name. Both inputs are backed up. The new folder contains the destination's
   expected save filename, required original template metadata and a local
   `conversion.json` receipt. Existing folders/files are refused.
5. Keep your original saves. Test the new copy in-game. For consoles, reimport
   and resign with the destination platform's save manager, such as
   [Apollo Save Tool](https://bucanero.github.io/apollo-ps3/).

Exported console gameplay and unchanged metadata are not a complete signed
console package. Icons, PFDs, keystones and platform save containers are not
created. The receipt reports byte preservation and hashes without input paths,
names, account values or signing keys. It remains local to your output folder.

## CLI

Use the installed package from any working directory. List exact route IDs:

```text
python -m koei_editor --list-conversions
python -m koei_editor --convert dw8xl-to-dw8xl_vita --source SourceCopy/save.dat --template VitaCopy/MainData00.dat --dry-run
python -m koei_editor --convert dw8xl-to-dw8xl_vita --source SourceCopy/save.dat --template VitaCopy/MainData00.dat --output-dir ConvertedVita
```

Dry run validates both copies and the resulting native format without creating
backups or output. Successful commands print JSON; invalid copies, routes,
changed sources and existing destinations return nonzero. The existing EXE's
windowed build is primarily a GUI app; use the Python entry for terminal JSON.

## Implementation and evidence

`conversion.py` declares explicit endpoints/routes and owns immutable review
snapshots, bounded reads, backups and safe exports. Each game's converter owns
its actual native transformation. GUI work runs in a background worker with Tk
updates confined to the main thread. Changing selections invalidates the review.
Native inputs must first pass their exact existing reader and unchanged
roundtrip. Source gameplay is compared with the decoded output before writing,
and the actual saved file is read through the destination reader afterward.
Inputs and complete console metadata are rechecked around backups and export.

DW8 XL converts only the common signature; the PC editor's other accepted
signature is never silently normalized. The destination PC template's original
word seed is retained. PS3 has its byte XOR layer and native byte sum; Vita uses
the plaintext plus sum. Unknown gameplay bytes, record IDs, progression, reward
flags and unusual values transfer unchanged. This does not create equipment or
reinterpret scalar limits.

P5S copies the entire shared prefix. PC encryption uses the destination
template's recovered low-24-bit stream state, which is not printed or put in the
receipt. A source PC save with any nonzero opaque data beyond the ten shared
slots is rejected rather than trimmed. The PC destination retains its own
opaque tail and recomputes only its native sum byte. PS4/Switch readers require
their documented zero reserved tail. All 33 bytes of each name transfer exactly;
no string truncation or language conversion is performed.

Research/inspiration, inspected independently:

- [koko-tsuu DW8 XL converter](https://github.com/koko-tsuu/dw8xl_save_converter)
  and its [author's release discussion](https://www.reddit.com/r/dynastywarriors/comments/1qth7rg/dw8_xl_save_converter_pc_ps3_ps4_psv/):
  platform framing and filename facts. Existing project codecs independently
  implement the streams and checksums. Its permissive truncation/header rewrite
  behavior is excluded here. No upstream implementation is incorporated.
- [zarroboogs P5S save utility](https://github.com/zarroboogs/p5spc.saveutil):
  platform geometry and English name-width facts, corroborated by existing
  native PC/PS4/Switch adapters. No declared reuse licence was identified; no
  implementation was copied. Existing independent stream code is reused.
- [ItsAllAboutTheCode save-converters](https://github.com/ItsAllAboutTheCode/save-converters):
  inspiration for explicit per-game routes and CLI workflows. GPL code is not
  incorporated; its unrelated game algorithms are not used.
- [WO3U community transfer report](https://steamcommunity.com/app/1879330/discussions/0/5788831477038148469):
  highlights decrypted exports and DLC compatibility. It does not prove the
  existing PS3/PC adapters are interchangeable; no WO3U route is registered.
- [Ryza community transfer report](https://www.reddit.com/r/Atelier/comments/1h2kenk):
  highlights update/revision incompatibility. Current original Ryza PC and
  Switch profiles differ and do not qualify a route.

## Validation and remaining mappings

`test_conversion.py` exercises all 12 routes and reverse conversions with
distinctive generated unknown bytes, template encryption/context preservation,
checksums, corruption, foreign metadata, changed sources, forged plans,
backup races, existing folders, actual destination read-back failures, opaque
tail preservation and rejection of lossy input. GUI/CLI checks are in
`test_conversion_gui.py`. Procedural bytes are not gameplay-load evidence.
Private upstream DW8 XL full-file PS3/Vita references passed both directed
routes and reverse roundtrips; the upstream modified PC signature is correctly
rejected. The four DW8 PC routes have procedural preservation/codec evidence,
with independent converted game loading still outstanding. Separately acquired
P5S native PC/PS4/Switch copies passed all six exported forward/reverse routes,
including complete byte-exact reverse results. These copies and output folders
stay outside the repository; none are packaged.

| Requested expansion | Exact blocker |
| --- | --- |
| DW6 PC ↔ PS3 | 212,248 versus 212,240 bytes, little versus big endian, 64-byte officer/horse displacement, differing headers/tails. Need complete typed schema and native paired game-load controls; blanket word swapping would change byte fields. |
| DW6 Xbox 360 | Title/revision-labelled extracted native gameplay, integrity/schema map and import/resign workflow. CON/STFS extraction alone does not prove compatibility. |
| WO3U PS3 ↔ PC / PS4 | PS3/PC records have distinct framing and serialized markers. Need the complete conversion schema, native controls and DLC/reward compatibility. A PS4 rename report does not prove PS3 compatibility. |
| DW8 XL PS4 | Separate larger native profile, exact tail/revision qualification, original title context and lossless handling of data outside the common core. |
| Ryza / Sophie / PW3 / DQB2 | Per-edition full payload/schema and integrity compatibility, native action/transfer pairs and destination import contracts. Shared names/fields are insufficient. |

Adding a family requires its own transform, exact source/destination readers,
preservation/data-loss policy, meaningful regressions and evidence document.
Adding an endpoint never makes other games or platform revisions supported.
