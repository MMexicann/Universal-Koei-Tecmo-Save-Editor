# Help and Compatibility Center

Open Help from global navigation, F1, or Ctrl+K. The center keeps game-specific
dashboards and editing workflows intact. Its offline help, platform guides and
navigation labels support English and German; reviewed game descriptions and
source evidence retain their original wording.

Compatibility lists only registered game/platform profiles. Search title, short
ID, edition/revision scope, functionality and evidence together, or restrict the
platform. Select a row to read implemented functionality, genuine-file evidence
and remaining validation. Edition subtitles are the registry's reviewed scope;
they do not imply an exact software build unless explicitly documented.
Research-only candidates do not become supported profiles through this view.

Genuine-file qualification and edited game-load/re-save validation are separate.
The existing evidence catalog does not contain structured game-load attestations,
so the center explicitly reports that absence. Community validation reports do
not automatically change the catalog or adapter registry.

## Installed game builds

The **Game Versions** tab checks a fixed list of reviewed Steam app IDs and
their install manifests. It reads bounded Steam library and app metadata, checks
that the mapped install folder exists, and never starts a game. This scan does
not inspect save files, Steam `userdata`, account IDs, native save folders, or
non-Steam stores. It currently detects only mapped Windows PC Steam profiles;
an absent result does not mean that another store, edition, platform, or game is
unsupported. Install paths stay in the scanner's local memory and are not shown
or written to tracker history.

The Steam `buildid` is an installation build marker. `LastUpdated` is shown
separately. Neither value is a save-format revision or proof that an editor,
mod, configuration utility, or asset format works with that build. The tracker
joins reviewed compatibility entries only on the exact registered game profile,
Steam app ID, platform, and decimal Steam build ID. It never infers a match from
a title, family, nearby version, community-plugin text, a different app ID, or
another build's result.

Each exact-build entry identifies a save editor, mod, configuration tool, or
asset format, its reviewed version, status, reason code, explanation, check time,
and evidence references. The tracker does not detect installed mod/tool versions
or inspect local assets; the version shown is the version in the catalog review.
For a `config_tool`, `artifact_version` is the utility's own release version, not
the configuration file format revision; for an `asset_format`, it is the named
format revision. Editor and mod entries use their reviewed release/version.
`verified` and `unsupported` entries require an exact build, artifact version,
and evidence. `unknown` means no exact review is available; it is not a warning
that the build is incompatible. An explicit `unsupported` result applies only
to the matching profile/build/artifact tuple, requires a next step that resolves
to a Help article, and explains the evidence. A record for an older build never
marks a newly detected build unsupported.

When a valid Steam build ID changes, local history records a first detection or
a build change. The warning prompts a review of exact-build records; the change
alone does not establish incompatibility or assert the current compatibility
status. If a manifest has no valid build ID, the current install is still listed,
but it does not create or replace a history entry. History is stored next to the
local app preferences without install paths, account IDs, or save data. Malformed
history is preserved and reported instead of being overwritten; the current scan
remains visible.

The packaged `data/version_compatibility.json` catalog is deliberately empty
until exact-build evidence has been reviewed. To add an entry, use a registered
Windows PC profile and mapped Steam app ID, exact decimal build ID, one of the
four artifact kinds, the specific reviewed artifact version, a timezone-qualified check time, a stable reason
code, concise explanation, relative `docs/...` or HTTPS evidence references,
and Help article IDs from `evidence` and `troubleshooting` for unsupported
entries. The UI displays the localized Help article titles for next steps.
Reject blank artifact versions; catalog versions must identify the specific
tool release or format revision being reviewed.
Open the matching topic from the Help tab to read the full guidance.
Use `unknown` when evidence is absent. Do not turn editor file-scope evidence,
Steam `LastUpdated`, install presence, or a community contribution into an exact
compatibility claim. Add focused procedural fixtures for every catalog change.

The **Compatibility history** table shows every reviewed entry for the selected
game profile, ordered by check time; the **Build history** tab shows local
first-seen and build-change observations. These histories have different
sources: compatibility history comes from the reviewed catalog, while build
history comes from this computer's install scans.

Guides cover preparation, copied imports, new-destination exports and testing.
Console guides retain companion-file context and leave extraction, encryption,
ownership and signing to external authorized platform tools. The help search
covers field explanations, keyboard controls, troubleshooting and privacy. Existing
editor field hints remain the authority for individual field constraints.

The center lazily opens separate Plugins, Validation and Feedback panels. These
panels never open a player save or transmit a report. Preview reports and plugin
contributions before enabling or sharing them.

Developer entrypoints are `shared.help_center.HelpCenter`,
`shared.compatibility_center.compatibility_entries` and
`shared.help_content.help_articles`. They use qualified imports, package-owned
text and the existing registry/catalog. Exact-build matching does not import
game backends. Add help topics in both languages with matching stable IDs;
update registry evidence through the existing reviewed support workflow.

Focused verification: `python -m unittest discover -s tests -p test_help_center.py`.
GUI tests need a display. Native Windows release checks remain separate.
