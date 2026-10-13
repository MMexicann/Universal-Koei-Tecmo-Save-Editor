# Blue Reflection candidates and mechanics

## Original Blue Reflection — Steam app658260

The public
[Kivoie cloud-copy repository](https://github.com/Kivoie/bluereflection_cloud_saves)
contains 32 native-looking `GAMEDATAnn.pcsave` gameplay files, each 768,000 bytes,
a separate 51,200-byte `SYSTEM.DAT`, and a chronological save-update history.
Two gameplay files were independently downloaded outside this checkout and
inspected without running the batch script, game or an editor executable. The
repository's restrictive noncommercial terms are recorded; no source or save
contents are copied into this project.

Observed native facts: the first big-endian integer is decimal `20150729`, a
serializer revision date, **not a proved checksum**. Tagged node lengths are
little-endian while observed numeric content is big-endian. Distinctive
`equipment`/supporter, `Fragment`, school-field maps and friendship tags separate
this title from other Gust games. Three `Party` records use 384-byte nodes in
the inspected gameplay layout. Node-based `money` appears separately from
inventory and story data. These are inspection findings, not write grants.

[DragoniteX1's BR1-to-Quartet converter description](https://www.nexusmods.com/bluereflection/mods/7?tab=description)
independently reports a 2017 big-endian to Quartet little-endian conversion and
explicitly declares the script CC0 despite restrictive default page boilerplate.
Its actual source download requires login and was not obtained. Reported
in-game results are the converter author's, not validation of this editor.
Quartet is a separate unqualified profile; shared content IDs do not prove
identical framing, ownership or dependency rules.

| Mechanic | Current blocker |
| --- | --- |
| Currency and native integrity | Need exact native loader/writer or freely accessible source establishing integrity coverage/absence, plus controlled purchase/re-save pair and displayed values. Plaintext and a plausible tagged scalar alone do not prove safe saving. |
| Existing inventory, crafting and recipes | Need item kinds, quantity/ownership rules and controlled consume/craft pair before writes; unknown IDs cannot qualify applicable consumables. |
| Fragments/equipment and effects | Need fragment ownership, skill assignment/reference rules and effect applicability. Equipped slots and collection unlocks remain distinct. |
| Character growth/skills | Original BR growth uses Growth Points and stat investment, separate from Second Light battle EXP/TP. Need controlled point-allocation/reset and displayed growth states; inherited generic engine EXP names are insufficient. |
| Friendship/supporters | Need float/int encodings, rank thresholds, supporter skill dependencies and controlled event/reward pair. |
| Exploration, collections, quests/story | Need independently qualified progress/reward/prerequisite relationships. No completion or event transplantation is supported. |

No writable original Blue Reflection adapter is registered. Precise next
inputs are an accessible title-specific native serializer/source, untouched
save/re-save control and a single money/item/growth action pair with game build
and displayed values. Public gameplay evidence exists; repeating a generic
request for a save is insufficient to describe the remaining blocker.

## Blue Reflection: Second Light — Steam app1423600 / PS4

A separate [original Steam PC adapter](BRSL_PC_FORMAT.md) now qualifies existing
ordinary-container quantity reductions using independently corroborated
source-backed byte/stride facts, mandatory native checksums and exact opaque
terminal Guide retention. The earlier observations below remain useful for
broader mechanics; money/Jewel, TP, recipes, ownership and story writes remain
unqualified. Edited game loading is still untested.

The independently shared [Barrel Wisdom PC saves](https://barrelwisdom.com/blog/atelier-pc-saves)
include clear data and an NG+ pre-final-boss gameplay copy. Both original
`GameData00/data.dat` and `GameData01/data.dat` files were downloaded and kept
outside the checkout. Their native sizes are 205,984 and 213,712 bytes. The
existing MIT-attributed Gust envelope codec independently decrypts both and
verifies both XOR and additive native checksums. Their 256-byte envelopes begin
with little-endian version 1; decoded payloads are 790,986 and 796,231 bytes and
start with the `20150729` serializer date followed by 28 zero bytes.

Bounded top-level traversal identifies title-specific `SchoolComm`,
`SchoolDev`, `LinkSketch`, `mix_party` and `free_space` blocks. The party block
contains 15 records; this is independently consistent with the converter's
standalone profile and differs from Quartet's 20-record layout. The 470,961-byte
item root contains native 88-byte records in container/important/expendable
pools of 5,000/300/50, plus ID counters and a separate Jewel scalar. These
extents establish records, not item kinds or editable offsets. Raw structures
must not inherit another Atelier game's endianness or item schema.

Both decoded streams end with a `Guide` node declaring 54 bytes while only 50
remain, immediately after `isGuidingScenario`'s four-byte length. Both native
checksum gates pass despite this apparent shortened scalar. Exact source or a
controlled native save/re-save pair must establish terminal-zero elision before
any parser completes this node or a writer appends bytes. The narrow PC writer
retains the exactly matched 50-byte terminal profile opaquely and never pads or
repairs it; its earlier bounded quantity field does not require completing this
node.
An external envelope check re-encoded each exact decoded payload and confirmed
identical decoded bytes and byte-identical native encrypted output, original
header/footer/seed preservation and corruption rejection. This is genuine-file
codec evidence; it is not an edited game-load
test or a safe gameplay-field qualification.

The commercial
[PS4 web editor](https://modwithchaoszage.com/editor/brsl) advertises creating the
first 4,095 items at quantity 999 for decrypted CUSA25335 files. It discloses no
native integrity/offset implementation and is not proof of PC applicability,
legitimate item bounds or safe ownership.

The separate
[Second-Light-to-Quartet converter](https://www.nexusmods.com/bluereflectionsecondlight/mods/5?tab=description)
reports encryption/block changes and party-size/recruitment repairs. That makes
copying a BR1/Quartet schema particularly unsafe. Its source download remains
login-gated. The public description also reports two converted DLC map
destinations that crash without matching game assets; save flags do not create
legitimate DLC ownership or installed content.

| Mechanic | Established facts and precise write blocker |
| --- | --- |
| Currency/Coins | The native tagged `money` scalar exists and the converter lists money, but no controlled action links it to displayed resources. [Coin](https://barrelwisdom.com/second-light/items/coin/en) is a craftable Tool item exchanged at facilities, with Warm Sand and Metals ingredients. Do not present an inherited engine money tag as verified player currency. Need a Coin craft/exchange pair and item-ID mapping. |
| Inventory, quantity and quality | Existing unique ordinary-container counts can now be reduced to at least 1 in the separately qualified original PC profile. Native catalog/applicability, displayed consume/craft pairs, zero/removal, increases, creation and quality/effects remain unqualified. |
| Synthesis and recipes | [Official crafting manual](https://www.koeitecmoamerica.com/manual/brsl/3200.html) explains Memories obtained through story, requests and Heartscapes; up to four helpers and unit bonuses alter effects. Need an existing unlocked recipe craft pair and exact result/material dependencies, not a generic Atelier trait transplant. |
| Talents/TP and battle EXP | [Official Talents manual](https://www.koeitecmoamerica.com/manual/brsl/7200.html) distinguishes spendable TP, cumulative TP-driven Talent Level, level rewards and Ao's TP gained from other characters' level increases. Four talent types have story/relationship unlocks. Need allocate/reward controls and native mappings for each linked value; battle EXP is separate. |
| Fragments/equipment | [Official Fragments manual](https://www.koeitecmoamerica.com/manual/brsl/7300.html) establishes date acquisition, fragment sizes, seven effect types, gear activation and slots expanded through Talents up to 10. Need owned fragment references and equipped-slot/action evidence before edits. |
| School facilities | Proposals depend on story/requests; each facility can be constructed once, upgraded, stored or placed, and sets activate effects. Need build/upgrade controls and item/reference dependencies. Coins exchanged at facilities remain resource edits separate from proposal/event unlocks. |
| Friendship, exploration and collections | Dates grant TP and choice-dependent Fragments. Heartscape blocked areas require items or Talent Levels. Need event/reward/prerequisite controls; no story, relationship, objective or collection completion edits are supported. |

The registered narrow PC quantity writer has its own [qualification and tests](BRSL_PC_FORMAT.md).
Broader features still require a native untouched re-save and terminal Guide
source, displayed Coin/item action pairs,
title-specific item/TP reference maps and a system companion where relevant.
Original PC genuine gameplay and envelope integrity are now evidenced; a
generic request for another save is not the remaining blocker.

## Older Fatal Frame lead

[Mikompilation/Himuro](https://github.com/Mikompilation/Himuro/blob/main/src/mc/mc_exec.c)
provides a title-specific original PS2 Fatal Frame decompilation lead: its save
writer reserves 16 prefix bytes and sums remaining saved bytes; its loader
checks that native checksum. This is separate from the newer Katana JSON
container and older Xbox conversion tools. No PS2 gameplay fixture, region-
labelled complete memory-card export and structure/offset qualification was
completed here. It must not be promoted as implemented support from checksum
source alone.
