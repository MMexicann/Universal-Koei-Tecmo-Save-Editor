# Progression dashboards

Open a separate, qualified save copy. **Progression Dashboard** is the first
workspace tab in scalar editors; **Edit Fields** retains the existing editor.
Dynasty Warriors 3 Remastered has a Dashboard tab beside its dedicated forms.

Choose a section, search for a record or value, or select a card. Large inventories
are divided into pages so the interface stays responsive. Selected-record details
show the full metrics beyond the card preview. Follow a linked value to reveal
its mapped editable field. Navigation clears field filters that would hide that
field, but preserves pending edits, Undo history and the original file.

Use the range-status filter to find records with full or unfinished **mapped
metric ranges**, or records without a mapped range. These describe individual
metrics, not whether an officer, weapon or game is complete. Sort by name or
mapped range; pin a record to compare matching, unambiguous metrics with another
record. Values with different units remain separate. The summary ribbon counts
matching records and mapped ranges without inventing an overall completion score.
Light and Dark themes repaint the cards, charts and comparison inspector.

Arrow keys move between cards, Return opens the selected record's fields, and the
record selector provides direct keyboard selection. On short windows, choose
**Filters / report** to reveal the additional controls. The inspector pages
fields separately from the inventory so large records stay accessible.

The dashboard is read only and shows the **opened snapshot**, not a preview of
pending edits. Use Edit Fields and Review Changes for staged values. Save As
refreshes the snapshot from the validated destination copy. Switching sessions,
themes, searches and cards never writes a game save.

## Standalone HTML reports

Choose **HTML report…** from the dashboard, select the sections to include and
optionally select up to four records for comparison. Save to a new `.html` file;
existing reports and saves are never replaced. The exported report contains only
the included display snapshot and its evidence notes, without adding save bytes,
source paths, account metadata or staged changes. Review displayed values before
sharing a report, particularly profiles with user-defined record names.

Open the file in a browser. Search, section and range filters, sorting, paged
cards, expanded metric details and record comparisons work offline. Choose System,
Light or Dark appearance in the report. Comparisons show values side by side;
missing mappings are labelled and unrelated metrics are not summed. If any selected
record repeats a metric label and unit, that comparison row is marked ambiguous;
inspect its individual record values instead of inferring matching fields. Reports keep
all explicitly included records embedded while rendering at most 24 cards per
page. Printing uses the currently displayed page and selected comparison.

The four priority profiles include scoped snapshot overviews. Equipment records
show saved character references where those references are mapped; physical pool
assignment, ownership and equipped state retain their separate meanings. Distinct
weapon-ID counts describe the current inventory, not catalogue completion.

## What the graphics mean

Progress bars require an explicit verified denominator. A storage ceiling or an
editor's permitted range alone does not establish progress. Unusual opened values
remain visible; they are not clamped to make a bar. A filled stat or aptitude bar
is separate from character unlocks, story completion and rewards. There is no
inferred overall game-completion score.

| Profile | Rich dashboard coverage | Interpretation limits |
| --- | --- | --- |
| DW8 XL PC | Officer level/XP/stats, four-star action aptitude, weapon references and populated records, attributes, resources, ally records | Officer names/unlocks, XP thresholds and story completion are not mapped. Physical ally records do not prove recruitment. |
| WO3 Ultimate PC | Level/XP/promotions/stats, weapons and attributes, raw compatibility, item inventory/references, mounts, resources, mapped ownership bars | Numbered officer records are not unlock states. Compatibility has no inferred stars or maximum. Item ownership coverage is separate from rank, equipment and story. |
| Origins | Existing named bonds, occupied weapons/traits, resources, peace and mapped clear history, stored proficiency XP/Battle Arts where qualified | Protagonist level/stats, Old Coins and proficiency-level thresholds are unavailable. Replay clear flags do not establish campaign completion or endings. |
| DW3 Remastered | Named officers, permanent stats/Merit, equipped references and owned weapons, Elixirs where present, individual routes and mapped galleries | Merit is not a computed character level. Route progress and clear flags are distinct. Missing arrays do not become zero-percent collections. |
| Other scalar profiles | Every mapped opened field in native record/category cards, search and direct field links | Generic views do not invent progression denominators or reinterpret a field's meaning. |

Console editions retain their own explicit profiles and mapped generic dashboards
unless a separate rich presentation is provided. A PC dashboard does not expand
console editing support. Native qualification and in-game load/re-save validation
remain separate; no dashboard implies a successful game load of an edited save.

## Optional platform achievements

Steam achievements are a separate source from opened-save records. The
DW3 Remastered Steam mapping uses app ID `3841510`, verified from the
[official Steam store page](https://store.steampowered.com/app/3841510/DYNASTY_WARRIORS_3_Complete_Edition_Remastered/).
The [Steamworks ISteamUserStats API](https://partner.steamgames.com/doc/webapi/ISteamUserStats)
provides the title schema and a player's achievement states. The app requests
those endpoints only after an explicit user action and requires a Steam Web API
key and 17-digit SteamID64 for that lookup. These values stay in memory for the
request and are not saved with preferences, checklists, reports or game saves.

The provider joins player state to the official schema by exact achievement API
name. It displays `unlocked` only for an explicit API value of `1` and `locked`
only for `0`. A private profile, API failure, missing or additional state, or a
schema mismatch is `unavailable`; missing data is never treated as locked.
Hidden achievements use a generic name and omit their descriptions. An unlocked
count and total are shown only when every schema entry has a matching state.
No percentage is calculated. Retrieval time and the `Steam Web API` source stay
with the displayed snapshot; the profile identifier and API key do not.

This mapping does not infer Steam achievements from save flags. DW3's existing
save-backed characters, mission routes and gallery records remain sourced from
the opened save. Other games without an explicit provider display achievement
information as unavailable.

| Claim | Public evidence | Limit |
| --- | --- | --- |
| DW3 Remastered maps to Steam app `3841510` and has Steam achievements | [Steam store listing](https://store.steampowered.com/app/3841510/DYNASTY_WARRIORS_3_Complete_Edition_Remastered/), [Steam achievements page](https://steamcommunity.com/achievements/3841510) | Platform achievements are not read from the game save. |
| Steam provides game schema and player achievement APIs | [Steamworks ISteamUserStats documentation](https://partner.steamgames.com/doc/webapi/ISteamUserStats) | Requires a user-supplied Steam Web API key; player states may be private or unavailable. |
| Save-backed DW3 progression comes from the registered opened-save mapping | [DW3 progression projection](../src/koei_editor/games/dw3/progression_dashboard.py), [save-format evidence](SAVE_FORMAT.md) | A saved flag does not imply a Steam achievement event. |
