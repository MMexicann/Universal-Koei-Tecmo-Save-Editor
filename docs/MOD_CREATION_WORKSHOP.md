# Mod Creation Workshop

The Koei Tecmo Mod Creation Workshop is available from the application library.
It helps create project metadata, register user-provided replacement files,
declare dependencies, check a compatibility context and build a verified ZIP.

## Projects and replacement files

Project templates create empty folders for general, texture or audio
replacements. They do not include game files. Add replacement files that you
created or are allowed to redistribute inside the project, then enter their
destination paths from public modding documentation. The workshop does not
browse game installations, inspect archives or extract original assets.

Each replacement records its project-relative source path, target path, SHA-256
digest, license and rights declaration. Permissively licensed files also need
attribution. These rights statements come from the project author and are not
independently verified. Changed, missing, linked or out-of-project source files
fail validation.

## Dependencies and compatibility

Dependencies use a lowercase mod ID and `*` or comma-separated semantic-version
comparators, for example `>=1.2.0,<2.0.0`. Optional missing dependencies produce
a warning; missing required dependencies and incompatible installed versions
are errors.

Compatibility checks compare the project with the game ID, game version or
range, platform and installed mod versions entered by the user. The workshop
does not query an authoritative game or mod catalog. A passing report records
that entered context; it does not establish that the game will load or run the
mod.

## Verified packages

The builder writes a deterministic ZIP containing `mod.json`,
`verification.json` and only the replacement files listed in the manifest. The
manifest stores archive-relative source references. Package verification
checks metadata, safe paths, declared file membership and every replacement
SHA-256 digest. Replacement bytes are streamed into the package and the
verifier streams them again, with a 256 MiB per-file limit and a 1 GiB total
uncompressed limit.

The ZIP is a generic workshop container. Game-specific loaders may require a
different installation layout or additional format conversion. Package
verification does not run a game, inspect executable files, test in-game
behavior or independently verify rights declarations. Do not package original
game files or extracted game archives.

**Export for Mod Manager…** creates a separate, reviewed manager-compatible ZIP
for the explicitly supported Nioh 2 and Nioh 3 PC layouts. It reuses the manager's
actual package inspector and preserves the generic builder. See the
[Workshop-to-Manager guide](MOD_WORKSHOP_MANAGER.md) for required targets,
dependency limits, headless commands and review-token protection.
