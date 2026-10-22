# Koei Tecmo RPG and adventure editor expansion audit

Date: 2026-10-22
Repository baseline: `main` at `1d86de1` (game-data encyclopedia feed, PR #113).
Purpose: record the verified editor scope, highest-value missing editions, and the evidence needed before adding writes. This is a research report; the only implementation in this workstream is the Project Zero film-label clarification in [PR #115](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/pull/115). No new save-writing operation or game/platform profile was qualified by these audits.

## Family findings

| Family | Registered editing scope reviewed | Missing titles or editions with useful research value | Write blockers and reference |
| --- | --- | --- | --- |
| Atelier | 15 separately scoped profiles: Sophie 2 Steam PC/PS4; Sophie Steam PC; Ryza Steam PC/Switch; Ryza 2 Steam PC/Switch; Ryza 3 DX Steam PC revision 4; Firis Steam PC; Rorona/Totori/Meruru PS3; Escha & Logy EU PS3; Ayesha US/Japan PS3; Meruru Plus US Vita. Existing writes cover selected occupied-item quality, bounded item uses, alchemy EXP, balances, selected base stats and existing gauges. | Rorona DX and Meruru DX PC; Totori DX PC; Lydie & Suelle PC; original Ryza 3 and unqualified Ryza ports/revisions; Sophie DX, Firis DX and Dusk DX. | Exact native title/build framing, integrity and action-specific ownership/prerequisite pairs are missing. The current Ryza 3 DX revision-4 map does not transfer to other builds. See [Atelier research status](ATELIER_NEXT_RESEARCH.md), [Arland DX](ARLAND_DX_RESEARCH.md), [Rorona DX](RORONA_DX_FORMAT.md), [Meruru DX](MERURU_DX_FORMAT.md), [Totori PC research](TOTORI_PC_RESEARCH.md) and [Ryza formats](RYZA_FORMATS.md). |
| Fatal Frame / Project Zero | European Project Zero PS2 SLES-50821: bounded camera-point, upgrade-tier and existing film-stock reductions. Fatal Frame II REMAKE Steam PC revision `0x24121300`: shared system Photo Point reductions. | Original Fatal Frame PS2/Xbox; Fatal Frame II regional PS2, Xbox Director’s Cut and Wii remake; Fatal Frame III PS2; Fatal Frame IV Wii and later remaster; Fatal Frame V Wii U and later remaster; Spirit Camera 3DS; other non-Steam remake builds; original Fatal Frame II US PS2 remains a candidate. | Separate platforms/builds need native identity, framing/integrity, no-op roundtrip and controlled pairs for each write. Original Fatal Frame II PS2 retail field links and dependencies remain unqualified. See [Project Zero PS2](PROJECT_ZERO_PS2_FORMAT.md), [Fatal Frame II Remake](FATAL_FRAME2_REMAKE_FORMAT.md) and [Fatal Frame II PS2 research](FATAL_FRAME2_PS2_FORMAT.md). |
| Blue Reflection | BLUE REFLECTION: Second Light original Steam PC app 1423600: reduce an existing ordinary-container quantity to at least one. Other inventory and gameplay values are inspection only. | Original BLUE REFLECTION, Quartet, Second Light PS4 and Switch. | Original BLUE REFLECTION lacks title-specific integrity/action pairs; Quartet has separate byte order and party geometry; console exports require separate qualification. Coin, TP, equipment, ownership, crafting and story changes need mechanic-specific evidence. See [Second Light PC](BRSL_PC_FORMAT.md) and [Blue Reflection research](BLUE_REFLECTION_RESEARCH.md). |
| Nights of Azure | Nights of Azure 2 original Switch, English Chapter 1/Chapter 7/Clear Data profiles: reduce current Libra within the opened balance. | Original Nights of Azure PS3/Vita/PS4/PC; Nights of Azure 2 PS4/Vita/PC and other Switch regions/builds. | NoA2 Blood, levels, AP, Servan/Lily state, items, quests and rewards remain read-only or unmapped. Exact edition copies, integrity coverage, byte-exact roundtrip and displayed before/after pairs are required. See [NoA2 Switch](NOA2_SWITCH_FORMAT.md). |

The Project Zero label change in PR #115 names four already-mapped slots as Type-14, Type-37, Type-74 and Type-90 film. It changes no writable field, limit, offset, minimum, serializer path or accepted input. The labels are supported by the pinned MIT-licensed [Himuro source mapping](https://github.com/Mikompilation/Himuro/blob/adcc35fb4602726ca9a692f2289bec816ce112db/src/graphics/graph2d/g2d_debug.c#L457-L460); no external implementation or catalog was copied.

## Adjacent Koei Tecmo RPG and adventure coverage

Existing profiles already cover Ar Tonelico Qoga and Trinity PS3, Berserk EU Vita, Attack on Titan 1 EU Vita, Dragon Quest Builders 2 Steam PC/Switch, Persona 5 Strikers PC/PS4/Switch, and Nioh 3 PC. Their field maps and bounds are platform-specific. The strongest uncovered candidates are:

- **Toukiden Kiwami and Toukiden 2:** no registered adapter; exact disk serialization, integrity and partner-file relationships remain unproved.
- **Dragon Quest Heroes I/II and Fate/Samurai Remnant:** no registered adapter; complete native save roles, integrity and gameplay semantics remain unproved.
- **Fairy Tail Switch:** title-block checksums are known, but no writable gameplay field has been tied to a controlled action pair.
- **Berserk PC and Attack on Titan PC editions:** framing leads exist, but title/build identity, gameplay schema, inner integrity and action pairs remain incomplete.
- **Dragon Quest Builders 2 PS4:** qualify the PS4 save/container independently; PC/Switch geometry does not establish PS4 compatibility.
- **Nioh 1/2 PC:** native integrity consumers are unresolved. Published tools that clear integrity flags do not qualify a writer.
- **Persona 5 Strikers:** equipment, growth, ownership, recipes, bonds, story and rewards need separate dependency-aware pairs even where balances and selected stacks are writable.

See the [adjacent-family survey](ADDITIONAL_EDITOR_SURVEY.md), [licensed action RPG status](LICENSED_ACTION_RPG_STATUS.md), [other Koei Tecmo PC research](OTHER_KOEI_PC_RESEARCH.md), [Toukiden Kiwami](TOUKIDEN_KIWAMI_RESEARCH.md), [Toukiden 2](TOUKIDEN2_RESEARCH.md), [Nioh integrity research](NIOH_INTEGRITY_RESEARCH.md) and [Fairy Tail research](FAIRY_TAIL_SWITCH_RESEARCH.md) for detailed profile and evidence notes.

## Open-source reuse review

No additional save-writing implementation was copied in this workstream. The MIT-licensed Sophie 2 implementation was already integrated and attributed in the repository. The MIT Himuro decompilation was used only to verify existing Project Zero film labels. Other checked projects did not qualify a new write: some lacked a usable license, some provided only runtime or cloud-sync tools, and some clear save-integrity flags. DQB2 and Persona 5 Strikers Switch editors are GPL-3.0 sources; Nioh 2 PC tools with Apache-2.0 or MIT licenses do not establish the unresolved native checksum behavior. See [editor source catalog](EDITOR_SOURCE_CATALOG.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

## Validation evidence

These are focused regression checks of current adapters, not proof of newly qualified save fields or edited-game load/re-save:

| Family | Reproducible command | Result |
| --- | --- | --- |
| Atelier | `PYTHONPATH=src python -m unittest tests.test_atelier_sophie2_format tests.test_sophie2_inventory tests.test_sophie2_audit tests.test_sophie_format tests.test_sophie_audit tests.test_firis_pc tests.test_ryza_format tests.test_ryza_audit tests.test_ryza_pc tests.test_ryza3_dx_pc tests.test_ryza_switch tests.test_ryza2_switch tests.test_meruru_plus_vita tests.test_meruru_dx_candidate tests.test_rorona_dx_candidate tests.test_totori_dx_ps4_candidate -v` | 129 passed; 20 skipped because private native saves or a graphical display were unavailable. |
| Fatal Frame | `PYTHONPATH=src python -m unittest tests.test_project_zero_ps2 -v` | 6 passed; 2 skipped because private native exports or a graphical display were unavailable. PR #115 repeats this check for the label change. |
| Blue Reflection | `PYTHONPATH=src python -m unittest tests.test_brsl_pc -v` | 6 passed; 1 skipped because an independently copied native Second Light save was unavailable. |
| Nights of Azure | `PYTHONPATH=src python -m unittest tests.test_nights_azure2_switch -v` | 12 passed; 2 skipped because native copies or a graphical display were unavailable. |

The family audit runs were performed in family worktrees based on `cede8a9`. Current `main` is `1d86de1`; its only changes since that baseline are the separate game-data encyclopedia feed, so the audited family files are unchanged. PR #115 also records a focused rerun, `tools/package_release --verify-only`, manifest refresh and `git diff --check`. No full-suite run or edited in-game load/re-save is claimed here.

## Evidence gate for the next writable field

For every new mechanic or edition, capture an exact game/platform/region/build save copy and an unchanged control; record the displayed value before and after one controlled in-game action; prove complete framing and applicable integrity; establish a byte-exact no-op roundtrip; map record identity, width, encoding, range and ownership/prerequisite dependencies; write only the qualified field and required integrity cells; then reparse and verify the requested result. Test the exact title/build and record game load/re-save separately. Keep currencies, lifetime totals, owned/equipped references, derived stats and rewards distinct. A related title, port, memory trainer, patch offset or synthetic test fixture is not a substitute for that evidence.
