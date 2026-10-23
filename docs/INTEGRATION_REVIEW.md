# Combined development integration

This review integrates the 14 open pull-request heads present at the start of
the requested integration. Main contains the combined source after required
checks pass; application version and latest published release remain v1.6.
No tag or new GitHub release is created. Windows workflow artifacts are preview
downloads for testing the development source.

## Reviewed snapshots

| Pull request | Pinned head | Change |
| --- | --- | --- |
| [#5](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/5) | `bdb3833a1ad4169c12d3f889d5e971dc481c9cc2` | Prepare additional game editors and searchable library |
| [#6](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/6) | `3da79cd349251e2dec07585d1f8190d8194bf040` | Independent validation: guard staged edits and inspector edge cases |
| [#7](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/7) | `0ba87f455bd135a671f0062ce9d4f66584599deb` | Add PS3 WO3 Ultimate resources and DW8 Empires horse controls |
| [#8](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/8) | `0729f5b0ae573ed5a5d81ae87e02309cd8091b4e` | Add native Samurai Warriors 4-II PC editor and Musou qualification |
| [#9](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/9) | `1aabfb13d66ec10b6fcfd0bc32156b64327e8e02` | Add qualified original Sophie, Ryza 2 and Fatal Frame II save editors |
| [#10](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/10) | `0adc10fa67328cd28e1fa14ea6b9a7027af1ebb0` | Document blocked Windows Toukiden and Monster Rancher qualification |
| [#11](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/11) | `ae481bbb2d7591f027ee132e94aa0f2279e9b016` | Add native Nioh 3 and original Ninja Gaiden II editors |
| [#12](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/12) | `5bce24445b480b472401097d47ea1991adab71d8` | Blocked: qualify Windows DQH and Fate editor evidence |
| [#13](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/13) | `bc2f6882720edfe9bef1b1658fa6eaa5145011fd` | Add scoped Gundam and Ken's Rage PS3 export editors |
| [#14](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/14) | `bfd2b5d0ea8791619f60963f0eff0ff372cbb2db` | Add original PC ROTK XIII city resources, population and training editor |
| [#15](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/15) | `e72a830180bab1f401d98ccc5dff8ddbc4a94afe` | Qualify Berserk/AoT Windows envelopes and document editor blockers |
| [#16](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/16) | `a7013f12e6e17a5ed371c867fa3af7ae2d22c606` | Qualify Special/regional editions and add read-only PSP inspection |
| [#17](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/17) | `ea0cde81e2f85c6a26fce7648a2f0a8d68b262a1` | Add original Windows PC Samurai Warriors 2 and Warriors Orochi editors |
| [#18](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/18) | `7b1a8483909ee6619d41890e3a565938347d6508` | Add Three Houses Switch v13/v23 gameplay export editor |

All additions are retained in the application package, tests or development
notes. Research-only work has no editable library card: this includes the
Toukiden/Monster Rancher, DQ Heroes/Fate, Berserk/AoT and PSP Special lanes.
The registry and generated supported-game inventory describe actual controls,
including reduction-only controls and read-only inspectors where appropriate.

## Integration fixes

- Preserve every incoming editor registration and metadata entry when resolving
  concurrent registry, inventory, manifest and documentation additions.
- Freeze and recheck PS3 companion identity/context for copied-save operations;
  reject changed source or destination metadata before saving/restoring.
- Require canonical immutable format identity and validate malformed pending
  edits/keys in the newly reviewed Gust and strategy parsers.
- Reject nonfinite Fatal Frame JSON exponent overflow while preserving finite
  unknown lexical values and native binary/photo bytes.
- Declare Nioh 3 integrity using the shared checksum contract, restoring the
  registered copied-save self-test.
- Align Ken's Rage backend self-test qualification flags with their registered
  source-backed scope; native integrity/edit qualification is not overstated.
- Keep GUI Undo tests consistent with restoring the opened field value before
  explicitly applying a new edit.
- Complete mocked Review dialog font/scrollbar setup and compare canonical
  saved-file identities in Windows GUI tests. Synthetic CBC fixtures use
  immutable bytes, matching the native Windows encryption provider contract.

## Validation

Individual reviews use procedural adversarial checks, independently acquired
genuine public saves and actual Tk workflows where inputs are available.
Public source tests do not distribute player files. Native file serialization
and GUI testing are separate from actual edited game load/re-save validation,
which has not been performed.

Combined Linux/Tk and Windows test/build results are recorded in
[integration PR #19](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/19).
The Windows workflow must verify source manifests, registered interfaces,
standalone EXE startup, embedded metadata/privacy and packaged archive hashes
before its artifact is offered as the preview download.

The ROTK XIII author reports seven genuine Traditional Chinese campaigns in
its branch validation. The integration review independently rechecked the
original period reader/writer's encoding, revision and field facts, procedural
GUI/format tests and rejection of unrelated native exports. The seven campaign
inputs and original public download provenance were unavailable to this review,
so those seven positive native checks were not independently repeated.
