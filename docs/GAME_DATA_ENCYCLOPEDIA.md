# Game data encyclopedia feed

The repository now bundles a small, edition-scoped JSON reference feed at
`src/koei_editor/data/game_data_encyclopedia.json`. It is the initial data
contract for future search and comparison surfaces. This seed is intentionally
scoped to the existing Fire Emblem Warriors: Three Hopes Switch profile's
character and weapon native-ID/name mappings. It does not claim complete
character, item, skill, equipment, or gameplay coverage.

## Coverage and limits

The feed contains 68 character mappings and 150 weapon mappings from the
repository's existing Three Hopes catalog. Each entry carries its stable feed
ID, native numeric ID, exact profile edition label, and a source reference for
each fact. The catalog names identify records in the mapped format; by
themselves they do not establish playable status, recruitment, routes, class,
stats, effects, or unlock requirements.

The shared validator in `koei_editor.shared.game_data_encyclopedia` checks the
schema version, profile edition, unique IDs, field-level source/license
metadata, and any explicit same-edition cross-references. Cross-references are
omitted unless a source documents the relationship. Consumers should pass
explicit `game_id` and entity IDs when linking records; a displayed label alone
is not a stable key.

## Schema version 1

The JSON envelope has `schema_version`, `dataset_license`,
`dataset_license_note`, `sources`, `games`, and `entities`. A source carries
`id`, `title`, `uri`, `license`, `license_uri`, `attribution`, `scope`, and
exactly one pin: `revision` or `accessed_on`. A game profile carries `id`,
`title`, `edition`, `platform`, `profile_source_id`, and `scope_note`; title,
edition, and platform mirror the registered profile exactly. An entity carries
stable `id`, `game_id`, `edition`, `kind`, `name`, and `field_sources`, plus
optional `native_id`, `summary`, `attributes`, and `relationships`. The
`field_sources` map relates each fact (including dotted attribute keys) to a
source ID. Each optional relationship has `type`, `entity_id`, and `source_id`;
the validator requires the target to exist in the same game edition.

This checkout does not contain a Character Workshop component, and this feed
does not add a user interface or claim that such integration is already
available. It is packaged as read-only reference data and does not change save
editing support.

## Provenance and license

Character and weapon names and numeric IDs are copied from the named facts in
`koei_editor.games.three_hopes.catalog`, which attributes
[`async-amethyst/few2-010-binary-templates`](https://github.com/async-amethyst/few2-010-binary-templates/tree/9b6e9946e5a33e182f80fbe3553e7c2afbebbdcb)
at commit `9b6e9946e5a33e182f80fbe3553e7c2afbebbdcb`. The source is MIT
licensed. Exact game title, edition label, and platform come from the local
profile registry at commit
[`cede8a91a7ce5d150d0b2d88a71120ac02bd821a`](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/cede8a91a7ce5d150d0b2d88a71120ac02bd821a/src/koei_editor/game_registry.py).
The source IDs and their license declarations are also embedded in the JSON
feed, and each mapped field refers to its source ID.

The feed contains text facts only. It does not redistribute game assets, images,
save files, restricted catalogs, or upstream template implementation code.
Retain the following MIT notice when redistributing the copied names and IDs:

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

Automated checks compare every bundled mapping with the source catalog and
reject duplicate identities, missing provenance, unsupported licenses, edition
mismatches, and unresolved or cross-edition links.
