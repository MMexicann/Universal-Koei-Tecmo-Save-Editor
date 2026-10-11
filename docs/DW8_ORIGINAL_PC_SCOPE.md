# Dynasty Warriors 8 original-edition Windows PC qualification

No distinct **original-only Windows PC** Dynasty Warriors 8 edition or native
save format was qualified in this investigation. No additional adapter or
library card is registered. The existing `dw8xl` adapter remains explicitly
Dynasty Warriors 8: Xtreme Legends Complete Edition; its offsets, headers,
integrity and limits are not presented as original-edition support.

## Edition evidence

| Product / public name | Qualification result |
| --- | --- |
| Dynasty Warriors 8 / Shin Sangoku Musou 7, original release | Koei's [original-title history](https://www.koeitecmoamerica.com/smusou25th/us/history/titles/smusou_07.html) lists the Japanese PlayStation 3 release. This is distinct from its XL title page; the original Xbox 360 editor below is console evidence. Neither establishes a native Windows original-only edition. |
| Dynasty Warriors 8: Xtreme Legends Complete Edition / Shin Sangoku Musou 7 with Moushoden | Koei's [XL/with Moushoden history](https://www.koeitecmoamerica.com/smusou25th/us/history/titles/smusou_07m.html) includes PC. [Steam app 278080](https://store.steampowered.com/app/278080/) is explicitly XL Complete Edition. Koei's [Taiwan XL site](https://www.gamecity.com.tw/smusou7m/) announces the Windows release within the XL product, rather than a new original-only product. These regional names do not establish another native format. |
| Shin Sangoku Musou 7 with Moushoden DX / Dynasty Warriors 8: Xtreme Legends Definitive Edition, Microsoft Store | Koei's [Windows catalog](https://www.gamecity.ne.jp/products/win.htm) separately names DX for Microsoft Store and with Moushoden for Steam. DX remains an XL compilation edition. No distinct Microsoft Store fixture or executable revision was qualified here, so save compatibility is not inferred from naming or a common `save.dat` filename. |
| Dynasty Warriors 8 Empires | A separate game, already tracked in [Dynasty research](DYNASTY_RESEARCH.md). It is not an original-edition substitute. |

The absence of an original-only PC adapter is an edition-scope result, not a
claim that the original game's content is absent from XL Complete Edition.

## Editor and save-source checks

- [Van's “Dynasty Warriors 8 Editor – PC ONLY” forum](https://www.tapatalk.com/groups/koeiwarriors/van-39-s-dynasty-warriors-8-editor-pc-only-t17450.html)
  uses shortened DW8 naming and discusses the `357` editor, LINKDATA editing
  and opening a Documents save. A title abbreviated in a forum is insufficient
  proof of an original-only PC product or distinct serialized layout. The
  [Steam editor discussion](https://steamcommunity.com/app/278080/discussions/0/515212956469866001/)
  identifies the same tool in the XL Complete Edition community. No editor
  executable was launched or incorporated.
- [XPG's original DW8 save-editor thread](https://www.xpgamesaves.com/threads/dynasty-warriors-8-save-editor-xbox-360-mod-tool.95251/)
  explicitly targets Xbox 360 and requires console-container extraction,
  reinjection and rehash/resign. It supplies no native-PC qualification. This
  console format belongs to the separate legacy-console lane.
- [Nexus “DW8XL Saves”](https://www.nexusmods.com/dynastywarriors8/mods/24)
  describes saves for Xtreme Legends. Its folder called “Original” is described
  as the author's last save, not a product edition. The page also lists Windows
  and Microsoft Store destinations, without independently proving native
  compatibility. Its files require Nexus access and have restrictive
  modification/distribution permissions; none were acquired or modified here.
- [koko-tsuu/dw8xl_save_converter](https://github.com/koko-tsuu/dw8xl_save_converter/tree/8ca795108a4f4f0bee91c55d3efce0c6da78515f)
  explicitly targets XL saves. Its published native PC fixture was downloaded
  to private storage and inspected using this project's existing backend.
  It is the same upstream fixture already cited by
  [DW8 compatibility research](DW8_COMPATIBILITY.md), not a newly independent
  player or an original-edition sample. No converter code was copied or run.

## Native-file validation and exact remaining inputs

The pinned converter PC fixture is 753,481 bytes. Its decoded five-byte identity
is `f0 27 02 19 09`, one of the existing XL adapter's qualified identities.
The backend accepted both native integrity layers and reproduced the complete
input byte-for-byte with no edits. This confirms the downloaded lead belongs
to the existing qualified XL scope; it does not establish a new original
edition, another region/build or a game-load/re-save test.

| Area | Result / exact input needed |
| --- | --- |
| Original-only Windows edition | No qualified product. Reopen only with an identifiable official Windows product/build and a genuine untouched save created by that product. Console exports, renamed XL saves, community shorthand and runtime trainers are insufficient. |
| Original-only framing, identity and native integrity | No evidence to implement. After product qualification, need native reader/writer facts or controlled unchanged save pairs establishing length, revision, cipher and checksum coverage independently. |
| Currencies, stats/EXP, skills/proficiency | No original-PC records qualified; existing XL field evidence is not imported. Need corresponding native records, displayed values, legitimate bounds and one-action before/after samples. |
| Weapons/attributes, equipment/inventories, mounts/companions | No original-PC ownership/equip/acquisition map qualified. Need populated records and controlled acquisition/equip pairs; no manufactured records or borrowed XL maxima. |
| Relationships, customization, exploration and collections | No original-PC system schema qualified. Need evidence that each system exists in that edition plus controlled native samples and reward/prerequisite mappings. |
| Microsoft Store DX compatibility | Separate XL edition question. Need an untouched actual Microsoft Store DX save with labelled build/region, and native structure/integrity proof before widening the existing adapter. No compatibility claim is added here. |
| Actual game loading | Not performed; requires the identified Windows game and disposable save-owner context. |

No source-copy saving, backup, Undo, Review Changes, themes or shared GUI behavior
changed during this scope check. Player files, downloaded external content and
private qualification records remain outside Git and release assets.

## Separate original US PS3 retry

The [original PS3 PSN NPUB31234 player export](https://bucanero.github.io/apollo-saves/PS3/NPUB31234/)
was acquired separately and its console PFD wrapper decoded privately. The
native `APP.BIN` is **665,767 bytes (`0xA28A7`)**, begins `13 01 13 00`, and
uses a different big-endian layout from XL. Its original metadata identifies
`NPUB31234-SAVEDATA`. The
[published original PS3 patches](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31234.savepatch)
identify gold at `0xBD`, resource candidates and officer/weapon record groups.
They perform direct writes without an explicit native integrity update.

This is useful native-input qualification, not a completed editor. Console
PFD signing alone does not establish that all game-internal integrity is
absent or updated. A matching complete native reader/writer, or a credible
controlled edited-load/re-save workflow covering those writes, is still needed.
The published XL byte cipher/checksum has fixed XL framing and must not be
applied to the original game's plaintext data. The broad original patch's
100 officer slots also exceed the original game's 77 playable officers; those
extra entries are not evidence of additional playable characters or safely
editable progression. No original-PC product, console writer or supported
library card is inferred from this separate console export.
