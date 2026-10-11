# Atelier Totori DX — Steam PC research

Totori DX Windows (Steam app **936180**) is not registered as a gameplay editor.
Two useful source projects were inspected, but a qualified native gameplay save
and complete disk framing/integrity specification remain missing. This is
separate from the PS3 game and from Rorona DX (app 936160).

## Source evidence

- [jrpx/AtelierTotoriColeCheat](https://github.com/jrpx/AtelierTotoriColeCheat/tree/a5c683a85757d69ff4b4af614304a36e59119f89),
  Apache-2.0, writes three bytes at `0xB3FC`: `80 1A 06` for 400,000 Cole or
  `C0 27 09` for 600,000. It does not validate title, file size, revision,
  checksum or current value. Its OpenOrCreate operation can even extend a
  foreign/truncated file. Three bytes written are **not proof of a three-byte
  currency field**, and its two cheat targets are not proof of a natural cap.
  No implementation was copied or exposed as a safe adapter.
- [nicoverbruggen/atelier-arland-fixes](https://github.com/nicoverbruggen/atelier-arland-fixes/tree/96a4506892de3284a8adc78a4b6a96d67e8bbf59),
  MIT, documents native Totori item constructors and serializers in
  `src/engines/phyre/item_guard.h` and `.cpp`. Runtime evidence establishes ten
  character equipment sets, three equipment records per set, 100 carried-item
  records, 999 container records and 52-byte item records. Items store two ID
  words, float quality, five trait indices, four effect indices and a tail word.
  There are 204 trait records and 223 effect records in the inspected builds;
  an empty index is -1. These are table/physical-record limits, not blanket
  item-validity or synthesis permissions.

The Cole tool also has **title-specific source-author gameplay testimony**.
In the [Steam app936180 announcement](https://steamcommunity.com/app/936180/discussions/0/2865909887924677355/),
its author directly links the GitHub release, describes the 400,000/600,000
targets and discusses playing a third or fourth loop. In the same author's
[later gameplay discussion](https://steamcommunity.com/app/936180/discussions/0/2865909982608566012/),
they write, "I created a Cole hacking tool, so I wondered if I screwed up the
wrong 1s and 0s. Turns out I didn't," then explain that Rorona's appearance
requires synthesis at Atelier Totori and a preceding flashback event. The
reported gameplay problem was a legitimate event prerequisite, rather than
the author diagnosing their currency tool as its cause.

This is useful source-author testimony connecting their narrow offline Cole
tool with continued **Totori DX PC** gameplay. It is stronger than a source listing
alone, but it is not a controlled edit/load/re-save record: no paired native
files, displayed post-edit Cole, executable revision, full storage width or
natural cap accompany those posts. The writer's three-byte operation still
does not qualify every byte of the currency field, unrelated gameplay fields
or a complete native integrity model. A genuine PC gameplay fixture remains
essential to check the narrow writer against exact title/revision/framing;
this testimony must not be lost or misdescribed as proof that no public
gameplay experience with the tool exists.

The MIT mod repairs loaded **memory**, then calls the original serializer with
an opaque stream. It explains a corrupt saved container limit of 5,000 allowing
out-of-bounds operations against the 999 physical records. It is not a complete
disk chunk decoder: file header, chunk directory/framing, native file lengths,
title marker, revision, checksum and ownership context are not specified.
Runtime equipment addresses must not be promoted to disk offsets. Its
action-item ID predicate applies only to a combat action table, not to every
weapon, armour or material in the save.

The mod identifies Totori's installed executable by an **A12V** basename prefix
(Rorona uses A11R, Meruru A13V). The exact full filename must come from the
installed game; an invented generic executable name is not an essential input.

## Genuine-save acquisition

The [SaveGamePro Totori-labelled page](https://savegame.pro/pc-atelier-totori-the-adventurer-of-arland-dx-savegame/)
provided an archive, but it contains only a 36,864-byte `SYSDATA` under app
936160. That is a Rorona-associated system-data download, not a qualified Totori
gameplay slot. It is shorter than the Cole lead's `0xB3FC` position. It was kept
private and excluded from qualification.

Savegameworld's inspected Totori search returned PS3 results, not a native PC
fixture. All four pages of Steam's inspected save search and the
[crash discussion](https://steamcommunity.com/app/936180/discussions/0/1745605598717092296/)
were read. The crash-fix author obtained a player's save through a private
friend exchange; no public gameplay archive was acquired from those posts.
GitHub repository/issue searches did not provide a native slot. Some general
searches presented bot challenges or irrelevant results; no challenge, login or
access control was bypassed. These acquisition limits are not decryption failures.

## Coverage and exact blockers

| Mechanic | Required proof before implementation |
| --- | --- |
| Cole | Native app936180 gameplay slot, unchanged control and purchase/sale before/after pair; establish actual storage width, cap and integrity coverage instead of blindly writing three bytes. |
| Characters, battle/alchemy level and EXP, skills | Native disk chunk locations, named record identities, natural limits and level/reward/derived-stat dependencies; runtime equipment sets alone are insufficient. |
| Equipment, carried items and container | Complete native chunk boundaries and record counts, qualified occupied records, named ID catalogs and equip/inventory references. Never enlarge the saved container limit to the source's corrupt 5,000 value. |
| Quality, traits, effects and synthesis | Valid per-item combinations, synthesis eligibility, cost/quality calculation and trait/effect references. Physical table bounds do not prove that every trait or effect belongs on every item. |
| Recipes, shop registrations, requests and collections | Qualified disk flags/records, recipe/category domains and acquisition/reward dependencies. |
| Adventurer licence/rank, points, exploration and travel | Separate earned/spendable progression, map/location flags, travel/time costs and rank rewards; native disk mappings remain missing. |
| Friendship, character events and endings | Controlled event pairs and prerequisite chains. Community reports show missed Mimi/boat and true-ending events; broad flag Max would risk inconsistent progression. |
| Calendar, story, boat construction and New Game+ | Exact calendar encoding, time-limit rules, construction/event triggers and carry-over behavior. Keep these separate from currency and equipment. |
| Gallery, music, costumes and other bonus content | Native unlock/view/equip flags and content entitlement/prerequisite evidence. |
| Integrity/revisions/owner context | Exact installed PC executable and complete save files are required to establish framing, integrity and supported builds. No owner secret or external key requirement has yet been proved. |

The most useful next input is a **complete native gameplay slot and SYSDATA from
Steam app936180**, copied outside the live/cloud folder, with language/build
information and an unchanged re-save. A Cole purchase/sale pair would qualify
the first narrow field. The installed **A12V-prefixed gameplay executable**
would allow static loader/writer and checksum analysis without executing it.
Further controlled inventory, equipment, synthesis and progression pairs would
extend coverage independently; one unresolved subsystem should not block others.

No qualified native PC roundtrip, targeted edit, GUI workflow or edited in-game
load was performed for Totori DX by this project. The source-author testimony
above is distinct from validation performed by this editor. The public sources
and the foreign archive are leads, not completed support. No player files or
external source code are included in this repository or its releases.
