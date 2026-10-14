# Compare Saves

Compare Saves shows changes between two independently qualified copies of the
**same registered game/platform profile**. It is available for the library's
93 scalar profiles; DW3's separate tagged editor is excluded from this workflow.
The comparison validates the exact selected backend, format, native integrity
and each copy's required original console metadata. It does not edit gameplay
files or create gameplay backups.

1. Open **Compare Saves**, select the exact game/platform and choose both copies.
2. Keep each console copy's own original companion metadata beside it. Different
   valid owner/slot contexts can be compared; neither context is transferred.
3. Select **Compare copies**. Browse changed values, changed field definitions,
   or fields available in only one copy. Search by record, field, group or ID.
4. Use the difference filter and Previous/Next controls for large results.
5. Optionally export a new JSON report. Replaced sources or metadata invalidate
   export; repeat the comparison after a change.

The workspace, results and filters remain when switching to the library, an
editor or Save Converter. Its worker performs file/parsing work outside Tk;
late results from changed selections are discarded. Closing waits for an active
copied-save operation. Themes use the shared application styles.

## Interpret the results

Field IDs align within one explicit profile. A conditional inventory record can
be editable in only one save, and a record's label, encoding or storage position
can change. Those differences are reported separately from an ordinary value
change. Editable names are compared as exact text; numbers remain exact typed
integers, including readable higher original values. Named record labels use
the existing backend presentation hook.

The summary counts differing decoded payload bytes, including length changes.
It separately counts bytes outside the union of both copies' editable field
storage spans. This can include checksum bytes, padding, unmapped progression
or changed serialized geometry. For packed fields, their entire declared byte
span is counted within the field's storage span: the comparison does not prove
that every bit in that byte is editable. Ciphertext differences and original
console metadata are not counted as gameplay payload differences.

A difference is an observation, not a new write mapping or proof of record
ownership. Comparison does not infer a conversion, apply another save's values,
remove inventory records or bypass either input's native checksum. Experimental
editing is unnecessary for reading unusual original values.

## Headless use

```text
python -m koei_editor --game dw8xl --compare first.dat second.dat
python -m koei_editor --game dw8xl --compare first.dat second.dat --comparison-report comparison.json
```

The first form prints JSON without writing a report. The second creates a new
`.json` file atomically and validates actual report read-back. An existing
report or gameplay file is never replaced. Comparisons require `--game` and
cannot be combined with converter options, self-tests or GUI smoke tests.

Schema 1 reports include the selected profile, raw/decoded SHA-256 hashes,
summary counts and typed difference rows. They omit source paths, gameplay
bytes, original companion bytes, account identifiers and signing information.
**Mapped editable names and scalar values can be personal**; keep a report
private when appropriate. Report export verifies its frozen summary and rows
against both native snapshots, then rechecks both files and original metadata
before and after writing. Procedural regressions cover forged counts/types,
conditional definitions, metadata/source races, aliases, read-back and CLI.
Private independent Qoga exports additionally qualify a real same-title pair.

This tool does not perform game-load/re-save validation. It helps inspect
controlled action pairs and preserve evidence while further formats are mapped.
