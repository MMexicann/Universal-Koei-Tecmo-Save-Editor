# Mod Workshop implementation report

```yaml
schema: koei-mod-workshop.implementation-report.v1
status: implemented
features:
  project_templates: [blank, texture-replacement, audio-replacement]
  asset_replacement:
    project_contained_sources_only: true
    sha256_integrity: true
    rights_declaration_required: true
    permissive_attribution_required: true
    original_game_asset_extraction: false
  dependencies:
    required_and_optional: true
    semantic_version_constraints: true
  compatibility:
    checks: [game_id, game_version, platform, installed_mod_dependencies]
    context_source: user-entered
    runtime_game_validation: false
  packaging:
    format: ZIP
    contents: [mod.json, verification.json, declared replacements only]
    deterministic: true
    verification: [metadata, archive paths, membership, replacement SHA-256]
    rights_verification: self-declared
    per_replacement_limit_bytes: 268435456
    total_uncompressed_limit_bytes: 1073741824
tests:
  command: "PYTHONPATH=src python -m unittest discover -s tests -p 'test_mod_workshop_*.py' -v"
  passed: 43
  failed: 0
  skipped: 2
  skip_reason: "GUI integration needs a display, unavailable in the headless review environment."
review:
  independent_read_only_review: complete
  blocking_findings: 0
  known_scope_limits:
    - Rights and licenses are declarations from the project author.
    - Compatibility uses user-entered game and installed-mod information.
    - No game loading or in-game behavior validation is performed.
release:
  version_changed: false
  release_created: false
```
