# Completion Companion evidence for Sol

This note maps product claims to implementation and source evidence. Treat each
claim within its listed scope. Do not infer completion states from missing data,
manual notes, or an unrelated save field.

| Claim | Evidence | Scope and limit |
| --- | --- | --- |
| Character, collectible and mission records come from existing opened-save progression views. | [Dashboard coverage and limits](PROGRESSION_DASHBOARDS.md); [shared projection](../src/koei_editor/shared/progression.py); [DW3 projection](../src/koei_editor/games/dw3/progression_dashboard.py) | These are mapped fields from the opened save snapshot. A level, stat, inventory reference or route flag is not by itself proof of a character unlock, campaign completion or total collection. |
| Existing progression comparisons show mapped values side by side. | [Dashboard comparison behavior](PROGRESSION_DASHBOARDS.md#standalone-html-reports); [desktop view](../src/koei_editor/shared/progression_view.py); [report renderer](../src/koei_editor/shared/progression_report.py) | Matching labels and units can be compared. Ambiguous, missing and different-unit values stay separate; comparisons do not produce a game completion score. |
| Provider PR #111 adds an explicitly registered Steam achievement source for DW3 Remastered. | [Official Steam store page](https://store.steampowered.com/app/3841510/DYNASTY_WARRIORS_3_Complete_Edition_Remastered/); [Steam achievements page](https://steamcommunity.com/achievements/3841510); [provider implementation PR #111](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/pull/111) | Steam app `3841510` only; the provider is not present in this branch or current `main` until PR #111 merges. The API requires a user-supplied Web API key and SteamID64; private profiles, API failures or schema mismatch are unavailable. The provider does not infer achievements from save data. |
| The UI displays platform state as verified only with a source identity and canonical UTC retrieval time. | [Completion Companion view](../src/koei_editor/shared/completion_checklist_view.py); [projection tests](../tests/test_completion_companion_view.py) | Unsupported or incomplete source results remain Unavailable. Only explicit provider states `locked` and `unlocked` can be shown as such. |
| Manual checklist entries are user-authored and separate from save data. | [Checklist storage](../src/koei_editor/shared/completion_checklist.py); [manual checklist tests](../tests/test_completion_checklist.py) | Rows are labeled Manual and stored in local `completion_checklists.json`, keyed by the exact game registry ID. A manual checked state is not verified platform or save progress. |

## Rules for AI consumers

- Preserve the source label and retrieval time with verified platform states.
- Treat unsupported, private, malformed, incomplete or ambiguous source data as
  **Unavailable**, never as **Locked**.
- Treat checklist entries as **Manual**, even when checked.
- Do not convert save flags into platform achievements or character unlocks
  unless a game-specific mapping explicitly establishes that meaning.
- Do not invent a denominator, percentage, total completion score or hidden
  state from absent data.
- Do not describe the DW3 Steam provider as support for another game, edition
  or platform.

## Validation evidence

For the Completion Companion branch, 11 focused tests passed and three were
skipped: two require a graphical display, and the registry integration waits
for provider PR #111. Fifteen progression contract, generic projection and game
dashboard regression tests passed. The public source manifest verified 1,188
entries on the branch's current main base; the supported-game inventory check
covered 98 adapters. Provider-specific tests and evidence are recorded in PR
[#111](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/pull/111).

This evidence does not claim an in-game load test, a complete catalogue for all
Koei Tecmo games, or a completion percentage.
