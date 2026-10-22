# Game Patch and Compatibility Analyzer

The source-only analyzer compares two immutable install snapshots and an
optional compatibility-requirements document. It reports version changes,
added, removed or changed files, archive entry changes, and supported-format
metadata changes. It can flag a mod, tool or save requirement that no longer
matches the candidate snapshot.

The analyzer does not find installations, read or write game files, manage mods,
or decide compatibility from a file hash alone. The Game Version Tracker owns
installation discovery and snapshot creation. The Mod Manager owns mod
installation state and supplies declarative requirements. Reports describe
evidence and possible impact; they do not certify a game load or save migration.

## Run a comparison

Install the source package once, then run with Python 3.10 or newer:

```text
python -m pip install -e .
python -m koei_editor.shared.game_compatibility baseline.json candidate.json \
  --requirements requirements.json \
  --json-out patch-report.json \
  --markdown-out patch-report.md
```

The two snapshot files are the Tracker's before and after observations for the
same `game_id` and `platform_id`. `--requirements` is optional. Omit either
output option to skip that file. The JSON report is deterministic and suitable
for automated triage; the Markdown report is a readable summary. Both contain
relative paths only. Inputs must be UTF-8 JSON regular files no larger than
64 MiB each.

## Snapshot contract

Snapshots use `schema_id` `org.koei-tecmo.game-install-snapshot` and
`schema_version` `1`. The required identity fields are `game_id`,
`platform_id`, and `version` (`value` and `source`, with optional `build_id`).
`captured_at` may contain a timezone-aware ISO-8601 capture time. The remaining
arrays are sorted observations:

| Field | Meaning |
| --- | --- |
| `files` | `relative_path`, `size_bytes`, and SHA-256. A missing hash is represented as `null` and stays unverified. |
| `archives` | `relative_path`, optional `format_id`, a `parsed`, `unsupported`, or `malformed` status, and the observed `entries`. |
| `archives[].entries` | `path`, `size_bytes`, and optional `compressed_size_bytes`, `crc32`, and SHA-256. Members without CRC or SHA-256 are listed as unverified. |
| `formats` | Supported format `id`, optional `revision`, `evidence_paths`, and optional confidence. |

When an archive changes between `parsed` and an unknown state, the report keeps
the parsed side's member list under `entries.observed_before` or
`entries.observed_after`. It does not classify those members as added or
removed because the other side could not be inspected.

Every path is a normalized relative POSIX path. Absolute install paths and file
contents do not belong in snapshots or reports. The analyzer validates the
schema, identity, hashes, and paths before comparing data. Unsupported or
malformed archive observations stay unknown; the analyzer does not guess at
their structure.

## Compatibility requirements

Requirements use `schema_id` `org.koei-tecmo.compatibility-requirements` and
`schema_version` `1`. Each entry has a stable `id`, a display `name`, a `kind`
(`mods`, `tools`, or `saves`), and matching `game_id` / `platform_id`. Optional
pins can state supported `supported_versions` / `supported_build_ids` exact
allowlists, required file SHA-256 values, supported format IDs/revisions, and
required archive entries. These are compatibility expectations supplied by
the owning tool or mod; the analyzer does not infer them from the save editor's
registered profiles. If both version and build allowlists are present, both
must match.

When an explicit requirement matches the baseline but not the candidate, the
report marks that requirement as potentially affected and includes the evidence.
A changed file with no matching requirement remains a reported change, not a
compatibility failure. Missing evidence is labeled unknown.

The JSON `version_change.changed` field is `true`, `false`, or `null` when a
confirmed change, confirmed lack of change, or uncertain version/build evidence
is observed. Unknown version sentinels and a build ID present on only one side
produce an uncertain result; the report records the reason in
`version_change.evidence_reasons`.

```json
{
  "schema_id": "org.koei-tecmo.compatibility-requirements",
  "schema_version": 1,
  "requirements": [
    {
      "id": "example-mod",
      "name": "Example Mod",
      "kind": "mods",
      "game_id": "example-game-pc",
      "platform_id": "windows",
      "supported_versions": ["1.2.0", "1.2.1"],
      "supported_build_ids": ["12345"],
      "required_files": [
        {"relative_path": "data/example.bin", "sha256": "<64 lowercase hex characters>"}
      ],
      "required_formats": [{"id": "save-header", "revision": "2"}],
      "required_archive_entries": [
        {"relative_path": "data/resources.pak", "format_id": "example-pak-v1", "path": "save/header.dat"}
      ]
    }
  ]
}
```

## Example shape

```json
{
  "schema_id": "org.koei-tecmo.game-install-snapshot",
  "schema_version": 1,
  "game_id": "example-game-pc",
  "platform_id": "windows",
  "captured_at": "2026-10-22T12:00:00Z",
  "version": {"value": "1.2.0", "source": "tracker", "build_id": "12345"},
  "files": [
    {"relative_path": "data/example.bin", "size_bytes": 4096, "sha256": "<64 lowercase hex characters>"}
  ],
  "archives": [
    {
      "relative_path": "data/resources.pak",
      "format_id": "example-pak-v1",
      "status": "parsed",
      "entries": [{"path": "save/header.dat", "size_bytes": 128, "compressed_size_bytes": 96, "crc32": "a1b2c3d4"}]
    }
  ],
  "formats": [
    {"id": "save-header", "revision": "2", "evidence_paths": ["data/example.bin"], "confidence": "observed"}
  ]
}
```

The placeholder hash above is documentation only; use an actual SHA-256 value
in inputs. Do not put game binaries, saves, extracted assets, or personal install
paths in the repository.

## Reproducible validation

The focused suite is `python -m unittest discover -s tests -p
'test_game_compatibility.py' -v`. Its procedural snapshots cover change
classification, malformed or unsupported archive observations, explicit
requirement impacts, deterministic exports, and source immutability. These tests
validate analyzer behavior; they do not establish that a particular mod, tool,
game build, or save loads correctly.
