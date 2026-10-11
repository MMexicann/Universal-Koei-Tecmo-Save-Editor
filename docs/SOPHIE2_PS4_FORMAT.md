# Atelier Sophie 2 — PlayStation 4 CUSA28451

This adapter opens copied `data.dat` gameplay exports with their original
`sce_sys/param.sfo`. The qualified native profile is CUSA28451, outer revision 2,
app 1.0. It edits existing named ordinary-material quality as reductions and
remaining uses on existing battle items within each record's saved capacity.
Inventory, equipment, Party levels/EXP, alchemy and serialized systems are
searchable. Reimport/signing remains external to this application.

## Native identity, integrity and writer

The complete public
[Apollo gameplay archive](https://github.com/bucanero/apollo-saves/blob/master/PS4/CUSA28451/00000001.zip)
is identified by its original SFO and archive listing as clear data / NG+.
Its gameplay `data.dat` is 301,104 bytes, decoding to 629,622 bytes. The separate
4,304-byte system save is not a gameplay substitute and is rejected.
The file passes every native Gust cipher/compression/XOR/sum checksum gate in the
existing attributed Sophie 2 codec. Direct canonical re-encoding of the complete
unchanged native payload, header, seed and footer is **byte exact**. Edited output
is fully decoded and compared with the intended payload before publishing a copy.
No truncation, tail padding, damaged-input repair or checksum bypass is used.

The same-game record and writer facts come from the MIT-licensed
[Sophie2SaveEditor model, commit 93d8070](https://github.com/Tartarshia/Sophie2SaveEditor/blob/93d807072a852c73799394af4d32fb164841cd3e/sophie2_model.py),
`ItemRecord`, inventory readers, `set_quality` and `_set_item_details` (current
uses and saved capacity), and its complete
codec writer. Their packed records match this native export, but PC tagged
scalar/array assumptions are **not** imported: PS4 span headers are LE32, tagged
scalar values and array byte lengths are BE, while packed 44-byte item fields
remain LE. Character identities are BE32, with IDs 0–5 and four `-1` unused
records; the PC source's shorter six-record array is not accepted here.

Complete root order/lengths, all packed pool extents and native app/item/Party
revisions are gated. There are 36 complete named roots ending exactly at 629,622:
`info`, `PlayGo`, `dlc`, `event`, `knowledge`, `money`, `party`, `fieldmap`,
`friend`, `library`, `item`, `time`, `event_check`, `date`, `global`, `mix_lv`,
`explore_equip`, `bonus`, `system`, `dlcbgm`, `shop`, `mix_recipe`, `achievement`,
`barQuest`, `collectData`, `costume`, `secret_base`, `battlescore`, `lambRoast`,
`weaponskin`, `record`, `RecipeIdea`, `ability`, `worldmap`, `party_quest`, `summary`.
The parser contains the full exact per-root size profile. Extra envelope bytes,
foreign titles/revisions, malformed names, duplicate nodes, shifted pools,
checksum corruption and incomplete arrays are rejected.

## Item qualification and mechanics

The official [Synthesis Basics manual](https://www.koeitecmoamerica.com/manual/sophie2/en/5100.html)
distinguishes ingredients' components, final quality, effects, recipe prerequisites
and links/assist skills. Quality changes do not invent recipes or effects.
Only nine separately checked ordinary-material identities are writable: Drinking
Water, Crackling Water, Blessed Sap, Red/Blue/Green/Yellow/White Flower and Tall
Taun. Their numerical identity facts are independently transcribed from the
[public same-game item mapping](https://fearlessrevolution.com/viewtopic.php?t=19323).
No external catalogue or CT file is bundled. All other IDs remain searchable
numeric inspection records until separately qualified.

The actual native standard container has 9,999 44-byte records. A writable named
material must already exist, have quality 1–999, zero saved stat bonus bytes,
uses/capacity 1/1, a unique occupied LE16 instance identity and no equipped
instance reference. Duplicate occupied identities stay read-only in every pool
and equipment record. Only its LE16 quality at
record `+6` can decrease, with the original opened value as its ceiling. Max does
not modify it; 999 is an admission/editing limit, not an asserted natural cap.
An existing consumable or equipped battle-item record from nineteen separately
checked named identities can change its byte
`+0x24` only between zero and its unchanged saved capacity at `+0x25`, if that
capacity is positive and current uses are consistent. Equipment quality, item
identity, instance IDs, traits, effects, stat bytes and capacity remain untouched.
The genuine clear-data export yields 464 named material fields and 21 qualified
battle-item-use fields; field counts legitimately depend on existing records.

## Coverage and remaining dependencies

| System | Implemented or precise blocker |
| --- | --- |
| Ordinary materials | Named quality reductions for the nine qualified identities; remaining IDs need independent item-kind/semantic mapping. |
| Existing battle items | Remaining uses within native stored capacity; no item creation, capacity increase or skill/effect change. |
| Equipment / gathering / adventure tools | Searchable existing quality/traits/effects/uses; equipment stat derivation and tool/story uniqueness remain read-only. |
| Cole | Inspect only: native BE wallet and LE outer header preview are coupled; an exact full writer for both is required before a wallet action. |
| Characters and alchemy | Named Party levels/EXP and Sophie/Plachta alchemy values inspect only; growth thresholds and coupled progression are unqualified. |
| Components, traits, effects, catalysts, recipe ideas | Preserved; legal compatibility/prerequisites and original PS4 field semantics are required before edits. |
| Weather/dream worlds, quests, bonds, collections, shops | Native sections searchable; progress/reward/history dependencies require controlled native action pairs. |
| Story/ending/NG+ | Preserved separately from items/resources; no completion/unlock actions. |

Whole unchanged original SFO bytes are opaque and their SHA-256 binds source,
Save As destination, backup/restore and private copied-save diagnostics. Only
public title identity is interpreted. Metadata/account bytes are never displayed
or embedded in Review Changes or backup manifests. Automatic original-byte
backups, Undo, Review Changes and atomic new-file saving are retained.

Checks distinguish procedural sparse fixtures from the genuine export: exact
canonical/no-op native reconstruction, every writable field's surgical mask,
one combined encrypted edit/readback, strict malformed/foreign rejection,
unknown/higher-value preservation, forged snapshots, source/metadata races,
backups/restore and actual native Tk Open/Search/Apply/Undo/Review/Inspect/Light-
Dark/Save As/Restore. **Edited in-game load/re-save validation has not been
performed.** This does not expand the published PC1.08 profile or imply Switch
support.
