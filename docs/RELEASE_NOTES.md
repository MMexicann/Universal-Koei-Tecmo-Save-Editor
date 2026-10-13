# Universal Koei Tecmo Save Editor v2.0

The library grows from **76 to 90 game/platform profiles across 15 platforms**.
This release includes the 14 profiles previously prepared on main, deeper
editing controls and fixes to existing editors.

New game/platform profiles:

- **PS3:** One Piece: Pirate Warriors 1, 2 and 3; original Dynasty Warriors 8;
  Bladestorm: The Hundred Years’ War.
- **Vita:** Dynasty Warriors 8 Xtreme Legends Complete Edition;
  Attack on Titan / A.O.T. Wings of Freedom.
- **Windows PC:** original Atelier Ryza; Atelier Firis;
  Blue Reflection: Second Light.
- **Classic platforms:** Bandit Kings of Ancient China on Macintosh;
  Nobunaga’s Ambition on NES; Gemfire on NES and SNES.

Existing-editor improvements:

- **Nioh 3:** 14 more named ordinary consumables, bringing the total to 32.
- **Sophie 2 PS4:** 14 more named ordinary materials, bringing the total to 23.
- **Three Hopes:** reduce existing material stocks across nine categories.
- **Project Zero PS2:** reduce existing film stocks while retaining one sheet.
- **Firis PC:** inspect active inventory capacities; quality controls respect
  the active basket/container bounds.
- **DW8 PS3:** fixed the Inspect Data crash.
- **Gundam PS3:** detects changed source/companion files during copied-save
  backup, saving and restore.
- **Shared editors:** record selection, pending-only filtering, hidden-edit
  counts and retained focus/scroll; Max restores exact higher opened values
  after reductions. Bulk actions continue to respect field exclusions.
- **Library:** related regional titles and editions share series filters,
  including Fatal Frame / Project Zero and Fire Emblem.

Controls remain specific to each listed edition and platform. See the
[supported-game inventory](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/v2.0/docs/SUPPORTED_GAMES.md) and
[profile evidence](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/v2.0/docs/SOL_EXPANSION.md) for exact scope. PS3/Vita exports still
need the documented external import/signing workflow. Edited saves have not
been loaded/re-saved in the games during this update.

Download **UniversalKoeiTecmoSaveEditor-v2.0.exe** for the standalone Windows app,
or the **Windows ZIP** with the same executable and documentation. No Python
installation is needed.
