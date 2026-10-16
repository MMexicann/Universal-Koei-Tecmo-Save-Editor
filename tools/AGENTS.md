# Build and maintenance tools

Read the [root guide](../AGENTS.md) and [build instructions](../docs/BUILDING.md).
Run tools as modules from the installed checkout, for example
`python -m tools.build_windows` and `python -m tools.package_release`.

Keep source-manifest paths relative to the repository root and collect qualified
package dependencies/data. Do not weaken archive/privacy validation or include
player saves, game assets/binaries, private reports or personal paths.

Build/check the standalone EXE on Windows before release; Linux checks are
separate. Refresh reviewed manifest entries only after code/docs are stable.
Use `python -m tools.update_supported_games` and `--check` for the registry-derived
source index, README summary and supported-game document.
