# Scalar adapter starter

This scaffold stays unregistered and rejects every file until its native format
and storage encoding are implemented. It supplies no game offsets or support
claim. Read [CONTRIBUTING.md](../../CONTRIBUTING.md) and the
[root agent guide](../../AGENTS.md).

1. Create `src/koei_editor/games/<game>/` with `__init__.py`. Copy and rename the
   parser/editor scaffolds into that package; use qualified package imports.
   Choose a stable game/platform ID. Do not copy files into the repository root.
2. Qualify title/revision, size, structure, integrity, codec/container metadata
   and occupied records. Implement the codec seams and a frozen field type
   satisfying `koei_editor.shared.adapter_contract.ScalarField`, with evidenced
   bounds and storage encoding. `maxable=False` must exclude dependency-sensitive
   choices and unproved natural caps from bulk actions. The bound adapter decodes
   every edited save and compares its payload to the requested payload; a backend
   that recomputes payload integrity words may declare exact byte ranges in
   `SERIALIZED_INTEGRITY_RANGES = ((start, end), ...)`. Ranges are half-open
   offsets into the decoded payload and may cover only verified integrity bytes
   that the serializer deterministically recalculates. All mapped edits must
   still read back as their requested values, and changes outside those ranges
   must still fail verification. Never use this declaration to hide unknown or
   unexpected serializer differences.
3. Register the implemented game in `koei_editor.game_registry.GAMES` with
   qualified editor/parser/backend module paths, extension, platform and honest
   provenance. Update reviewed runtime metadata, the supported-game inventory,
   README/document and tests together. Research without an editor remains in
   `src/koei_editor/research/<game>/`, outside the gameplay library.
4. Optional `record_label`, `field_hint` and `inspection_rows` backend hooks
   customize inspection. Richer views subclass `ScalarPresentation` and set the
   editor's `presentation_type`. Add no game-ID branches to shared GUI/CLI code.
5. Copy `contract_test.py` into `tests/test_<game>_contract.py` and supply
   `fixture_bytes()`. Test no-op/stage/unstage, targeted payload edits, rejection,
   immutable input, backups/restore, new destinations and changed-source safety.
   Add format corruption, identity, array/revision variation and dependency
   checks. Synthetic success is separate from native-file/in-game evidence.
6. Install and run focused tests, integration/GUI checks and the smoke test.
   Regenerate supported inventories with `python -m tools.update_supported_games`
   and verify `--check`. Coordinate qualified build imports/data and reviewed
   source-manifest additions. Add a format/evidence document to the docs index.

```text
python -m pip install -e .
python -m unittest tests.test_<game>_contract -v
python -m koei_editor --smoke-test
```

The copied-save CLI is `python -m koei_editor --game YOUR_ID --self-test INPUT
EMPTY_OUTPUT_DIR`. It preserves the input and creates private reports and
edited/restored copies. Reports and player fixtures never belong in public
source archives.
