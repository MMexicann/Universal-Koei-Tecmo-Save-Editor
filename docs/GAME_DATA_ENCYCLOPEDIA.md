# Game Data Encyclopedia

## Desktop browser (development source)

Open **Editing and Research → Game Data Encyclopedia**, or search for the tool
with **Ctrl+K**. The desktop workspace runs on Windows and Linux. It searches
the bundled reference records without opening a save or contacting a website.
Filter by exact game/platform profile and record kind, then search a name,
native ID, edition or summary. Multiple search words must all match.

Select a row to read its edition, scope, attributes, source-backed relationships
and field-level provenance. The details include source URLs, pinned revisions
or access dates, attribution and licenses. Search and selection never turn a
reference value into an editable save field. The reviewed source descriptions
retain their original language when the application language changes.

The published Toolkit 1.0 contained the reference feed only; this desktop
browser is a follow-up development feature until a new binary is published.

## Bundled reference feed

The repository bundles an edition-scoped JSON reference feed at
`src/koei_editor/data/game_data_encyclopedia.json` as a data contract for search
and comparison surfaces. Its initial coverage is intentionally narrow: exact
native ID/name mappings for Three Hopes Switch characters and weapons; Hyrule
Warriors Wii U materials, weapons, and skills; and three short, source-linked
Hyrule Warriors mechanics summaries. It does not claim complete character,
item, skill, equipment, or gameplay coverage.

## Coverage and limits

The Three Hopes portion contains 68 character mappings and 150 weapon mappings.
The Hyrule Warriors Wii U portion contains 77 materials, 147 named weapons,
and 48 named skills from its existing catalog, plus three paraphrased summaries
of weapon skill and Adventure Mode mechanics. Six reserved or unknown weapon
labels and the blank skill label are omitted from player-facing entities. These
exact catalog rows are excluded:

| Kind | Native ID | Catalog label |
| --- | ---: | --- |
| Weapon | 60 | `[unknown weapon]` |
| Weapon | 109 | `*** Ganon's Rage (Ganon) RESERVED, DO NOT USE ***` |
| Weapon | 110 | `*** Cucco's Spirit (Cucco) RESERVED, DO NOT USE ***` |
| Weapon | 150 | `Unknown (Unk - Unk Level 1)` |
| Weapon | 151 | `Unknown (Unk - Unk Level 2)` |
| Weapon | 152 | `Unknown (Unk - Unk Level 3)` |
| Skill | 0 | `(blank)` |

Those IDs are intentionally absent; other catalog IDs remain unchanged. Each
mapped entry carries a stable feed ID, catalog position/native ID, exact
registered profile edition label, and source reference for each fact. Catalog
names identify records in the mapped format; by themselves they do not
establish ownership, unlock state, playability, or a complete progression model.

The shared validator in `koei_editor.shared.game_data_encyclopedia` checks the
schema version, profile edition, unique IDs, field-level source/license
metadata, and any explicit same-edition cross-references. Cross-references are
omitted unless a source documents the relationship. Consumers should pass
explicit `game_id` and entity IDs when linking records; a displayed label alone
is not a stable key.

## Schema version 1

The JSON envelope has `schema_version`, `dataset_license`,
`dataset_license_note`, `sources`, `games`, and `entities`. `dataset_license`
names a uniform license when one applies to the full feed, or is
`source-specific` for this mixed-license feed. A source carries `id`, `title`,
`uri`, `license`, `license_uri`, `attribution`, `scope`, and at least one pin:
`revision` or `accessed_on` (or both). New scoped source rows may also declare
applicable `game_ids` and machine-readable `claim_scopes`; if `claim_scopes` is
present, `game_ids` is required and both are checked against each fact. These
fields remain optional for older schema v1 source records. License names must
use their canonical license URI (MIT: `https://opensource.org/license/mit`;
CC BY-SA 3.0: `https://creativecommons.org/licenses/by-sa/3.0/`). A game profile
carries `id`,
`title`, `edition`, `platform`, `profile_source_id`, and `scope_note`; title,
edition, and platform mirror the registered profile exactly. An entity carries
stable `id`, `game_id`, `edition`, `kind`, `name`, and `field_sources`, plus
optional `native_id`, `summary`, `attributes`, and `relationships`. The
`field_sources` map relates each fact (including dotted attribute keys) to a
source ID. Each optional relationship has `type`, `entity_id`, and `source_id`;
the validator requires the target to exist in the same game edition.

The Character & Weapon Workshop is a separate editor component. The encyclopedia
browser does not supply new workshop providers or writable mappings. It remains
read-only and does not change registered save-editing support.

## Provenance and license

Three Hopes character and weapon names and numeric IDs are copied from the named facts in
`koei_editor.games.three_hopes.catalog`, which attributes
[`async-amethyst/few2-010-binary-templates`](https://github.com/async-amethyst/few2-010-binary-templates/tree/9b6e9946e5a33e182f80fbe3553e7c2afbebbdcb)
at commit `9b6e9946e5a33e182f80fbe3553e7c2afbebbdcb`. The source is MIT
licensed. Exact game title, edition label, and platform come from the local
profile registry at commit
[`cede8a91a7ce5d150d0b2d88a71120ac02bd821a`](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/blob/cede8a91a7ce5d150d0b2d88a71120ac02bd821a/src/koei_editor/game_registry.py).
The source IDs and their license declarations are also embedded in the JSON
feed, and each mapped field refers to its source ID.

Hyrule Warriors Wii U material, weapon, and skill names and IDs come from the
repository's `koei_editor.games.hyrule_warriors.catalog`, attributed to
[`MarcRobledo/savegame-editors`](https://github.com/MarcRobledo/savegame-editors/tree/b4db8cd11157c6d5ae54a0a5edc88dba82aebe9d)
at commit `b4db8cd11157c6d5ae54a0a5edc88dba82aebe9d`, under MIT. The exact Wii U
title, edition and platform come from the registry in the `1d86de1b78195d873a59bffb2c1de20befe6c473`
base commit.

The Hyrule Warriors mechanic summaries are paraphrased from the pinned Koei
Tecmo Wiki revisions [Weapon Skills (Hyrule Warriors)](https://koeitecmo.wiki/wiki/Weapon_Skills_(Hyrule_Warriors)?oldid=525135)
and [Adventure Mode (Hyrule Warriors)](https://koeitecmo.wiki/wiki/Adventure_Mode_(Hyrule_Warriors)?oldid=513185),
accessed 2026-10-22. The page contributors are credited in each source record;
the pages state that their text is available under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
These paraphrased summaries are adaptations distributed under that same
license.

The feed contains text facts only. It does not redistribute game assets, images,
save files, restricted catalogs, or upstream template implementation code.
Each source-specific MIT permission notice is retained for redistributed names
and IDs.

### FEW2 source MIT notice

> Copyright (c) 2022 SilentLuna
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in
> all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

### Hyrule Warriors source MIT notice

> Copyright (c) 2017-2023 Marc Robledo
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in
> all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

The `dataset_license: source-specific` marker avoids applying either license
to every row. The source record attached to each fact supplies the applicable
license and attribution.

Automated checks compare every bundled mapping with the source catalog and
reject duplicate identities, missing provenance, unsupported licenses, edition
mismatches, and unresolved or cross-edition links.
