# Research Import — additional game candidates

Open **Editing and Research → Research Import**, or search for it with **Ctrl+K**.
This read-only workspace imports separately copied files from explicitly listed
research candidates. It does not add supported editing profiles, expose gameplay
writes, repair damaged data, export game saves or run conversions.

The persistent banner is **Research only — no editing or game-load qualification.**
Each candidate has its own reader. Rejection never tries another game's parser.
Use the exact file and required original companion shown before browsing.

| Candidate | Exact copied input | What the report establishes |
| --- | --- | --- |
| Dynasty Warriors: Gundam 2, US/EU PS3 | Revision-13 decrypted `DATA.BIN`, original BLUS30288/BLES00528 `PARAM.SFO` | Native byte-sum validation and four published pilot level-index/point records. Growth curves, rewards and gameplay writes remain unqualified. |
| Atelier Totori Plus, US Vita | Decrypted extensionless `USR-DATA0000`, original PCSE00231 `sce_sys/param.sfo` | Exact own-title TLV framing and an uninterpreted tag-3 word. No wallet semantics or native integrity claim. |
| Atelier Rorona Plus, US Vita | Decrypted extensionless `USR-DATA0000`, original PCSE00466 `sce_sys/param.sfo` | Exact own-title TLV framing and an uninterpreted tag-3 word. Assignment/calendar and field dependencies remain unresolved. |
| Atelier Ayesha Plus, US Vita | Decrypted extensionless `USR-DATA0000`, original PCSE00584 `sce_sys/param.sfo` | Exact own-title framing and an uninterpreted tag-3 word. PS3 addresses are not transplanted. |
| Uncharted Waters IV Power-Up Kit, original Windows | A copied `.DK4` file with the exact observed native header and one of the admitted 39,486–39,870-byte lengths | Header and declared-length observations only. The header word at +24 and gameplay record semantics are unclassified; body corruption may pass this framing gate. No checksum, playable-save or editing claim. HD files are rejected. |

## Read a copied candidate

1. Keep the complete original save folder untouched. Export/decrypt console
   gameplay with the platform's save manager first; authentication stays external.
2. Select an exact research candidate and read its required filename, companion
   and limitations. **Find candidate** searches the reviewed list; it does not
   discover unknown formats or load arbitrary plugins.
3. Browse to a separate copy and choose **Inspect copied file**. Reads are bounded
   by that profile. The original gameplay and context are rechecked around report
   creation. A changed source, conflicting metadata or rejected format prevents
   the report from being accepted.
4. Read the snapshot report. Profile, input size, SHA-256 and exact qualification
   limits stay distinct from native integrity and gameplay loading. Reports may
   contain private mapped values, but do not include input paths or owner metadata.
5. Switching tools preserves this local workspace. Changing the profile or source,
   filtering out the selected candidate, or **Clear import** removes the old
   report. Inspect again after changing the file or its original metadata.

The workspace uploads nothing and writes no backups, reports or game files.
No Save As, Max, repair, editor-opening or conversion action is available. Text
can be read and selected locally; review it before sharing values elsewhere.

The existing source CLI remains available with the same explicit interface:

```text
python -m tools.inspect_candidate --profile gundam2_ps3 copied/DATA.BIN
python -m tools.inspect_candidate --profile totori_plus_vita copied/USR-DATA0000
python -m tools.inspect_candidate --profile dk4pk_pc copied/SaveDat0.DK4
```

## Evidence and validation

The original four inspectors and their evidence are described in
[Additional title qualification](EXPANSION_CANDIDATES.md). The DK4 framing
matches eight complete public original-PK references from
[supermizar/dk4pk](https://github.com/supermizar/dk4pk) and the native identity in
[litsungyi/Dk4PkEditor](https://github.com/litsungyi/Dk4PkEditor/tree/7552b18275e9d404f3eae7c1984b2a8b3926c63d).
The old editor branch is commented and the historical Kafka helper performs
raw writes without explaining header +24. Those facts do not prove absence of
native integrity. The new inspector deliberately stops at observed framing;
there is no hypothetical checksum reconstruction or gameplay-field import.

`test_research_import.py` covers every selected reader, source preservation,
wrong/oversized inputs, foreign title metadata, source/context races, rejected
and stale worker results, read-only GUI records, themes, retained navigation,
command/menu integration and the preserved CLI. `DK4PK_NATIVE_DIR` optionally
checks the private complete original-PK references without writing them. Generated
fixtures are distinguished from native-file observations and in-game validation.
No private file, account context, external source tree or game asset is packaged.
