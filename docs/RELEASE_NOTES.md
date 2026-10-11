# Universal Koei Tecmo Save Editor v1.71

Three additional editors and a DW5 Special compatibility fix bring the library
to **51 game/platform profiles across nine platforms**.

- **Dynasty Warriors 5 Special — Windows:** fixed opening compatible native saves that previously showed “Unsupported Windows DW5 Special revision.”
- **Atelier Ryza — original Nintendo Switch:** edit existing ordinary item and equipment quality from 1–100; search inventory, equipment and trait records.
- **Dynasty Warriors 8: Xtreme Legends — US PS3 PSN:** edit gold, gems, facility/weapon materials, officer stats, weapon-action aptitudes and existing weapon attribute ranks. Open the extracted `APP.BIN` with its original `PARAM.SFO`; use Apollo for reimport/signing.
- **Dragon Quest Builders 2 — Steam PC:** reduce existing named medicine and seed stacks; search pockets, the bag and player/equipment status. Open a copied `CMNDAT.BIN` from the original save slot.
- **Faster checks:** the complete regression suite now runs in parallel, reducing Windows test waiting by about 83% in the measured comparison.

Light/Dark themes, backups, Undo, Review Changes and safe Save As remain available.
Download the standalone **UniversalKoeiTecmoSaveEditor-v1.71.exe**, or the
**Windows ZIP** containing the same app and user documentation. No Python
installation is needed. From source, install with `python -m pip install -e .`
and run `python -m koei_editor`.
