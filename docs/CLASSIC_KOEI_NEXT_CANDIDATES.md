# Classic Koei candidates after the English DOS New Horizons adapter

ROTK III Traditional Chinese DOS and original Japanese Windows 95 Tenshouki PK now have scoped v1.9 editors: [ROTK III](ROTK3_DOS_FORMAT.md), [Tenshouki PK](NOBU6_PK_PC_FORMAT.md). Their current documents supersede the historical missing-reference claims below; other editions remain separate.

These are research leads, not supported game/platform registrations. Exact
edition, complete native writer/integrity and original record evidence must
agree before a new editor is exposed. No game executable has been run, and no
external implementation or restricted catalog has been copied.

| Candidate | Concrete source/file evidence | Specific remaining blocker |
| --- | --- | --- |
| Romance of the Three Kingdoms III — Chinese/Japanese DOS | [BeckYang/San3Mender](https://github.com/BeckYang/San3Mender) is a complete Java editor with native `SANGOKU3.SAV` ten-slot framing, direct surgical disk writes and city/officer/country mappings. | No matching complete native/reference `SANGOKU3.SAV` has been acquired. Chinese city/record offsets differ from the newer [Kane72se editor](https://github.com/Kane72se/DOS-SanGoKu3-Simple-Chinese-Translation), which includes its own qualified and uncertain fields; do not choose one mapping by guess or translate across revisions. Need exact edition and native campaign proving occupied slots and geometry. No explicit licence was found for the Java source; use factual format evidence only. |
| Uncharted Waters IV Power-Up Kit — original Windows PC | [supermizar/dk4pk](https://github.com/supermizar/dk4pk) individually publishes eight `SaveDat0.DK4`–`SaveDat7.DK4` files, 39,486–39,870 bytes. They have `DAIKOUKAI4PKW9 1` and matching LE32 length at offset 20. [litsungyi/Dk4PkEditor](https://github.com/litsungyi/Dk4PkEditor) provides MIT source with sailor/city/inventory mappings. | The current console is read only; its historical write code is commented and refers to a `Kafka::FileWriter` absent from the pinned dependency. The changing word at offset 24 has not been established as a checksum, seed or other value. Standard CRC32 over bytes 32 onward and a byte sum do not match it. An active complete original-edition writer, precise header-word semantics and field/edit acceptance proof are needed. Do not declare integrity absent from the old commented code. |
| Uncharted Waters IV HD — Windows PC | [Kyeongrok/dh4-helper SaveEditService.cs](https://github.com/Kyeongrok/dh4-helper/blob/main/Dh4Launcher.Forms/Services/SaveEditService.cs) has an active money writer and seven protagonist-specific offsets selected by exact 107,098–107,482-byte sizes. Its author reports original-game money display/load checks with the offset-24 word left intact. | No matching original HD native campaign has been acquired here. HD lengths/offsets cannot be applied to the original 39 KB PK saves merely because the same magic appears. The source calls offset 24 an unresolved possible checksum and reports observed non-enforcement; this is distinct from proving its algorithm absent. Need matching HD campaign and complete edition/integrity qualification. |
| Uncharted Waters II — Traditional Chinese/Korean DOS | [ssppmm/uw2](https://github.com/ssppmm/uw2) publishes an individual `KOUKAI2.DAT` with size 333,551, while the qualified original English reference is 319,591 bytes. Additional community projects contain native-analysis or game-font leads. | Different file/slot/name geometry. No complete matching native writer and occupied campaign gate has been proved. Do not infer translated offsets from the English array or accept this file through the English adapter. |
| Uncharted Waters II executable asset editors | [Tuo-ZHANG/Uncharted-water-2-editor](https://github.com/Tuo-ZHANG/Uncharted-water-2-editor) explicitly targets Traditional Chinese DOS and has a functional UI. | Its edit functions patch `main.exe`; this is an executable asset editor, not a gameplay-save writer. It cannot qualify a native save editor. |
| L'Empereur — classic PC | [playhan/lempereur-editor](https://github.com/playhan/lempereur-editor) has editor plans and UI mockups. | No implemented native parser/writer or campaign reference in the examined repository tree. A project title/mockup is not a functioning save editor. |

The corresponding English DOS New Horizons implementation and its precise
published-format/player-save distinction are documented in
[UNCHARTED_WATERS2_DOS_FORMAT.md](UNCHARTED_WATERS2_DOS_FORMAT.md). Its public
reference contains initialized empty slots; an independently shared occupied
original English `KOUKAI2.DAT` remains the most useful next input.

Native files and external source copies stay outside the checkout and public
downloads. This round examined public GitHub source/tree/code results, public
game-specific references and search-engine/forum leads. Unusable or unrelated
search results are not treated as negative proof that a save/editor cannot
exist. None of the blocked rows adds a supported library card.
