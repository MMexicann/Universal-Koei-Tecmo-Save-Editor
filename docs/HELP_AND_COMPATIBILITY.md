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
text and the existing registry/catalog. Compatibility discovery does not import
game backends. Add help topics in both languages with matching stable IDs;
update registry evidence through the existing reviewed support workflow.

Focused verification: `python -m unittest discover -s tests -p test_help_center.py`.
GUI tests need a display. Native Windows release checks remain separate.
