# Regional edition qualification and remaining inputs

This investigation adds **no additional regional gameplay writer**. Product
existence, translated titles and save compatibility are separate questions.
The existing Windows DW5 Special editor remains the sole DW5 Special adapter;
its regional product evidence is recorded in [DW5_SPECIAL.md](DW5_SPECIAL.md).
The other initial Special leads are tracked in
[DW6_SPECIAL_REGIONAL_RESEARCH.md](DW6_SPECIAL_REGIONAL_RESEARCH.md),
[DW7_SPECIAL_PSP_RESEARCH.md](DW7_SPECIAL_PSP_RESEARCH.md) and
[PSP_SPECIAL_RESEARCH.md](PSP_SPECIAL_RESEARCH.md).

Research below is scoped against the development inventory at base `bdb3833`.
It does not supersede separate console, modern Windows, Gust, Team Ninja or
Switch assignments. Regional branding does not create another supported-game
entry, and a similar record offset does not establish compatibility.

Coordination retained [the prepared DW5 adapter](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/5)
and reviewed [the console lane](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/7)
and [the additional Windows Musou lane](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/8).
Those drafts remain separate; this branch does not copy or supersede their
WO3 Ultimate, SW2 HD, SW4-II, Sanada or original DW9 work.

## Additional leads and evidence boundary

| Candidate or existing profile | Verified evidence | What remains unproved |
| --- | --- | --- |
| DW4 Hyper, native Windows | The pinned public PC research and independently qualified native file identify `save.dat`, 69,568 bytes, raw plaintext serialization, a u32 byte-sum checksum and 32 item entries. See [DW4_PLATFORM_FORMATS.md](DW4_PLATFORM_FORMATS.md). | The existing qualification does not identify an independently supplied Japanese, Traditional Chinese or Simplified Chinese build/sample pair. A regional name or download-page language cannot establish another layout or a compatible profile. |
| DW4 Xtreme Legends, PS2 USA | The independently qualified USA profile identifies the `BASLUS-20812` inner gameplay file, 34,064 bytes, u16 byte-sum integrity, revision 3 and 41 items. This is demonstrably different from Windows Hyper, despite several shared offsets. | Japanese/European payload field compatibility, native product/revision checks, localized name encoding, and actual import/load of edited regional copies remain unqualified. |
| DW4 XL Japanese/European archives | Existing repository research records independently extracted Japanese GameFAQs entry 4640 and European entry 5256 and their rejection by the USA adapter. Those regional exports therefore must not be passed through a renamed USA selection. | The earlier archive evidence is not a newly obtained native qualification in this investigation. The current GameFAQs page/download requests returned HTTP 403; no additional regional archive was acquired, decoded or edited here. Regional filenames, lengths and writable maps are not inferred from the USA save. |
| Original DW6 Windows, Chinese product lead | The concurrent Special research distinguishes the ordinary Windows product from PSP/PS2 Special; see [DW6_SPECIAL_REGIONAL_RESEARCH.md](DW6_SPECIAL_REGIONAL_RESEARCH.md). The existing adapter qualifies a 212,248-byte native plaintext profile with 41 canonical officer records. | No independently attributed Chinese/Japanese pair proves either a different format or reuse of the existing profile. Localized horse names, unknown record words, native revision identity and integrity responsibilities need their own evidence. |
| Musou / Warriors Orochi Z Windows | The existing editor qualifies one native revision-2 profile: 155,464 (`0x25F48`) bytes, two serialized sections, a twenty-byte integrity record and preserved opaque tail. This is a functioning existing editor, with genuine-file evidence described in [OROCHI_RESEARCH.md](OROCHI_RESEARCH.md). | The genuine fixture establishes the observed profile, not all Japanese/Chinese builds. A second localized build needs provenance and a native sample before compatibility can be expanded; no separate regional Z adapter is justified yet. |
| Other modern regional Deluxe/Complete branding | Modern supported Windows editions and open assignments already cover explicit game/platform profiles. | A regional retail label, bundled soundtrack, costume/DLC entitlement or different display language is insufficient evidence of a save revision. No additional profile was promoted from such branding. |

The Japanese number is not the Western Dynasty Warriors number: the Japanese
`Shin Sangokumusou 3` family corresponds to Western **Dynasty Warriors 4**,
`Shin Sangokumusou 4` to **Dynasty Warriors 5**, and `Shin Sangokumusou 5`
to **Dynasty Warriors 6**. In particular, Windows Hyper and PS2 Xtreme Legends
are different products/platforms; the existing code does not treat their shared
character/weapon offsets as a common file format. An unverified localized
retail spelling is left a lead rather than asserted as an official title.

## Concrete differences already established

The format comparison above is useful for rejecting false regional matches,
not for claiming another implemented edition:

| Property | Existing Windows DW4 Hyper | Existing PS2 DW4 XL USA |
| --- | --- | --- |
| Serialization | Entire raw file is gameplay data | Gameplay file is an entry inside a memory-card export |
| Native gameplay length | `0x10FC0` | `0x8510` |
| Integrity | u32 little-endian sum at `0x10FA8`; twenty zero trailer bytes | u16 little-endian sum at 0 over bytes 4 onward; u16 revision 3 at 2 |
| Difficulty enum | Three values | Five values |
| Item count / equipped empty sentinel | 32 / 32 | 41 / 41 |
| Special weapon EXP | 36,001; no XL Lv.11 claim | 36,001 and 36,002 |
| Export metadata | None | Entry metadata, icon files, alignment and padding preserved |

The independently inspected public research is pinned to
[Hyper `3638c8d`](https://github.com/talkative-platano/dw4hyper-save-editor/tree/3638c8dc23d2607b862a1105bfc9806e69d9e871)
and [XL `b3ea895`](https://github.com/talkative-platano/dw4xl-save-editor/tree/b3ea895c6e854accd6860fd51ce69aeb024f53e9).
Their README contents were retrieved again for this investigation. Neither
reference supplies a declared source licence or a regional native qualification;
no external implementation was imported. Existing independent Python adapters
and public procedural tests remain the authoritative application behavior.

## Localization is not serialization proof

The Hyper inspector currently decodes its nine-byte custom/bodyguard name cells
as ASCII for read-only display. This is source-backed for the inspected public
English reference. It is **not** proof that localized cells use ASCII, Big5,
GBK, Shift JIS, UTF-16 or the same width. Replacement characters in that
inspector do not alter the original bytes, and name editing remains unavailable.
The DW5 Special inspector likewise preserves original bodyguard name bytes;
its localized product qualification does not silently add a guessed codec.

An automatic encoding guess would be ambiguous: many short byte strings decode
under multiple East Asian code pages. A matching native executable's save/name
routines or labelled entered-name pairs are needed to identify the actual
encoding, terminator, byte budget and treatment of unrepresentable characters.
Likewise, a Chinese UI or a translated filename alone does not prove changed
officer counts, array strides, integrity coverage or revision semantics.

## Exact additional inputs needed

For each proposed regional profile, provide privately an original copied save
and attributable product/build context. The useful evidence is:

- A matching product page/manual or installed product identity establishing
  platform, official regional title and build, plus an unedited complete native
  save. A community translation or renamed archive must be identified as such.
- An unchanged control pair and one-action pairs for an existing weapon or item,
  officer progression, equipped reference and named record where applicable.
  Keep ownership, rank, growth, rewards and stage completion separate.
- Matching save read/write and integrity evidence from permitted source or static
  inspection. Different file sizes need the full native layout rather than a
  guessed padding adjustment. Similar sizes need positive title/revision evidence.
- For Japanese/European PS2 XL, an original export retaining all directory
  entries and padding, plus controlled gameplay pairs for that exact product.
  Archive conversion alone does not prove console-native export metadata.
- For a claimed Windows Hyper or Orochi Z localized variation, a second native
  save and matching build first; only then compare serialization and integrity
  against the qualified existing adapter. Reuse is preferable if compatibility
  is independently proved.

No downloaded binary was executed, and no player saves, identifiers, extracted
assets or third-party source copies were added to the checkout. This document
records source review and blockers; it introduces no offsets, guessed natural
caps, adapter registration or new file/game-load test result. Existing genuine
roundtrips and author-reported game acceptance remain attributed in their
original format documents. This investigation performed no edited game load.
