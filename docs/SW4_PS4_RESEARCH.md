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
