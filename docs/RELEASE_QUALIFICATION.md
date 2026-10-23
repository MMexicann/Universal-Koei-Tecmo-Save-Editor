# Toolkit 1.0 release qualification

Toolkit 1.0 continues Save Editor v3.1 under the **Universal Koei Tecmo Game
Toolkit** name. The version reset preserves the repository, historical releases,
existing save profiles, preferences and legacy command.

## Contribution review

On 2026-10-23, the project owner explicitly confirmed that all other development
agents had finished and that no other agent work remained active. This resolves
the completion gate; a count of pull requests is not used as a substitute for
that confirmation.

The reviewed contribution inventory covers PRs **#110–#150**: 39 merged changes,
#112 closed as superseded by the stronger integration in #146, and the
unqualified PS4 transfer proposal in #110 excluded from 1.0. Supporting changes,
follow-ups and research submissions are included in that inventory; they do not
represent 41 distinct assignments.

PR #110's proposed original-SW4 PS4 gold word at `0x7842` lacks an independently
verified controlled gold-change pair or equivalent game-readable evidence.
Copying that candidate value into a PC save does not prove its PS4 meaning.
The raw proposal also contains a separately identified companion-backup race.
Its new route and PS4 source adapter are not shipped. The useful, independent
PC serializer correction is retained: assigning an exact opened value preserves
unusual balances and locked-officer flags without bypassing validation of new
values. The route inventory stays at **145**, rather than 146.

## Compatibility and evidence

- **98 save game/platform profiles across 15 save platforms** remain registered.
  Research editions do not add editing support. See [the exact catalog](SUPPORTED_GAMES.md).
- The three supported Arland DX PC configuration profiles are separate from save
  editing. Nioh 3 equipment details remain read-only inspection values.
- Mod Manager's documented Nioh 2 PC method requires an existing loader. Nexus
  API access remains gated; website links are available.
- Controller profiles store local records. Windows Troubleshooting folder scans
  report unavailable evidence. Neither feature silently applies native settings.
- The distributed application runs on Windows. Save Vault and Playthrough
  Profiles also require Windows when run from source because their filesystem
  operations depend on held native directory handles.

Procedural format tests, copied genuine-file checks and actual game loading are
different evidence classes. Passing checksums, unchanged roundtrips or output
readback does not prove that edited or converted files load and re-save in the
game. That game-load qualification remains unverified; see
[validation](VALIDATION.md) and [compatibility limits](../README.md#compatibility).

## Required release checks

The console CLI reuses existing validated copy, conversion and automation engines.
Catalog filters retain full versus filtered counts without changing support scope.
GUI and CLI diagnostics share a bounded metadata-only report; Game Hub reports
omit local paths and notes and retain partial-scan evidence. Their explicit report
exports use one identity-bound, no-replace publisher and never overwrite a file.

The official workflow runs the complete isolated Windows test suite and verifies
the combined shard coverage and source fingerprints. Fresh release-source checks
are required after version, CLI or packaging changes; an earlier integration
run does not qualify a different source tree.

Qualification covers the portable application, standalone GUI EXE and standalone
CLI, including bounded startup, complete runtime resources, privacy checks and
required license notices. Active Defender scans cover the runtimes and all four
exact payloads: GUI EXE, CLI EXE, portable ZIP and source ZIP. The published
`DefenderScan-v1.0.json` binds those bytes to the tested source commit;
`SHA256SUMS.txt` covers the downloads and scan report. The workflow verifies
those bindings again before publication. See [building and release](BUILDING.md).

## Licensing and history

An independent notice audit matched every license member in the exact pinned
miniaudio, trimesh, NumPy, cffi, pycparser and PyInstaller wheels to retained
notices, allowing only whitespace differences. This includes 20 NumPy wheel
license-file members and the PyInstaller bootloader exception. The libffi MIT notice and
adapted-code notices remain required in both frozen application forms and the
CLI. Research references do not authorize importing restricted implementations,
game assets, player saves or account metadata; those remain outside the release.
See [third-party notices](THIRD_PARTY_NOTICES.md).

The historical `v1.0` tag is preserved. The new product uses **`toolkit-v1.0`**,
with application version **1.0**. Release verification must match that tag, the
tested source commit, exact asset list and recorded hashes.
