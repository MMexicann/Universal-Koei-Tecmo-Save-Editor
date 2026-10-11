# Ninja Gaiden 2 Black — Steam compiled-editor recheck

This recheck adds research evidence, not a writable game profile. See
[the native Ninja Gaiden research](NINJA_GAIDEN_RESEARCH.md) for the bounded
GVAS inspector and separate story/system integrity blockers.

## What the public editor actually writes

[real-guilty/NG2B-Save-Editor](https://github.com/real-guilty/NG2B-Save-Editor/tree/fd7b25934e9cda24d47d9a59c7b7a3398ef22a0f)
contains compiled PyInstaller artifacts rather than application source. No
explicit reuse licence was found. Its Python 3.12 application code object was
extracted as data from the package archive and statically disassembled. Neither
the downloaded application nor its dependencies were imported or executed.
No application implementation or assets are incorporated into this project.

The complete observed application write path reads the selected file into a
byte array, replaces literal absolute-file slices for checked controls, and
writes the complete array back. Unchecked controls leave their existing bytes
alone. There is no title, GVAS revision, property, array-length, native checksum
or dependency validation in that path. No native checksum is recomputed.

The exposed controls are chapter-challenge/difficulty unlocks, story-completion
flags and Tag Mission completion/weapon/Ninpo unlocks. They are not proven
Essence, item-quantity, weapon-upgrade or other safe resource controls. The
README explicitly describes brute-force unlocks and mutually exclusive Tag
weapon choices. Those flags must not be presented as a rich gameplay editor
or a safe all-equipment action.

Representative factual write locations are absolute file bytes 8648 and 8654
for chapter-challenge/Master Ninja unlocks, 3099–3114 for four completion words,
8659–8708 for fifty Tag Mission flags, and 8710 onward for weapon selections.
The application never derives these positions from the GVAS property tags.
These are research observations, not approved mappings or portable offsets.

## Independent native check and remaining gate

The existing bounded inspector was independently rerun against all nineteen
private genuine Steam copies: eighteen story files and one system file. The
observed system byte array begins at file byte 1791 and contains `0x24B0`
bytes. Story arrays contain `0x8280` bytes and begin at eight different
header-derived positions, ranging from 2023 to 2039. This corroborates why
absolute-file offsets cannot define a general container parser or a story
layout. The system and story structures remain separate.

The compiled editor's direct writes do **not** establish that native inner
integrity is absent or that edited saves are accepted. Story revision 6 has
a verified metadata CRC and a separate unresolved payload checksum; system
integrity and unlock/reward dependencies still lack qualification. An unchanged
roundtrip proves preservation, not acceptance of modified native payloads.

The specific remaining inputs are a complete title/revision-matched native
serializer/checksum implementation or demonstrated edited-file acceptance,
followed by controlled gameplay pairs proving spendable resources, equipment
ownership/equipped references and prerequisite/reward behavior. Existing saves
are available; another unexamined archive alone does not close these gates.
No game-load test was performed, and no player files, native contents,
identifiers or downloaded compiled artifacts are published.
