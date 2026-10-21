# v3.1 additional-title investigation

This follow-up checked distinct Koei Tecmo game candidates in addition to the
implemented Warriors platform work. No candidate below is registered as a new
editing profile. No game or third-party editor binary was executed. Public
source was inspected as evidence; no implementation, asset catalog, player save
or owner context is incorporated into the release.

## Uncharted Waters IV Power-Up Kit — original Windows

The most concrete candidate has eight complete publicly distributed
`SaveDat0.DK4`–`SaveDat7.DK4` references, 39,486–39,870 bytes. They share the
`DAIKOUKAI4PKW9 1` identity and correct little-endian file lengths at offset 20.
The independently inspected [native collection](https://github.com/supermizar/dk4pk)
is the existing reference corpus; no new independent player provenance is claimed.

[Dk4PkEditor at 7552b182](https://github.com/litsungyi/Dk4PkEditor/tree/7552b18275e9d404f3eae7c1984b2a8b3926c63d)
currently reads leader/sailor/city/item records. Its old editing branch is after
an unconditional return and inside a block comment, already present that way in
[the early substantive e3d7489 revision](https://github.com/litsungyi/Dk4PkEditor/blob/e3d74894591fe67214eddcd2ffd4a221e09f0eef/Dk4PkEditor.cpp).
Those old writes mainly change recruitment, port availability and item ownership,
which do not supply a prerequisite-safe resource-only editing policy.

The follow-up **recovered the previously missing historical `Kafka::FileWriter`**:
[FileWriter.cpp at 200a09ba](https://github.com/litsungyi/Kafka/blob/200a09bafad27c284848e56bc78bd14bc6ac7e70/src/Stream/FileWriter.cpp).
`SetByte` performs `fseek`/`fwrite`; `CloseFile` only closes the stream. There is
no game-specific integrity calculation in that implementation. Commit 132509f
removed/replaced this older interface. Recovering it resolves the historical
source dependency gap, but does not independently show that the game's loader
accepts arbitrary edits while preserving the changing 32-bit word at offset 24.
A generic raw-write helper is not proof that native integrity is absent.

That header word remains unexplained. Additional bounded CRC32 checks over
header/body starts and short tail exclusions, skipped/zeroed checksum-word
variants, Adler32 seeds and common signed/unsigned rolling hashes found no match.
These rejected hypotheses are not negative proof that no integrity algorithm
exists. No guessed repair or checksum bypass was added.

**Exact remaining gate:** classify offset 24 with the matching native loader or
an independently verified complete original-edition writer; then qualify one
ordinary-resource action with unchanged control, exact record identity and
edited game loading. A port/recruitment unlock recipe is insufficient.

The separate [HD money writer](https://github.com/Kyeongrok/dh4-helper/blob/3abeb5c1db84ee521f58bd7890745dc14dae4d86/Dh4Launcher.Forms/Services/SaveEditService.cs)
explicitly calls offset 24 unresolved. Its Korean HD size-selected offsets and
reported loads are not a codec for original 39 KB PK files or the 16-byte-shorter
Traditional Chinese HD references already acquired.

## Aerobiz Supersonic — Genesis

Freshly inspected [complete disassembly at 9dcbfb68](https://github.com/matiaszanolli/aerobiz-disasm/tree/9dcbfb68c9c4148882242773dd3782e470ae9fb7)
contains `PackSaveState`, `LoadAllGameData`, SRAM copy routines and checksum
instructions. It documents four player records and a separately stored cash
balance rather than treating quarter revenue/expense accumulators as money.

Instruction review corroborates a 16-bit unsigned byte sum over the packed
record's body: `ByteSum` at `0x1D6FC`; the helper at `0xF522` stores the result at
header +2 and body length at +4; `VerifyChecksum` at `0xF552` reads those fields.
Function names/comments are not uniformly reliable: the `0xF522` helper is
labelled `UpdatePassengerDemand`, while a supposed SRAM-footer call at `0xF104`
actually invokes the displayed save-slot panel. Instructions, not these labels,
must define a future contract.

**Exact remaining gate:** complete independent native SRAM reference and emulator
export geometry, complete slot/occupied/header qualification, corroborated
packed record extent and gameplay action/load evidence. ROM-header SRAM address
ranges alone do not establish whether an exported file packs or interleaves odd
bus bytes. No file identity gate was invented from a procedural buffer.

## Other fresh source checks

| Candidate/source | Result and exact blocker |
| --- | --- |
| [Dead or Alive 3 recomp, f1460dc5](https://github.com/parkerallan/doa3-recomp/tree/f1460dc5d2172b264248aa96c060cfc180571c42) | Contains generated game recompilation and generic Xbox kernel cryptography. A matching native save, isolated title-specific save signing/integrity contract and semantic resource/record mapping were not qualified. Generic HMAC support is insufficient. |
| [Samurai Warriors 2 Empires recomp, c173e304](https://github.com/rbxrootx/samurai_warriors_2_empires_recomp/tree/c173e304612d32a979f76c0440a67d244008cd51) | Public generated game code and runtime/modding tooling, with no complete qualified native save reference or independently mapped copied-save writer found in its tree. Existing original SW2 or PS3 SW4 saves do not substitute. |
| [Sangokushi IV DOS reverse engineering, 927e8489](https://github.com/TC999/sangokushi4-re/tree/927e8489bc1f98055d61803ae93523cf78e19d42) | Source labels require verification: the function named `game/save.c` actually contains arithmetic division/remainder logic, not native save serialization. No matching complete campaign writer/reference was qualified. |
| [Tenshouki original-editor archive, a4be7378](https://github.com/tenshoukijp/nobu6_tool_savedataeditor_original/tree/a4be7378ac6e9b9f7ba9e2021308c35255cddfa8) | “Original” describes the editor version. The extracted source explicitly requires 844,623-byte `SAVEDAT.N6P`, magic `1995.08.16`, and identifies Power-Up Kit in its dialog filter. It duplicates the already supported PK edition, not a new base-game profile. |

Broad public source searches also distinguished asset editors, runtime trainers,
configuration generators and tools for non-Koei games from native save writers.
Existing unresolved Fairy Tail, Toukiden, Gundam 2, Atelier Plus and Team Ninja
integrity tracks were not relabelled as supported games to increase a count.
The recovered FileWriter history and concrete native checksum instructions above
are useful new research evidence; they do not establish a newly qualified title.
