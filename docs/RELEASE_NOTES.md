# Universal Koei Tecmo Save Editor v2.1

## Experimental values above supported limits

- Start with normal supported limits; enable experimental editing per open
  session after acknowledging that larger values may break the save or game.
- See supported maxima and separate encoding limits. Save As warns again for
  pending values above the supported range.
- DW3 Remastered supports experimental officer stats, normal item values,
  elixirs, Bodyguard Merit and existing normal weapon bonuses.
- Other game/platform editors apply this to their mapped numeric fields where
  the native encoding permits it. IDs, choices, flags, references and required
  structure remain constrained. Max keeps supported limits.
- Keep backups, Undo, Review Changes, native integrity and actual saved-value
  read-back. Opening a new copy resets experimental mode.

## More games and shared refinements

The Windows app now includes **90 game/platform profiles across 15 platforms**.
The 14 additions since v1.91 cover nine additional titles and new platform
editions, including Gemfire NES/SNES, Bandit Kings Macintosh, Nobunaga NES,
Bladestorm PS3, Firis PC, Second Light PC, original Ryza PC, DW8 XL Vita,
Pirate Warriors 1–3 PS3, original DW8 PS3 and Attack on Titan Vita.

Record navigation, pending-only filters, hidden-edit counts and scroll/focus
retention improve large editors. Shared fixes protect staged values, Max,
loadouts and console companion metadata during writing/read-back.

Download **UniversalKoeiTecmoSaveEditor-v2.1.exe** for the standalone Windows app,
or extract the complete Windows ZIP and launch the EXE inside its versioned
folder, keeping `_internal` beside it. No Python installation is needed. The
Source ZIP is for contributors. Console export/reimport and external resigning
requirements remain. The release pipeline scans both Windows builds before
startup and the final EXE and ZIPs with active Microsoft Defender; the published
`DefenderScan-v2.1.json` binds those results to the exact downloads and commit.

Experimental in-game loading is unverified. Read
[experimental scope and exceptions](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/v2.1/docs/EXPERIMENTAL_EDITING.md) and the
[supported inventory](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/v2.1/docs/SUPPORTED_GAMES.md) for exact available controls.
