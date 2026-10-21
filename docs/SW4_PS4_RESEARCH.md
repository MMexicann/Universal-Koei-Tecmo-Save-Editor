# SW4 PS4 transfer investigation — 2026-10-21

The investigation obtained two publicly shared **EU PS4 CUSA00783** save packages,
but neither contains decrypted native gameplay. No PS4 conversion route is
qualified by these packages.

## Public sources checked

- [PlayerSquared original save request, thread 5594](https://playersquared.com/threads/samurai-warriors-4-us-save-set.5594/), posted June 4, 2023. Post 11 (April 26, 2026) publicly links an EU CUSA00783 RAR. Posts 16–17 explicitly discuss the inability to decrypt the save without a corresponding console/working tools.
- [Thread 5594, page 2](https://playersquared.com/threads/samurai-warriors-4-us-save-set.5594/page-2): posts 28 and 31 (August 15, 2026) link another original EU CUSA00783 ZIP. Post 31 also attaches that ZIP. The two public originals were downloaded privately and their archive entries inspected without executing any supplied file.
- [EU CUSA00783 trophy save set, thread 19420](https://playersquared.com/threads/samurai-warriors-4-save-set-cusa00783.19420/), posted September 15, 2026 and updated September 18. The download requires account interaction and was not accessed. The author discusses Save Wizard/bot re-signing and a prospective save editor, but supplies no publicly accessible native serializer or decrypted example in the visible text.
- [Sony title metadata mirror: EU CUSA00783](https://github.com/FlexBy420/sce-tmdb-scraper/blob/abba1a1c2efd2ace308e9bbf2c2960b08fe282f4/tmdb/json/CUSA00783.json), [US CUSA00919](https://github.com/FlexBy420/sce-tmdb-scraper/blob/abba1a1c2efd2ace308e9bbf2c2960b08fe282f4/tmdb/json/CUSA00919.json), [Japan CUSA00771](https://github.com/FlexBy420/sce-tmdb-scraper/blob/abba1a1c2efd2ace308e9bbf2c2960b08fe282f4/tmdb/json/CUSA00771.json). These establish regional title identities only, not gameplay formats or interchangeability.
- [ShadPS4 original EU version 1.00 report, issue 2405](https://github.com/shadps4-compatibility/shadps4-game-compatibility/issues/2405), March 31, 2026, with a linked original emulator log. The game reaches menus and crashes before gameplay. The log records opening `/savedata0/app.dat`; it contains no native save dump, byte length, revision or checksum contract. That filename observation is only a preparation lead and does not establish a parser.
- [Apollo SW4 checksum fixer](https://github.com/bucanero/save-decrypters/tree/e9f81c1f42ceac6df2e859595578b0b7e7e29a10/sw4-checksum-fixer) explicitly targets **PS3**. The current Apollo save/patch catalogs checked supply SW4 PS3 records, not a PS4 native SW4 implementation. The existing PC DX and PS3 profiles remain separately qualified.

## Exact acquired-input limitation

Both original archives contain an `app0000` save image of **10,485,760 bytes**
and a 96-byte `app0000.bin` sealed-key companion. They are PS4 console-export
containers. Neither is a decrypted gameplay file; neither supplies readable
original `sce_sys/param.sfo`. One archive is approximately 2.1 MiB compressed and
the other approximately 10.0 MiB. The existing exact PC and PS3 native readers
correctly reject the save image. No container key, account value, save bytes or
personal path is published by this report.

External console/save-tool decryption must produce the complete native gameplay
file and original title/revision metadata first. A working route then needs
its exact framing, native integrity coverage, native object/record geometry and
edition-specific migration policy. An original low-progress export and a
single-action control pair would distinguish balance/ID meaning from plausible
byte patterns. The source images themselves cannot establish those facts.

## SW4 gem-transfer correction

The existing PC evidence document states that the **gem name/order dictionary is
not qualified for this DX build**. Eight corresponding bytes and similar caps
are insufficient to prove a PS3 gem index denotes the same material on PC.
The new SW4 PS3 ↔ PC routes should transfer **gold only (4 mapped bytes)** and
retain all eight destination gem balances until an enumeration/action-pair
mapping is independently established. Gold's semantic identity, offsets,
endianness and 999,999 bound are independently implemented in both adapters.

This limitation does not remove the existing per-platform manual gem controls.
It prevents silently assigning a source gem type to an unproven destination type.


## Native migration and exact external input

Further static inspection of the supplied **PC DX** build, without execution,
independently confirms that reader `0x140194F00` handles eight revisions. For
example, native revision `0x2118` uses section b length `0x828`, versus `0x858`
in current `0x39EA`. Revision `0x35C7` also transforms custom-character records
from stride `0x6C` to `0xCC`, including native string conversion. These are PC
loader facts, not proof that an original PS4 export has that framing or revision.

Migration for `0x2118`/`0x253B` additionally remaps custom-character part selectors
through an external **1,268-entry, stride-`0x38` table**. Loader `0x1401943F0`
requests resource **`0x2591`** and stores its pointer at `0x140F7B178`. The pointer
is in non-file-backed data, not an embedded dictionary; at least **71,008 decoded
bytes (`0x11560`)**, plus any native resource framing, are required. The matching
acquired input contains the executable only, without that resource archive.

A future converter might retain a fully qualified, PC-compatible legacy payload
and revision in a native PC envelope, letting the destination game's existing
loader perform migration using its installed assets. This is an **unqualified
avenue**: no PS4 plaintext example yet establishes the framing, section geometry,
checksum coverage or revision, and the current PC adapter rejects older revisions.
It does not justify changing a revision word or copying unclassified blocks.

## Additional original-edition source checks

- The complete 403-entry [decrypted PS4 save corpus](https://github.com/xcier/Decrypted-PS4-Saves) and two indexed forks contain Borderlands/Diablo examples, not original SW4. The [historical PS4 collection](https://github.com/bloodrive65/PS4-Game-Saves-Database/blob/master/actual%20bbcode) instead describes encrypted USB exports and external Save Wizard re-signing.
- The original ShadPS4 report's complete log and comments provide no gameplay file, original SFO or native read/write-size/checksum evidence. Its `app.dat` filename event remains a preparation lead only. Public save-set preview attachments return HTTP 403 and were not accessed through alternate routes.
- Original Vita regional identities are corroborated separately, but the [EU PCSB00592 VitaCheat file](https://github.com/r0ah/vitacheat/blob/master/db/PCSB00592.psv) contains runtime memory/pointer patches, not a disk decoder or checksum writer. The complete rinCheat and Apollo Vita/save catalogs checked supply no original-SW4 native save codec. Vita, PS3 and SW4-II facts cannot establish original PS4 compatibility.

The next useful input is a complete **original SW4 PS4 decrypted gameplay file**
with unchanged original title/revision metadata and a known game/update/DLC
configuration. A low-progress copy and a single-action control pair would qualify
integrity and typed fields. Broader custom-character migration additionally needs
the exact resource `0x2591` correspondence or proof of native legacy handoff.
Gold can avoid CAW/equipment references after source qualification; separately
qualified standard-officer base stats may also form a scoped transfer. Whole
progression/equipment/CAW groups still need linked-identity and dependency proof.

## Official console inheritance is a separate route

The [official Japanese SW4 DX site](https://www.gamecity.ne.jp/sengoku4/dx/)
explicitly documents original SW4 **PS4/PS3/Vita → PS4 DX** inheritance. It uses
an original save already on the PS4, or the original game's latest-update
Data Sharing upload, and offers import at startup; trophies do not transfer.
This confirms an official console-edition migration operation. It does not
identify raw file framing, promise EU/US compatibility, or establish Steam
imports of console files. The [Steam web manual](https://www.gamecity.ne.jp/manual/sengoku4/dx/jp/)
links the PS4 gameplay manual for general game explanations; that reference
does not extend the console inheritance statement to PC.
