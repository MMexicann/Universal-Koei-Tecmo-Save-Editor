# Save Research Lab

The read-only Research Lab compares two separate copies using one explicitly
selected registered scalar game/platform parser. It retains the comparison's
mapped field search, status filters and pagination. Native input qualification,
required companion metadata and protections remain authoritative; a rejected
save is never passed to another profile. DW3's tagged document workflow is not
a scalar research profile.

Double-click a changed mapped field or decoded change run to inspect its offset.
Offsets refer to the **decoded payload**, not the encrypted native file,
container entries or exported console wrapper. The lab shows contiguous changed
runs, bounded hexadecimal windows, changed byte indexes, XOR and changed bits,
both endian signed/unsigned integers and finite or explicitly labelled nonfinite
float interpretations. Native scalar storage overlaps identify already mapped
spans; overlap does not qualify unknown packed bits or additional writes.

Candidate discovery searches both snapshots for exact before/after integer
observations, with explicit 1/2/4/8-byte widths, byte order, signedness and
alignment. The Python API additionally supports bounded offset ranges. Matches
are **unverified hypotheses**, including matches overlapping existing fields.
Multiple encodings may correlate with the same action. No match creates an
editable field or invents a semantic mapping. Use one controlled game action,
an unchanged control, then independent pairs and record identities to test each
hypothesis. Establish native dependencies, encoding and surgical roundtrips
before proposing an adapter change.

Annotations attach a title, observation/hypothesis and evidence or next experiment
to a decoded offset and bounded span. Controlled-action notes describe the pair.
Both remain attached to this retained comparison; choosing a new profile or
source clears the research state. Remove annotations individually as needed.

**Export for Codex** creates a new private JSON report with schema
`koei-save-research`, version 1. It contains the existing qualified comparison
report, source/payload hashes, controlled-action notes, annotations, up to 1,000
decoded change runs with bounded previews, the last inspected offset and the
last candidate query/results. Total counts and truncation flags distinguish
bounded previews from complete results. Source paths, native companion files
and complete raw saves are omitted. Decoded excerpts, mapped names/values and
free-text notes can still be personal: inspect the report before sharing it.

Exports use guarded atomic new-file storage, revalidate both sources and original
metadata before and after writing, and read back the actual report. Existing
files are never replaced. The lab never stages edits, calls a native save writer,
repairs integrity, creates backups, or changes save bytes. A source change makes
export fail and requires a new comparison.

`tests/test_research_lab.py` covers procedural qualified native comparisons,
exact numeric correlation, encoding ambiguity and invalid requests, bounded
annotations and research reports, forged snapshots, stale metadata, output races
and source preservation. `tests/test_research_lab_gui.py` exercises real Tk
workers, field/offset navigation, retained research, annotations, exports,
scrolling and stale worker rejection. These procedural checks are not genuine
player-save qualification or in-game load/re-save evidence.
