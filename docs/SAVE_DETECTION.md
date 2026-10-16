# Find installed games and import their saves

**Find Your Saves** reads Steam installation metadata and locates candidate saves
for a small, explicit catalogue of supported Windows PC editions. It does not
search every disk or guess a game by trying parsers until one accepts a file.

1. Leave the Steam installation blank to use detected Windows registry/install
   locations, or choose a custom Steam installation/library folder.
2. Select **Discover supported saves**. Libraries listed in `libraryfolders.vdf`
   are included. Search or filter the returned game/save records.
3. Select **Import selected copy** for a qualified result and choose a separate
   destination folder. The app creates a uniquely named subfolder, copies the
   unchanged bytes, validates the actual new files and opens that copy through
   the existing editor. Backups, editing, Review Changes and Undo then operate
   through that editor's normal workflow.

Discovery is read-only for originals. It never changes Steam metadata, synchronizes
Cloud, repairs a file, moves a save, or backs up into a live folder. Temporary
captures are removed after qualification. Explicit imports remain separate files.
Cancellation or a failed read-back may retain a newly created import folder;
the app never deletes a path that another process might have replaced.

## Interpreting the results

| Status | Meaning |
| --- | --- |
| Ready to import | A captured copy passed the selected native parser, existing field qualification and exact unchanged serialization. Source/context fingerprints will be checked again on import. |
| Installed · no located save | A supported app manifest and ordinary install folder were found, but no matching ordinary save was found in enabled locations. This does not mean the player has never saved. |
| Not qualified | The located input failed native validation or could not be captured safely. Foreign editions, unsupported revisions, corruption, changed files and missing original context remain rejected. No other parser is tried. |
| Choose one installation | Conflicting ordinary installations of the same app were found. Choose one library explicitly before trying again. |

The version column reports a parser's native revision when available, otherwise
it says the explicit native profile was qualified. Installed-game identity is
separate from compatible-save evidence. A successful import does not establish
an edited save's in-game load/re-save behavior.

## Enabled location hints

These are curated factual references, not an imported third-party catalogue or
new game support. All files must independently pass this project's owning parser.
Steam Cloud Remote Storage candidates are restricted to the profile's exact
Steam app ID and reviewed filename/extension patterns.

| Game/profile | Steam app | Windows Documents location hint |
| --- | --- | --- |
| Dynasty Warriors 8 XL (`dw8xl`) | [278080](https://store.steampowered.com/app/278080/) | `TecmoKoei/Dynasty Warriors 8/Savedata/save.dat` |
| Dynasty Warriors 7 XL Definitive (`dw7xl`) | [968790](https://store.steampowered.com/app/968790/) | `KoeiTecmo/Dynasty Warriors 7 DX/Savedata/save.dat` |
| Warriors Orochi 3 Ultimate Definitive (`wo3u`) | [1879330](https://store.steampowered.com/app/1879330/) | `KoeiTecmo/WARRIORS OROCHI 3 Ultimate/SAVEDATA/SAVEDATA.BIN` |
| Dynasty Warriors: Origins (`origins`) | [2384580](https://store.steampowered.com/app/2384580/) | Not enabled: conflicting public location references. App-scoped Remote Storage slot candidates only. |
| Samurai Warriors 4 DX (`samurai4dx`) | [2719200](https://store.steampowered.com/app/2719200/) | `KoeiTecmo/SAMURAI WARRIORS 4 DX/Savedata`, native `.dat` candidates |
| Samurai Warriors 4-II (`sw4ii`) | [348470](https://store.steampowered.com/app/348470/) | `KoeiTecmo/SAMURAI WARRIORS 4-II/Savedata/save.dat` |
| Atelier Sophie 2 (`atelier_sophie2`) | [1621310](https://store.steampowered.com/app/1621310/) | `KoeiTecmo/Atelier Sophie 2`, `data.dat` up to two subfolder levels |
| Samurai Warriors 5 (`samurai5_pc`) | [1591530](https://store.steampowered.com/app/1591530/) | `KoeiTecmo/SAMURAI WARRIORS 5/Savedata`, `.bin` candidates up to two levels with their original `steam_autocloud.vdf` |

Location references were reviewed from the public
[Ludusavi manifest](https://github.com/mtkennerly/ludusavi-manifest/blob/a6d44cb992e7b737f5cd3fbeadcee186c028a3df/data/manifest.yaml),
with app identities linked above and filenames/extensions checked against the
existing registered adapters. A path hint identifies where to look, not a save's
edition, integrity or gameplay compatibility. Origins' conflicting Documents
references are deliberately withheld. Use Save Library for separate copies when
automatic discovery has no enabled location for your game.

Steam's conventional Remote Storage path is
`Steam/userdata/<account>/<app ID>/remote`; see
[Steam Cloud documentation](https://partner.steamgames.com/doc/features/cloud).
Auto-Cloud titles may save in Documents instead and need not have a `remote`
folder. The app neither reads `remotecache.vdf` nor interprets account folders as
ownership or sign-in authorization. Console exports, other storefronts, Proton
prefixes and arbitrary unknown games are outside this discovery catalogue.

## Safety and bounds

Live-source capture intentionally has its own read-only ordinary-file check;
the ordinary editor's `safe_path` continues to reject live/Cloud folders and Steam
metadata. No backend receives a live source path. Captured gameplay and required
opaque owner context reach a newly created separate temporary folder before
native validation. Context bytes are only interpreted by the original owning
backend; the discovery layer preserves them exactly and never repairs them.

Checks reject symlinks, linked ancestors, Windows junctions/reparse points,
hardlinked or special files, relative library traversal, UNC/device paths,
ambiguous duplicate KeyValues keys and changed source/context identities. Streaming
reads bind an opened handle to the checked path and recheck path/handle identities,
length and digest. Windows path `st_ctime` and handle `st_ctime` are compared only
within the same API, preserving CPython 3.14 compatibility. Source ancestor
directory identities are retained too.

Limits: 32 Steam roots/libraries, 8 Documents roots, 64 account folders per root,
5,000 directory entries, 256 candidate files, 32 MiB per gameplay file, 64 KiB per
required companion, 1 MiB per Steam metadata file, 128 MiB admitted read bytes and
a 60-second worker budget. Recursive depth is fixed by each reviewed location;
Remote Storage discovery is limited to three subfolder levels. Cancellation is
checked between bounded reads and native qualification steps. Native validation
itself is not interrupted halfway through a parser call.

The scan retains metadata and fingerprints, not gameplay/context bytes. No
telemetry, upload, account lookup, background watching or automatic import occurs.
Local paths shown in the UI stay local.

## Validation

Procedural tests cover Steam KeyValues parsing, extra libraries, explicit app
identity, traversal/duplicate/ambiguous manifests, wrong native input without
fallback, ordinary source capture, unchanged native roundtrip, separate import,
opaque SW5 context, source/context changes, hardlinks/symlinks/FIFOs, cancellation,
budgets, Windows stat API differences and real Tk worker/import behavior.
Copied-native audits, when available, are separate from these generated fixtures
and do not establish gameplay loading. No native files or owner metadata are
included in the repository or release archives.
